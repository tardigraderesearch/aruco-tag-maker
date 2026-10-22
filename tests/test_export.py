import importlib.util
import json

import cv2
import pytest

from aruco_tag_maker.exporter import existing_conflicts, export
from aruco_tag_maker.settings import Settings, ValidationError


def load_module(path):
    spec = importlib.util.spec_from_file_location("markers_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_layout_and_names(exported):
    folder, names, _ = exported
    for name in names:
        assert (folder / "stl" / f"{name}.stl").is_file()
        assert (folder / "stl" / "multi-material" / f"{name}_white.stl").is_file()
        assert (folder / "stl" / "multi-material" / f"{name}_black.stl").is_file()
        assert (folder / "png" / f"{name}.png").is_file()


def test_markers_json_round_trip(exported):
    folder, names, settings = exported
    data = json.loads((folder / "markers.json").read_text(encoding="utf-8"))
    assert data["dictionary"] == "DICT_4X4_100"
    assert data["tag_size_mm"] == 24.0
    assert data["tags"] == {name: {"id": 10 + i} for i, name in enumerate(names)}
    assert Settings.from_dict(data["settings"]) == settings


def test_markers_py_round_trip_and_detect(exported):
    folder, names, _ = exported
    markers = load_module(folder / "markers.py")
    assert markers.MARKERS == {name: 10 + i for i, name in enumerate(names)}
    assert markers.ID_TO_NAME[11] == "Right-Gripper"
    assert markers.DICTIONARY == "DICT_4X4_100"
    assert markers.TAG_SIZE_MM == 24.0
    image = cv2.imread(str(folder / "png" / "cam_7.png"))
    assert markers.detect(image) == ["cam_7"]
    (name, corners), = markers.detect(image, with_corners=True)
    assert name == "cam_7" and corners.shape == (4, 2)


def test_markers_py_ignores_foreign_ids(exported):
    folder, _, _ = exported
    markers = load_module(folder / "markers.py")
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_100)
    foreign = cv2.aruco.generateImageMarker(dictionary, 0, 200)
    foreign = cv2.copyMakeBorder(foreign, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    assert markers.detect(foreign) == []


def test_refuses_to_overwrite_without_permission(exported, tmp_path):
    folder, names, settings = exported
    assert existing_conflicts(names, folder)
    with pytest.raises(FileExistsError):
        export(names, settings, folder)
    assert {p.name for p in existing_conflicts(["fresh"], folder)} == {"markers.json", "markers.py"}


def test_overwrite_and_new_folder(tmp_path):
    target = tmp_path / "a" / "b"
    export(["one"], Settings(engrave_names=False), target)
    export(["one"], Settings(engrave_names=False), target, overwrite=True)
    assert (target / "stl" / "one.stl").is_file()


def test_invalid_names_write_nothing(tmp_path):
    with pytest.raises(ValidationError):
        export(["ok", "OK"], Settings(), tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_progress_reports_every_tag(tmp_path):
    seen = []
    export(["a", "b", "c"], Settings(), tmp_path, progress=lambda d, t, n: seen.append((d, t, n)))
    assert seen == [(0, 3, "a"), (1, 3, "b"), (2, 3, "c"), (3, 3, "done")]
