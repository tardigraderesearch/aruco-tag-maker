"""Printable two-colour tile geometry.

Coordinates are millimetres. The tile sits on the print bed (z = 0) with the
marker face up. Layout:

* white base:   full tile, z = 0 .. base_thickness
* black relief: the marker's black modules, z = base_thickness .. +relief
* name (opt.):  engraved into the *bottom* face, mirrored so it reads correctly
                when the tile is turned over. The marker face is never touched.

Black modules that only touch diagonally are pulled apart by 1 micron
(the same trick the original aruco-maker CLI used), so every STL is a clean
2-manifold that slicers and ``trimesh.is_watertight`` accept.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import manifold3d as m3d
import numpy as np

from .font import engrave_layout
from .marker import marker_matrix
from .settings import Settings

CLEARANCE_MM = 0.001

Rect = tuple[float, float, float, float]  # x0, x1, y0, y1


def bitmap_rects(bitmap: np.ndarray, x_left: float, y_top: float, cell: float) -> list[Rect]:
    """One rectangle per True cell (row 0 = top), shrunk on sides with no neighbour."""
    rows, cols = bitmap.shape
    rects: list[Rect] = []
    for r in range(rows):
        for c in range(cols):
            if not bitmap[r, c]:
                continue
            left = c > 0 and bitmap[r, c - 1]
            right = c < cols - 1 and bitmap[r, c + 1]
            up = r > 0 and bitmap[r - 1, c]
            down = r < rows - 1 and bitmap[r + 1, c]
            x0 = x_left + c * cell + (0.0 if left else CLEARANCE_MM)
            x1 = x_left + (c + 1) * cell - (0.0 if right else CLEARANCE_MM)
            y1 = y_top - r * cell - (0.0 if up else CLEARANCE_MM)
            y0 = y_top - (r + 1) * cell + (0.0 if down else CLEARANCE_MM)
            rects.append((x0, x1, y0, y1))
    return rects


def _boxes(rects: list[Rect], z0: float, z1: float) -> m3d.Manifold:
    parts = [
        m3d.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])
        for x0, x1, y0, y1 in rects
    ]
    if not parts:
        return m3d.Manifold()
    return m3d.Manifold.batch_boolean(parts, m3d.OpType.Add)


@dataclass
class TileMeshes:
    combined: m3d.Manifold  # single-extruder print with a filament swap
    white: m3d.Manifold  # multi-material: base body
    black: m3d.Manifold  # multi-material: raised marker pattern


def build_tile(settings: Settings, marker_id: int, name: str | None = None) -> TileMeshes:
    tile = settings.tile_size_mm
    cell = settings.module_mm
    base = settings.base_thickness_mm
    top = settings.total_height_mm
    q = settings.quiet_zone_modules

    matrix = marker_matrix(settings.dictionary, marker_id)
    black_rects = bitmap_rects(matrix, x_left=q * cell, y_top=tile - q * cell, cell=cell)
    black = _boxes(black_rects, base, top)

    white = m3d.Manifold.cube([tile, tile, base])
    if settings.engrave_names and name:
        layout = engrave_layout(name, settings)
        if layout is None:
            raise ValueError(f"name {name!r} does not fit on the back of a {tile:g} mm tile")
        # Mirror left-right: the text is read from underneath.
        bitmap = np.fliplr(layout.bitmap)
        x_left = (tile - layout.width_mm) / 2
        y_top = (tile + layout.height_mm) / 2
        cut_rects = bitmap_rects(bitmap, x_left, y_top, layout.pixel_mm)
        white = white - _boxes(cut_rects, -1.0, settings.engrave_depth_mm)

    combined = white + black
    for label, body in (("combined", combined), ("white", white), ("black", black)):
        if body.status() != m3d.Error.NoError:
            raise RuntimeError(f"{label} mesh for id {marker_id} failed: {body.status()}")
    return TileMeshes(combined=combined, white=white, black=black)


def mesh_arrays(body: m3d.Manifold) -> tuple[np.ndarray, np.ndarray]:
    mesh = body.to_mesh()
    vertices = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    faces = np.asarray(mesh.tri_verts, dtype=np.int64)
    return vertices, faces


def stl_bytes(body: m3d.Manifold, label: str = "aruco-tag-maker") -> bytes:
    """Binary STL bytes for a manifold."""
    vertices, faces = mesh_arrays(body)
    tris = vertices[faces].astype(np.float32)  # (n, 3, 3)
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    record = np.zeros(
        len(faces),
        dtype=[("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")],
    )
    record["normal"] = normals
    record["v"] = tris
    header = label.encode("ascii", "replace")[:80].ljust(80, b" ")
    return header + struct.pack("<I", len(faces)) + record.tobytes()


def write_stl(path: Path, body: m3d.Manifold, label: str) -> None:
    path.write_bytes(stl_bytes(body, label))


def read_stl(path: Path) -> np.ndarray:
    """Read a binary STL written by this tool; returns triangles (n, 3, 3)."""
    data = path.read_bytes()
    (count,) = struct.unpack_from("<I", data, 80)
    record = np.frombuffer(
        data,
        dtype=[("normal", "<f4", 3), ("v", "<f4", (3, 3)), ("attr", "<u2")],
        count=count,
        offset=84,
    )
    return record["v"].astype(np.float64)


def is_closed_manifold(triangles: np.ndarray, decimals: int = 5) -> bool:
    """Every undirected edge is used by exactly two triangles, once per direction."""
    if len(triangles) == 0:
        return False
    points = np.round(triangles.reshape(-1, 3), decimals)
    _, index = np.unique(points, axis=0, return_inverse=True)
    faces = index.reshape(-1, 3)
    directed = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    if len({tuple(e) for e in directed.tolist()}) != len(directed):
        return False  # some directed edge repeats -> inconsistent winding / non-manifold
    undirected = np.sort(directed, axis=1)
    _, counts = np.unique(undirected, axis=0, return_counts=True)
    return bool(np.all(counts == 2))
