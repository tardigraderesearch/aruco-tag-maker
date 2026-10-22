"""ArUco marker bit patterns and raster images."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from .settings import DICTIONARIES, Settings


@lru_cache(maxsize=None)
def get_dictionary(name: str) -> "cv2.aruco.Dictionary":
    if name not in DICTIONARIES:
        raise ValueError(f"unsupported dictionary {name!r}")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


@lru_cache(maxsize=4096)
def _matrix_bytes(dictionary: str, marker_id: int) -> tuple[bytes, int]:
    bits = DICTIONARIES[dictionary][0]
    modules = bits + 2
    image = cv2.aruco.generateImageMarker(get_dictionary(dictionary), marker_id, modules)
    return (image < 128).tobytes(), modules


def marker_matrix(dictionary: str, marker_id: int) -> np.ndarray:
    """Bool matrix (row 0 = top) of the marker incl. its black border; True = black."""
    size = DICTIONARIES[dictionary][1]
    if not 0 <= marker_id < size:
        raise ValueError(f"id {marker_id} is outside {dictionary} (0..{size - 1})")
    data, modules = _matrix_bytes(dictionary, marker_id)
    return np.frombuffer(data, dtype=bool).reshape(modules, modules).copy()


def marker_image(
    dictionary: str, marker_id: int, quiet_zone_modules: int = 1, pixels_per_module: int = 40
) -> np.ndarray:
    """Grayscale uint8 image of the marker with a white quiet zone."""
    matrix = marker_matrix(dictionary, marker_id)
    q = quiet_zone_modules
    total = matrix.shape[0] + 2 * q
    canvas = np.full((total, total), 255, dtype=np.uint8)
    canvas[q : q + matrix.shape[0], q : q + matrix.shape[0]] = np.where(matrix, 0, 255)
    return np.repeat(np.repeat(canvas, pixels_per_module, axis=0), pixels_per_module, axis=1)


def write_png(path: Path, settings: Settings, marker_id: int, pixels_per_module: int = 100) -> None:
    image = marker_image(settings.dictionary, marker_id, settings.quiet_zone_modules, pixels_per_module)
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"failed to encode PNG for id {marker_id}")
    path.write_bytes(encoded.tobytes())


def detect_ids(image: np.ndarray, dictionary: str) -> list[int]:
    detector = cv2.aruco.ArucoDetector(get_dictionary(dictionary), cv2.aruco.DetectorParameters())
    _corners, ids, _rejected = detector.detectMarkers(image)
    return [] if ids is None else sorted(int(v) for v in ids.flatten())
