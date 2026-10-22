import numpy as np

from aruco_tag_maker.font import MIN_PIXEL_MM, engrave_layout, glyph, text_bitmap
from aruco_tag_maker.settings import MAX_NAME_LENGTH, Settings


def test_every_allowed_character_has_a_glyph():
    for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_":
        assert glyph(char).shape == (7, 5)
        assert glyph(char).any()


def test_layout_fits_inside_tile():
    s = Settings()
    for name in ("a", "gripper", "x" * MAX_NAME_LENGTH):
        layout = engrave_layout(name, s)
        assert layout is not None
        assert layout.pixel_mm >= MIN_PIXEL_MM
        assert layout.width_mm < s.tile_size_mm and layout.height_mm < s.tile_size_mm


def test_default_tile_fits_the_longest_name():
    assert engrave_layout("W" * MAX_NAME_LENGTH, Settings()) is not None


def test_illegible_layout_is_rejected():
    assert engrave_layout("x" * 30, Settings(tag_size_mm=6)) is None


def test_bitmap_centres_lines():
    bitmap = text_bitmap(["AB", "C"])
    assert bitmap.shape == (16, 11)
    assert np.array_equal(bitmap[9:, 3:8], glyph("C"))


def test_line_breaks_prefer_separators():
    from aruco_tag_maker.font import split_lines

    assert split_lines("camera_mount", 2) == ["camera_", "mount"]
    assert split_lines("abcdef", 2) == ["abc", "def"]
    assert split_lines("ab", 3) == ["ab"]
    assert "".join(split_lines("x" * 32, 3)) == "x" * 32
