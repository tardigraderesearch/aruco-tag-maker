"""Read tag names for the scripting path (`aruco-tag-maker generate --names`)."""

from __future__ import annotations

from pathlib import Path


def read_names(path: Path | str) -> list[str]:
    """One name per line. Blank lines and lines starting with '#' are ignored."""
    text = Path(path).read_text(encoding="utf-8-sig")
    names = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            names.append(stripped)
    return names
