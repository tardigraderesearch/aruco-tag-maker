import pytest

from aruco_tag_maker.exporter import export
from aruco_tag_maker.settings import Settings


@pytest.fixture(scope="session")
def exported(tmp_path_factory):
    """A small exported set shared by several tests (export is the slow part)."""
    folder = tmp_path_factory.mktemp("tags")
    names = ["left_gripper", "Right-Gripper", "base", "cam_7"]
    settings = Settings(tag_size_mm=24.0, start_id=10)
    export(names, settings, folder)
    return folder, names, settings
