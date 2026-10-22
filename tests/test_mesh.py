import numpy as np
import pytest
import trimesh

from aruco_tag_maker.mesh import build_tile, is_closed_manifold, mesh_arrays, read_stl, write_stl
from aruco_tag_maker.settings import Settings
from aruco_tag_maker.verify import render_marker_face
from aruco_tag_maker.marker import detect_ids


def to_trimesh(body):
    v, f = mesh_arrays(body)
    return trimesh.Trimesh(v, f, process=True)


@pytest.mark.parametrize("dictionary", ["DICT_4X4_100", "DICT_5X5_100", "DICT_6X6_250", "DICT_7X7_100"])
@pytest.mark.parametrize("engrave", [True, False])
def test_tiles_are_watertight_with_expected_bounds(dictionary, engrave):
    s = Settings(dictionary=dictionary, tag_size_mm=30, engrave_names=engrave)
    for marker_id in (0, 1, 37, 99):
        tile = build_tile(s, marker_id, "Gripper_07")
        combined = to_trimesh(tile.combined)
        assert combined.is_watertight and combined.is_winding_consistent and combined.volume > 0
        assert np.allclose(combined.bounds, [[0, 0, 0], [s.tile_size_mm, s.tile_size_mm, s.total_height_mm]],
                           atol=1e-4)
        white, black = to_trimesh(tile.white), to_trimesh(tile.black)
        assert white.is_watertight and black.is_watertight
        assert white.bounds[1][2] == pytest.approx(s.base_thickness_mm)
        assert black.bounds[0][2] == pytest.approx(s.base_thickness_mm)
        assert black.bounds[1][2] == pytest.approx(s.total_height_mm)
        # two parts together are the combined print
        assert white.volume + black.volume == pytest.approx(combined.volume, rel=1e-6)


def test_engraving_is_on_the_back_only():
    s = Settings()
    plain = build_tile(s, 3, None)
    named = build_tile(s, 3, "WWWW")
    assert named.combined.volume() < plain.combined.volume()  # material was removed
    removed = plain.white - named.white
    lo, hi = removed.bounding_box()[:3], removed.bounding_box()[3:]
    assert lo[2] == pytest.approx(0, abs=1e-6)
    assert hi[2] == pytest.approx(s.engrave_depth_mm)
    assert named.black.volume() == pytest.approx(plain.black.volume())


def test_binary_stl_round_trip_and_marker_face_decodes(tmp_path):
    s = Settings(tag_size_mm=20)
    tile = build_tile(s, 42, "abc")
    path = tmp_path / "t.stl"
    write_stl(path, tile.combined, "t")
    tris = read_stl(path)
    assert is_closed_manifold(tris)
    assert detect_ids(render_marker_face(tris, s.tile_size_mm), s.dictionary) == [42]


def test_closed_manifold_check_catches_holes():
    s = Settings()
    tris = mesh_arrays(build_tile(s, 0).combined)
    v, f = tris
    assert is_closed_manifold(v[f])
    assert not is_closed_manifold(v[f][:-1])
