"""Bounded subprocess execution and persistent inspection artifacts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import signal
import uuid


@dataclass(frozen=True)
class Result:
    command: tuple[str, ...]
    returncode: int
    output: str


async def execute(command: list[str], timeout: float = 20) -> Result:
    """Reap the observer on timeout/cancellation; never signal the target PID."""
    spawn = asyncio.create_task(asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        start_new_session=os.name == "posix",
    ))
    communication = None
    try:
        async with asyncio.timeout(timeout):
            process = await asyncio.shield(spawn)
            communication = asyncio.create_task(process.communicate())
            output, _ = await asyncio.shield(communication)
    except (TimeoutError, asyncio.CancelledError):
        cleanup = asyncio.create_task(stop_observer(spawn, communication))
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                # A second cancellation must not interrupt reaping the observer.
                continue
        cleanup.result()
        raise
    text = output.decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return Result(tuple(command), process.returncode, text)


async def stop_observer(
    spawn: asyncio.Task[asyncio.subprocess.Process],
    communication: asyncio.Task[tuple[bytes, bytes | None]] | None,
) -> None:
    try:
        process = await spawn
    except OSError:
        return
    try:
        if os.name == "posix":
            # Children may still own the output pipe after the wrapper exits.
            os.killpg(process.pid, signal.SIGKILL)
        elif process.returncode is None:
            process.kill()
    except ProcessLookupError:
        pass
    if communication is None:
        await process.communicate()
    else:
        await communication


def artifact_path(directory: Path, pid: int, kind: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return directory / f"{pid}-{kind}-{stamp}-{uuid.uuid4().hex[:8]}.{suffix}"


def profile_command(python: str, pid: int, mode: str, duration: int, output: Path) -> list[str]:
    if mode not in {"running", "all"}:
        raise ValueError("Async mode must be running or all.")
    if not 1 <= duration <= 300:
        raise ValueError("Duration must be between 1 and 300 seconds.")
    return [python, "-m", "profiling.sampling", "attach", "--async-aware",
            "--async-mode", mode, "-d", str(duration), "--flamegraph", "-o", str(output), str(pid)]
