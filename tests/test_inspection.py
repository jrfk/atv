import asyncio
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

import psutil

from atv.inspection import Result, artifact_path, execute, profile_command
from atv.app import AtvApp, ProcessTable
from atv.processes import ProcessInfo
from textual.events import Key
from textual.widgets import Static


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
    async def test_waiting_wrapper_child_stops_on_timeout_and_cancel(self):
        for cancel in (False, True):
            with self.subTest(cancel=cancel), tempfile.TemporaryDirectory() as directory:
                pid_file = Path(directory) / "child-pid"
                wrapper = (
                    "import pathlib, subprocess, sys\n"
                    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                    "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                    "child.wait()\n"
                )
                task = asyncio.create_task(execute(
                    [sys.executable, "-c", wrapper, str(pid_file)], timeout=2))
                try:
                    async with asyncio.timeout(1):
                        while not pid_file.exists():
                            await asyncio.sleep(0.01)
                    child = psutil.Process(int(pid_file.read_text()))
                    if cancel:
                        task.cancel()
                    done, _ = await asyncio.wait({task}, timeout=3)
                    self.assertIn(task, done, "the wrapper child kept the pipe open")
                    with self.assertRaises(asyncio.CancelledError if cancel else TimeoutError):
                        task.result()
                    # An orphan may briefly remain a zombie until init reaps it.
                    self.assertTrue(not child.is_running() or child.status() == psutil.STATUS_ZOMBIE)
                finally:
                    if pid_file.exists():
                        try:
                            os.kill(int(pid_file.read_text()), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_failure_preserves_stdout_and_stderr(self):
        result = await execute([sys.executable, "-c",
            "import sys; print('permission denied'); print('details', file=sys.stderr); sys.exit(2)"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("permission denied", result.output)
        self.assertIn("details", result.output)

    async def test_timeout_reaps_observer(self):
        real_spawn = asyncio.create_subprocess_exec
        children = []

        async def spawn(*args, **kwargs):
            child = await real_spawn(*args, **kwargs)
            children.append(child)
            return child

        with patch("atv.inspection.asyncio.create_subprocess_exec", side_effect=spawn):
            with self.assertRaises(TimeoutError):
                await execute([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
        self.assertIsNotNone(children[0].returncode)

    async def test_cancel_reaps_observer(self):
        real_spawn = asyncio.create_subprocess_exec
        ready = asyncio.Event()
        children = []

        async def spawn(*args, **kwargs):
            child = await real_spawn(*args, **kwargs)
            children.append(child)
            ready.set()
            return child

        with patch("atv.inspection.asyncio.create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(execute([sys.executable, "-c", "import time; time.sleep(30)"]))
            await ready.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertIsNotNone(children[0].returncode)

    async def test_repeated_cancel_during_spawn_reaps_observer(self):
        real_spawn = asyncio.create_subprocess_exec
        ready = asyncio.Event()
        release = asyncio.Event()
        children = []

        async def spawn(*args, **kwargs):
            child = await real_spawn(*args, **kwargs)
            children.append(child)
            ready.set()
            await release.wait()
            return child

        with patch("atv.inspection.asyncio.create_subprocess_exec", side_effect=spawn):
            task = asyncio.create_task(execute([sys.executable, "-c", "import time; time.sleep(30)"]))
            try:
                await ready.wait()
                task.cancel()
                await asyncio.sleep(0)
                task.cancel()
                release.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertIsNotNone(children[0].returncode)
            finally:
                release.set()
                for child in children:
                    if child.returncode is None:
                        child.kill()
                await asyncio.gather(task, return_exceptions=True)

    @unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
    async def test_timeout_closes_pipe_held_by_child_after_wrapper_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "child-pid"
            wrapper = (
                "import pathlib, subprocess, sys\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
            )
            task = asyncio.create_task(execute([sys.executable, "-c", wrapper, str(pid_file)], timeout=1))
            try:
                done, _ = await asyncio.wait({task}, timeout=3)
                self.assertIn(task, done, "the observer's child kept the pipe open")
                with self.assertRaises(TimeoutError):
                    task.result()
                self.assertTrue(pid_file.is_file())
            finally:
                if not task.done() and pid_file.is_file():
                    try:
                        os.kill(int(pid_file.read_text()), signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await asyncio.gather(task, return_exceptions=True)


class UITests(unittest.IsolatedAsyncioTestCase):
    async def test_capture_diff_save_and_profile(self):
        rows = [ProcessInfo(123, "python", "python demo.py", "demo.py")]
        count = 0

        async def fake_execute(command, timeout=20):
            nonlocal count
            if "--help" in command:
                return Result(tuple(command), 0, "help")
            if "--flamegraph" in command:
                Path(command[command.index("-o") + 1]).write_text("<html>profile</html>")
                return Result(tuple(command), 0, "Captured samples")
            count += 1
            return Result(tuple(command), 0, f"task-{count}\n")

        with tempfile.TemporaryDirectory() as directory:
            app = AtvApp(output_dir=Path(directory))
            with (
                patch("atv.app.list_python_processes", return_value=rows),
                patch("atv.app.execute", side_effect=fake_execute),
                patch("atv.app.psutil.Process") as process,
            ):
                process.return_value.create_time.return_value = 100.0
                async with app.run_test(size=(140, 42)) as pilot:
                    app.query_one(ProcessTable).focus()
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertEqual(count, 1)
                    await pilot.press("p")
                    await pilot.pause()
                    self.assertIn("-task-1", app.current_diff)
                    await pilot.press("s")
                    self.assertEqual(len(list(Path(directory).glob("*.txt"))), 1)
                    process.return_value.create_time.return_value = 101.0
                    await pilot.press("p")
                    await pilot.pause()
                    self.assertEqual(app.current_snapshot, (123, "ps", "task-3\n"))
                    self.assertIsNone(app.current_diff)
                    await pilot.press("t")
                    await pilot.pause()
                    self.assertEqual(app.current_snapshot[1], "pstree")
                    self.assertIsNone(app.current_diff)
                    await pilot.press("f")
                    await pilot.pause()
                    self.assertTrue(app.last_profile.is_file())
                    with patch("atv.app.webbrowser.open", return_value=True) as browser:
                        await pilot.press("o")
                        browser.assert_called_once_with(app.last_profile.as_uri())
                    self.assertFalse(app.busy)

    async def test_queued_cancel_allows_another_capture(self):
        rows = [ProcessInfo(123, "python", "python demo.py", "demo.py")]
        app = AtvApp()
        attempts = 0

        async def fake_execute(command, timeout=20):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                await asyncio.Future()
            return Result(tuple(command), 0, "task\n")

        with patch("atv.app.list_python_processes", return_value=rows), patch("atv.app.execute", side_effect=fake_execute):
            async with app.run_test() as pilot:
                app.post_message(Key("p", "p"))
                app.post_message(Key("x", "x"))
                await pilot.pause()
                self.assertFalse(app.busy)
                self.assertIsNone(app.operation)
                await pilot.press("p")
                await pilot.pause()
                self.assertEqual(app.current_snapshot, (123, "ps", "task\n"))

    async def test_failed_inspection_does_not_replace_snapshot(self):
        rows = [ProcessInfo(123, "python", "python demo.py", "demo.py")]
        app = AtvApp()
        with patch("atv.app.list_python_processes", return_value=rows), patch("atv.app.execute", return_value=Result((), 1, "Permission denied")):
            async with app.run_test() as pilot:
                await pilot.press("p")
                await pilot.pause()
                self.assertIsNone(app.current_snapshot)
                self.assertFalse(app.busy)
                self.assertIn("failed", str(app.query_one("#ps-title", Static).render()))


class CommandTests(unittest.TestCase):
    def test_profile_is_bounded_attach_and_unique_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            first = artifact_path(Path(directory), 123, "all", "html")
            second = artifact_path(Path(directory), 123, "all", "html")
            self.assertNotEqual(first, second)
            cmd = profile_command("/python with spaces", 123, "all", 5, first)
            self.assertEqual(cmd[0], "/python with spaces")
            self.assertIn("attach", cmd)
            self.assertEqual(cmd[-1], "123")
            self.assertEqual(cmd[cmd.index("-d") + 1], "5")
            with self.assertRaises(ValueError):
                profile_command("python", 123, "all", 0, first)


if __name__ == "__main__":
    unittest.main()
