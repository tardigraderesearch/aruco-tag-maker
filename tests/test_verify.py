import shutil

import pytest

from aruco_tag_maker.verify import VerificationError, main, verify_folder


def test_verifier_passes_on_export(exported):
    folder, names, _ = exported
    assert verify_folder(folder, log=lambda _m: None) == len(names)
    assert main([str(folder)]) == 0


def test_verifier_catches_swapped_png(exported, tmp_path):
    folder, names, _ = exported
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy)
    shutil.copy(copy / "png" / f"{names[0]}.png", copy / "png" / f"{names[1]}.png")
    with pytest.raises(VerificationError, match="decodes to"):
        verify_folder(copy, log=lambda _m: None)


def test_verifier_catches_swapped_stl(exported, tmp_path):
    folder, names, _ = exported
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy)
    shutil.copy(copy / "stl" / f"{names[0]}.stl", copy / "stl" / f"{names[1]}.stl")
    with pytest.raises(VerificationError, match="marker face decodes"):
        verify_folder(copy, log=lambda _m: None)


def test_verifier_catches_truncated_mesh(exported, tmp_path):
    folder, names, _ = exported
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy)
    path = copy / "stl" / "multi-material" / f"{names[2]}_black.stl"
    data = bytearray(path.read_bytes())
    count = int.from_bytes(data[80:84], "little") - 1
    data[80:84] = count.to_bytes(4, "little")
    path.write_bytes(bytes(data[: 84 + 50 * count]))
    with pytest.raises(VerificationError, match="closed manifold"):
        verify_folder(copy, log=lambda _m: None)


def test_verifier_leaves_no_bytecode_behind(tmp_path):
    from aruco_tag_maker.exporter import export
    from aruco_tag_maker.settings import Settings

    folder = tmp_path / "fresh"
    export(["solo"], Settings(), folder)
    verify_folder(folder, log=lambda _m: None)
    assert not (folder / "__pycache__").exists()
