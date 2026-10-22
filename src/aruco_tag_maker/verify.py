"""Check an exported tag folder end to end.

For every tag: the PNG decodes to the right id, each STL is a closed
2-manifold with the expected bounding box, and the marker face of the
combined STL, re-rendered top-down from its triangles, decodes to the right id.
Also checks that markers.py imports and agrees with markers.json.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from .marker import detect_ids
from .mesh import is_closed_manifold, read_stl
from .settings import DICTIONARIES

PIXELS_PER_MM = 12


class VerificationError(AssertionError):
    pass


def render_marker_face(triangles: np.ndarray, tile_mm: float, ppm: float = PIXELS_PER_MM) -> np.ndarray:
    """Top-down render: faces on the highest plane are black, everything else white."""
    z_top = triangles[:, :, 2].max()
    normals = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    on_top = (np.abs(triangles[:, :, 2] - z_top).max(axis=1) < 1e-4) & (normals[:, 2] > 0)
    pad = int(round(2 * ppm))  # extra white border so the quiet zone is never clipped
    size = int(round(tile_mm * ppm)) + 2 * pad
    image = np.full((size, size), 255, dtype=np.uint8)
    for tri in triangles[on_top]:
        pts = np.stack([tri[:, 0] * ppm + pad, (tile_mm - tri[:, 1]) * ppm + pad], axis=1)
        cv2.fillPoly(image, [np.round(pts * 16).astype(np.int32)], 0, lineType=cv2.LINE_8, shift=4)
    return image


def load_markers_py(path: Path):
    spec = importlib.util.spec_from_file_location(f"_atm_markers_{abs(hash(path))}", path)
    if spec is None or spec.loader is None:
        raise VerificationError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True  # don't leave __pycache__ in the user's export folder
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def verify_folder(folder: Path | str, log=print) -> int:
    """Raise VerificationError on the first problem; return the number of tags checked."""
    folder = Path(folder)
    data = json.loads((folder / "markers.json").read_text(encoding="utf-8"))
    dictionary = data["dictionary"]
    _check(dictionary in DICTIONARIES, f"unknown dictionary {dictionary}")
    tags = {name: int(entry["id"]) for name, entry in data["tags"].items()}
    _check(len(set(tags.values())) == len(tags), "markers.json has duplicate ids")
    tile = float(data["tile_size_mm"])
    height = float(data["print"]["total_height_mm"])

    module = load_markers_py(folder / "markers.py")
    _check(module.MARKERS == tags, "markers.py MARKERS differs from markers.json")
    _check(module.ID_TO_NAME == {v: k for k, v in tags.items()}, "markers.py ID_TO_NAME is wrong")
    _check(module.DICTIONARY == dictionary, "markers.py DICTIONARY differs from markers.json")
    log(f"markers.json / markers.py agree: {len(tags)} tags in {dictionary}")

    expected = np.array([tile, tile, height])
    for name, marker_id in tags.items():
        png_path = folder / "png" / f"{name}.png"
        _check(png_path.is_file(), f"missing png/{name}.png")
        # imdecode instead of imread: imread cannot open non-ASCII paths on Windows
        png = cv2.imdecode(np.fromfile(png_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        _check(png is not None, f"png/{name}.png is not a readable image")
        found = detect_ids(png, dictionary)
        _check(found == [marker_id], f"png/{name}.png decodes to {found}, expected [{marker_id}]")

        combined = read_stl(folder / "stl" / f"{name}.stl")
        _check(is_closed_manifold(combined), f"stl/{name}.stl is not a closed manifold")
        lo, hi = combined.reshape(-1, 3).min(axis=0), combined.reshape(-1, 3).max(axis=0)
        _check(np.allclose(lo, 0, atol=1e-3), f"stl/{name}.stl does not start at the origin")
        _check(np.allclose(hi - lo, expected, atol=1e-3), f"stl/{name}.stl is {hi - lo}, expected {expected}")
        face = render_marker_face(combined, tile)
        found = detect_ids(face, dictionary)
        _check(found == [marker_id], f"stl/{name}.stl marker face decodes to {found}, expected [{marker_id}]")

        for part in ("white", "black"):
            tris = read_stl(folder / "stl" / "multi-material" / f"{name}_{part}.stl")
            _check(is_closed_manifold(tris), f"{name}_{part}.stl is not a closed manifold")
    log(f"all {len(tags)} tags verified: PNG + STL marker face decode to the right ids, meshes closed")
    return len(tags)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: aruco-tag-maker verify FOLDER", file=sys.stderr)
        return 2
    try:
        verify_folder(Path(argv[0]))
    except (VerificationError, FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        print(f"verification FAILED: {exc}", file=sys.stderr)
        return 1
    return 0
