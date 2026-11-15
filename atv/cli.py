"""Command-line entry points for atv."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

from .app import AtvApp


def main() -> None:
    """Launch the Textual application."""

    parser = argparse.ArgumentParser(description="Explore asyncio tasks and capture Tachyon profiles.")
    parser.add_argument("--python", default=sys.executable,
                        help="Observer Python executable; match the target version/build")
    parser.add_argument("--duration", type=int, default=10, help="Profile duration in seconds (1–300)")
    parser.add_argument("--output-dir", type=Path, default=None,
                        help="Capture directory (default: ~/.atv/captures)")
    args = parser.parse_args()
    if not 1 <= args.duration <= 300:
        parser.error("--duration must be between 1 and 300")
    python = shutil.which(args.python)
    if python is None:
        parser.error(f"Python executable not found: {args.python}")
    AtvApp(python=python, duration=args.duration, output_dir=args.output_dir).run()


if __name__ == "__main__":
    main()
