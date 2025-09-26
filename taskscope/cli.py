"""Command-line entry points for TaskScope."""

from __future__ import annotations

from .app import TaskScopeApp


def main() -> None:
    """Launch the Textual application."""

    TaskScopeApp().run()


if __name__ == "__main__":
    main()
