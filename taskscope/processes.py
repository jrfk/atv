"""Utilities for discovering asyncio-capable Python processes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import psutil


@dataclass(slots=True)
class ProcessInfo:
    """Lightweight descriptor for a running Python process."""

    pid: int
    name: str
    command_line: str
    file: str | None


def list_python_processes() -> List[ProcessInfo]:
    """Return visible Python processes that are likely asyncio-capable.

    We treat a process as "Python" if either its executable name or command
    line contains the token ``python``. Processes we cannot introspect (e.g.
    due to permissions) are skipped.
    """

    candidates: List[ProcessInfo] = []
    for proc in psutil.process_iter(attrs=["pid", "name", "cmdline"]):
        try:
            name = proc.info.get("name") or ""
            cmdline: Iterable[str] = proc.info.get("cmdline") or []
            cmdline_list: List[str] = list(cmdline)
            mark = "python" in name.lower() or any(
                "python" in part.lower() for part in cmdline_list
            )
            if not mark:
                continue

            command_line = " ".join(cmdline_list) if cmdline_list else name
            file = _detect_entrypoint(cmdline_list)
            candidates.append(
                ProcessInfo(
                    pid=proc.pid, name=name, command_line=command_line, file=file
                )
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue

    candidates.sort(key=lambda info: info.pid)
    return candidates


def _detect_entrypoint(cmdline: Sequence[str]) -> str | None:
    """Best-effort extraction of the target script/module name.

    Returns a basename for file paths, the module string for ``-m`` invocations,
    or ``None`` if nothing matches.
    """

    if not cmdline:
        return None

    remainder = list(cmdline)

    # If command begins with python executable, skip it.
    if remainder and "python" in os.path.basename(remainder[0]).lower():
        remainder = remainder[1:]

    i = 0
    while i < len(remainder):
        token = remainder[i]
        if token == "-m" and i + 1 < len(remainder):
            return remainder[i + 1]
        if token.startswith("-"):
            i += 1
            continue
        # Treat first non-option token as a potential script path.
        return os.path.basename(token)
    return None
