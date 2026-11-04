"""Bounded subprocess execution and persistent inspection artifacts."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import re
import uuid


@dataclass(frozen=True)
class Result:
    command: tuple[str, ...]
    returncode: int
    output: str


async def execute(command: list[str], timeout: float = 20) -> Result:
    """Reap the observer on timeout/cancellation; never signal the target PID."""
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
    )
    communication = asyncio.create_task(process.communicate())
    try:
        output, _ = await asyncio.wait_for(asyncio.shield(communication), timeout)
    except (TimeoutError, asyncio.CancelledError):
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await communication
        raise
    text = output.decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return Result(tuple(command), process.returncode, text)


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
