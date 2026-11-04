"""Textual application scaffolding for atv."""

from __future__ import annotations

import asyncio
import sys
import difflib
from pathlib import Path
import shlex
import webbrowser
from typing import Iterable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Log, Static

from .inspection import artifact_path, execute, profile_command
from .processes import ProcessInfo, list_python_processes


class ProcessTable(DataTable):
    """Tabular view of detected Python processes."""

    def on_mount(self) -> None:  # noqa: D401 - Textual lifecycle hook
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns("PID", "Process", "File", "Command line")

    def get_selected_pid(self) -> int | None:
        """Return the PID associated with the highlighted row, if any."""

        if self.row_count == 0:
            return None
        coordinate = self.cursor_coordinate
        if coordinate is None:
            return None

        # Always read PID from column 0 to avoid reliance on internal row keys.
        pid_coordinate = Coordinate(coordinate.row, 0)
        try:
            pid_value = self.get_cell_at(pid_coordinate)
        except Exception:  # pragma: no cover - defensive safeguard
            return None

        try:
            return int(pid_value)
        except (TypeError, ValueError):
            return None

    def update_processes(self, processes: Iterable[ProcessInfo]) -> None:
        """Replace the table content with the given process collection."""

        selected = self.get_selected_pid()
        self.clear(columns=False)
        for info in processes:
            display_name = info.name or "(unknown)"
            file_display = info.file or "-"
            self.add_row(
                str(info.pid),
                display_name,
                file_display,
                info.command_line,
                key=info.pid,
            )

        if self.row_count:
            self.cursor_coordinate = (0, 0)
            if selected is not None:
                for row in range(self.row_count):
                    if str(self.get_cell_at(Coordinate(row, 0))) == str(selected):
                        self.cursor_coordinate = (row, 0)
                        break


class AtvApp(App):
    """Primary Textual application for atv."""

    CSS = """
    #content {
        layout: horizontal;
        padding: 1 2;
        height: 1fr;
    }

    #process-pane, #output-pane {
        layout: vertical;
        height: 1fr;
    }

    #process-pane {
        width: 1fr;
    }

    #output-pane {
        width: 2fr;
        margin-left: 2;
    }

    #intro {
        color: #b3b3b3;
    }

    DataTable {
        height: 1fr;
    }

    Log {
        height: 1fr;
        border: round $accent;
        padding: 0 1;
    }
    """

    TITLE = "atv"
    SUB_TITLE = "Task inspection and Tachyon profiling"

    def __init__(self, *, python: str = sys.executable, duration: int = 10,
                 output_dir: Path | None = None):
        super().__init__()
        self.python = python
        self.duration = duration
        self.output_dir = (output_dir or Path.home() / ".atv" / "captures").expanduser().resolve()
        self.snapshots: dict[tuple[int, str], str] = {}
        self.current_snapshot: tuple[int, str, str] | None = None
        self.current_diff: str | None = None
        self.last_profile: Path | None = None
        self.busy = False
        self.operation = None


    BINDINGS = [
        Binding("r", "refresh_processes", "Refresh", priority=True),
        Binding("enter", "inspect_selected", "Inspect"),
        Binding("p", "inspect_selected", "Inspect"),
        Binding("t", "inspect_tree", "Await tree"),
        Binding("s", "save_snapshot", "Save"),
        Binding("d", "show_diff", "Diff"),
        Binding("f", "profile_running", "Profile running"),
        Binding("g", "profile_all", "Profile all"),
        Binding("o", "open_profile", "Open HTML"),
        Binding("x", "cancel_operation", "Cancel"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Container(
                Static(
                    "Select a Python process to inspect. Press R to refresh. \n"
                    "Enter: tasks · T: await tree\n"
                    "F: running tasks · G: include waiting tasks\n"
                    f"Profile: {self.duration}s · observer: {self.python}",
                    id="intro",
                ),
                ProcessTable(id="process-table"),
                id="process-pane",
            ),
            Container(
                Static("Awaiting selection", id="ps-title"),
                Log(id="ps-output"),
                id="output-pane",
            ),
            id="content",
        )
        yield Footer()

    def on_mount(self) -> None:  # noqa: D401 - Textual lifecycle hook
        self.refresh_process_list()

    def action_refresh_processes(self) -> None:
        """Binding target: refresh the process table."""

        self.refresh_process_list()

    def action_inspect_selected(self) -> None:
        self.start_operation("ps")

    def action_inspect_tree(self) -> None:
        self.start_operation("pstree")

    def action_profile_running(self) -> None:
        self.start_operation("running")

    def action_profile_all(self) -> None:
        self.start_operation("all")

    def start_operation(self, kind: str) -> None:
        if self.busy:
            self.notify("An observation is running. Press X to cancel it first.")
            return
        pid = self.query_one(ProcessTable).get_selected_pid()
        if pid is None:
            self.notify("Select a Python process first.", severity="warning")
            return
        self.busy = True
        self.query_one("#ps-title", Static).update(f"{kind}: observing PID {pid}…")
        self.query_one("#ps-output", Log).clear()
        self.operation = self.run_worker(self.observe(pid, kind), name=f"{kind}-{pid}")

    def action_cancel_operation(self) -> None:
        if self.busy and self.operation is not None:
            self.operation.cancel()

    def display(self, title: str, content: str) -> None:
        self.query_one("#ps-title", Static).update(title)
        log = self.query_one("#ps-output", Log)
        log.clear()
        log.write_lines(content.splitlines())

    async def observe(self, pid: int, kind: str) -> None:
        try:
            output = None
            if kind in {"ps", "pstree"}:
                command = [self.python, "-m", "asyncio", kind, str(pid)]
            else:
                probe = await execute([self.python, "-m", "profiling.sampling", "attach", "--help"])
                if probe.returncode:
                    self.display("Tachyon is unavailable", probe.output +
                                 "\nChoose a Python 3.15+ observer with --python. Match the target Python version/build.")
                    return
                output = artifact_path(self.output_dir, pid, kind, "html")
                command = profile_command(self.python, pid, kind, self.duration, output)
            result = await execute(command, timeout=self.duration + 20 if output else 20)
            text = f"$ {shlex.join(command)}\n\n{result.output}"
            if result.returncode:
                self.display(f"Observation failed: PID {pid}", text +
                             "\nCheck that the target is still running and uses asyncio.\n"
                             "Match the observer Python version/build to the target.\n"
                             "Permission help: https://docs.python.org/3/howto/remote_debugging.html#permission-requirements")
                return
            if output is not None:
                if not output.is_file() or output.stat().st_size == 0:
                    self.display("No profile was generated", text)
                    return
                self.last_profile = output
                self.display(f"Profile complete: PID {pid} ({kind})", text +
                             f"\nSaved: {output}\nPress O to open this profile in your browser.")
            else:
                key = (pid, kind)
                previous = self.snapshots.get(key)
                self.current_diff = None if previous is None else "".join(difflib.unified_diff(
                    previous.splitlines(keepends=True), result.output.splitlines(keepends=True),
                    fromfile="previous capture", tofile="current capture"))
                self.snapshots[key] = result.output
                self.current_snapshot = (pid, kind, result.output)
                self.display(f"{kind}: PID {pid} · S save · D compare previous capture", text)
        except asyncio.CancelledError:
            self.display("Observation cancelled", "The observer stopped; the target process was not terminated.")
            raise
        except TimeoutError:
            self.display("Observation timed out", "The observer stopped. Check the target and its permissions.")
        except (OSError, ValueError) as exc:
            self.display("Observation failed", str(exc))
        finally:
            self.busy = False

    def action_save_snapshot(self) -> None:
        if self.current_snapshot is None:
            self.notify("Capture tasks or an await tree first.")
            return
        pid, kind, text = self.current_snapshot
        try:
            path = artifact_path(self.output_dir, pid, kind, "txt")
            path.write_text(text)
        except OSError as exc:
            self.notify(str(exc), severity="error")
        else:
            self.notify(f"Saved PID {pid} {kind}: {path}", timeout=8)

    def action_show_diff(self) -> None:
        if self.busy:
            return
        if self.current_diff is None:
            self.notify("Capture the same PID and view twice to compare snapshots.")
            return
        pid, kind, _ = self.current_snapshot
        self.display(f"Snapshot diff: PID {pid} ({kind})", self.current_diff or "No text changes.")

    def action_open_profile(self) -> None:
        if self.last_profile is None:
            self.notify("Create a profile with F or G first.")
            return
        if not webbrowser.open(self.last_profile.as_uri()):
            self.notify(f"Open this file in a browser: {self.last_profile}", timeout=10)

    def refresh_process_list(self) -> None:
        """Fetch Python processes and update UI state."""

        processes = list_python_processes()
        table = self.query_one(ProcessTable)
        table.update_processes(processes)

        count = len(processes)
        noun = "process" if count == 1 else "processes"
        self.sub_title = f"{count} Python {noun} visible"

        if not count:
            self.notify(
                "No Python processes detected. Launch your target application and press R to refresh.",
                severity="warning",
                timeout=4,
            )
            output = self.query_one("#ps-output", Log)
            output.clear()
            self.query_one("#ps-title", Static).update("Awaiting selection")
