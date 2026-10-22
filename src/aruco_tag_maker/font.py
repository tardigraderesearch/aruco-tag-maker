"""A tiny 5x7 pixel font for engraving tag names into the back of a tile.

Pixel fonts print cleanly with an FDM nozzle and turn into simple boxes, so
the engraving stays a robust boolean cut. Lower-case letters are engraved as
upper-case.
"""

from __future__ import annotations

from itertools import combinations
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .settings import Settings

GLYPH_W = 5
GLYPH_H = 7
LETTER_GAP = 1
LINE_GAP = 2
MAX_LINES = 3
MIN_PIXEL_MM = 0.4  # roughly one 0.4 mm nozzle line; smaller is not legible
MARGIN_FRACTION = 0.08

_GLYPHS: dict[str, tuple[str, ...]] = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": ("..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."),
    "-": (".....", ".....", ".....", "#####", ".....", ".....", "....."),
    "_": (".....", ".....", ".....", ".....", ".....", ".....", "#####"),
}


def glyph(char: str) -> np.ndarray:
    rows = _GLYPHS.get(char.upper())
    if rows is None:
        raise ValueError(f"no glyph for {char!r}")
    return np.array([[c == "#" for c in row] for row in rows], dtype=bool)


def split_lines(text: str, lines: int) -> list[str]:
    """Split into ``lines`` non-empty pieces with the shortest longest line,
    preferring breaks right after '-' or '_' (worth one character of width)."""
    if lines <= 1 or len(text) < lines:
        return [text]
    best: tuple[tuple[int, int, int], list[str]] | None = None
    for cuts in combinations(range(1, len(text)), lines - 1):
        bounds = (0, *cuts, len(text))
        pieces = [text[a:b] for a, b in zip(bounds, bounds[1:])]
        nice = sum(text[c - 1] in "-_" for c in cuts)
        longest = max(map(len, pieces))
        score = (longest - nice, -nice, longest)
        if best is None or score < best[0]:
            best = (score, pieces)
    return best[1]


def text_bitmap(lines: list[str]) -> np.ndarray:
    """Render lines (centered) into a bool bitmap; row 0 is the top row."""
    width = max(len(line) for line in lines) * (GLYPH_W + LETTER_GAP) - LETTER_GAP
    height = len(lines) * (GLYPH_H + LINE_GAP) - LINE_GAP
    bitmap = np.zeros((height, width), dtype=bool)
    for row_index, line in enumerate(lines):
        line_width = len(line) * (GLYPH_W + LETTER_GAP) - LETTER_GAP
        x = (width - line_width) // 2
        y = row_index * (GLYPH_H + LINE_GAP)
        for char in line:
            bitmap[y : y + GLYPH_H, x : x + GLYPH_W] |= glyph(char)
            x += GLYPH_W + LETTER_GAP
    return bitmap


@dataclass(frozen=True)
class EngraveLayout:
    lines: tuple[str, ...]
    pixel_mm: float
    bitmap: np.ndarray  # row 0 = top of the text as read

    @property
    def width_mm(self) -> float:
        return self.bitmap.shape[1] * self.pixel_mm

    @property
    def height_mm(self) -> float:
        return self.bitmap.shape[0] * self.pixel_mm


def engrave_layout(name: str, settings: "Settings") -> EngraveLayout | None:
    """Pick 1-3 lines and a pixel size that fit the tile back, or None if illegible."""
    if not name or any(c.upper() not in _GLYPHS for c in name):
        return None
    usable = settings.tile_size_mm * (1 - 2 * MARGIN_FRACTION)
    max_pixel = settings.tile_size_mm / 24.0
    best: EngraveLayout | None = None
    for count in range(1, MAX_LINES + 1):
        if count > len(name):
            break
        lines = split_lines(name, count)
        width_px = max(len(line) for line in lines) * (GLYPH_W + LETTER_GAP) - LETTER_GAP
        height_px = count * (GLYPH_H + LINE_GAP) - LINE_GAP
        pixel = min(usable / width_px, usable / height_px, max_pixel)
        if pixel + 1e-9 < MIN_PIXEL_MM:
            continue
        if best is None or pixel > best.pixel_mm + 1e-9:
            best = EngraveLayout(tuple(lines), pixel, text_bitmap(lines))
    return best
