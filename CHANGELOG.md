# Changelog

## Unreleased

- One entry point: `python aruco_tag_maker.py` on every OS. It asks (Y/n) before
  installing its libraries into a private `.venv`, or says it's good to go and starts.
  `run.sh`, `run.bat`, `run.command` and `launcher.py` are gone. This also fixes
  `run.bat` failing on Windows because cmd mis-parsed inline Python.
- Tests: the GUI smoke test is skipped on hosted macOS CI runners, where Tk blocks
  forever inside `update()` (set `ARUCO_GUI_TESTS=1` to run it on a real Mac); it no
  longer opens the modal success dialog. Tests time out after 120 s and CI jobs after
  20 minutes.

## v0.1.0 (2026-10-22)

First release.

- Desktop app (tkinter): choose 1 to 99 tags and the tag size, name each tag next to
  its marker preview (20 per page), pick an export folder and generate.
- Inline validation: names are required, unique (case-insensitive) and safe as file
  names on Windows, macOS and Linux; out-of-range settings are flagged before export.
- Export folder: `stl/<name>.stl` (single-extruder, filament swap),
  `stl/multi-material/<name>_white.stl` + `<name>_black.stl`, `png/<name>.png`,
  `markers.json` and an importable `markers.py` with a `detect()` helper.
- Optional name engraved (mirrored) into the back of each tile; the marker face is
  never modified.
- Every export is verified: PNGs and a top-down re-render of each STL must decode to
  the right id, and every mesh must be a closed 2-manifold.
- Scripting path: `aruco-tag-maker generate --names names.txt`, plus `verify` and
  `doctor` commands.
- Zero-setup launchers for Linux, macOS and Windows (since replaced by
  `python aruco_tag_maker.py`).
- CI on Linux, Windows and macOS with Python 3.11 and 3.12.
