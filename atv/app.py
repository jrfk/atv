"""Textual application scaffolding for atv."""

from __future__ import annotations

import asyncio
import sys
from typing import Iterable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Footer, Header, Log, Static

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
    SUB_TITLE = "Asyncio process discovery (alpha)"

    BINDINGS = [
        Binding("r", "refresh_processes", "Refresh", priority=True),
        Binding("enter", "inspect_selected", "Inspect"),
        Binding("p", "inspect_selected", "Inspect"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Container(
                Static(
                    "Select a Python process to inspect. Press R to refresh. \n"
                    "Press Enter to capture `python -m asyncio ps <pid>`.",
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
        """Run ``python -m asyncio ps`` for the highlighted process."""

        table = self.query_one(ProcessTable)
        pid = table.get_selected_pid()
        if pid is None:
            self.notify("Select a Python process first.", severity="warning", timeout=3)
            return

        header = self.query_one("#ps-title", Static)
        header.update(f"Running asyncio ps for PID {pid}…")
        log = self.query_one("#ps-output", Log)
        log.clear()
        log.write("Awaiting asyncio ps output…")

        self.run_worker(
            self.capture_asyncio_ps(pid),
            exclusive=True,
            description=f"Inspecting PID {pid}",
            name=f"ps-{pid}",
        )

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

    async def capture_asyncio_ps(self, pid: int) -> None:
        """Execute ``python -m asyncio ps`` for *pid* and stream the results."""

        cmd = [sys.executable, "-m", "asyncio", "ps", str(pid)]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            self._display_ps_failure(pid, "Failed to locate python executable to launch asyncio ps.")
            return

        stdout_bytes, stderr_bytes = await process.communicate()
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        self.log.debug(
            "asyncio ps completed",
            pid=pid,
            returncode=process.returncode,
            stdout_preview=stdout_text[:200],
            stderr_preview=stderr_text[:200],
        )

        if process.returncode != 0:
            message = stderr_text or "asyncio ps exited with a non-zero status."
            self._display_ps_failure(pid, message.strip())
            return

        self._display_ps_success(pid, stdout_text, stderr_text)

    def _display_ps_success(self, pid: int, stdout_text: str, stderr_text: str) -> None:
        header = self.query_one("#ps-title", Static)
        header.update(f"asyncio ps output for PID {pid}")
        log = self.query_one("#ps-output", Log)
        log.clear()
        lines: list[str] = [f"$ {sys.executable} -m asyncio ps {pid}"]

        if stdout_text.strip():
            lines.append("-- stdout --")
            lines.extend(stdout_text.splitlines())
        else:
            lines.append("(stdout was empty)")

        if stderr_text.strip():
            lines.append("")
            lines.append("-- stderr --")
            lines.extend(stderr_text.splitlines())

        log.write_lines(lines)

    def _display_ps_failure(self, pid: int, message: str) -> None:
        header = self.query_one("#ps-title", Static)
        header.update(f"Failed to capture asyncio ps for PID {pid}")
        log = self.query_one("#ps-output", Log)
        log.clear()
        log.write_lines([
            f"$ {sys.executable} -m asyncio ps {pid}",
            "-- error --",
            message or "asyncio ps failed with an unknown error.",
        ])
