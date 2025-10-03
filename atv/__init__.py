"""atv package metadata."""

from __future__ import annotations

from importlib import metadata

__all__ = ["__version__"]

try:
    from .__about__ import __version__
except ImportError:  # pragma: no cover - fallback for editable installs without version file
    __version__ = metadata.version("atv")
