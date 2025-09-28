"""Command-line entry points for atv."""

from __future__ import annotations

from .app import AtvApp


def main() -> None:
    """Launch the Textual application."""

    AtvApp().run()


if __name__ == "__main__":
    main()
