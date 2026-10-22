import json

from aruco_tag_maker.cli import main
from aruco_tag_maker.names_file import read_names


def test_read_names_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "names.txt"
    path.write_text("﻿# my tags\nalpha\n\n  beta  \n#gamma\n", encoding="utf-8")
    assert read_names(path) == ["alpha", "beta"]


def test_generate_command(tmp_path, capsys):
    names = tmp_path / "names.txt"
    names.write_text("arm\nleg\nhead\n", encoding="utf-8")
    out = tmp_path / "out"
    code = main(["generate", "--names", str(names), "--out", str(out), "--tag-size", "20",
                 "--dictionary", "DICT_5X5_100", "--start-id", "5"])
    assert code == 0
    data = json.loads((out / "markers.json").read_text())
    assert data["tags"] == {"arm": {"id": 5}, "leg": {"id": 6}, "head": {"id": 7}}
    assert "verified" in capsys.readouterr().out
    # second run without --overwrite refuses, with it succeeds
    assert main(["generate", "--names", str(names), "--out", str(out)]) == 2
    assert main(["generate", "--names", str(names), "--out", str(out), "--overwrite", "--no-verify"]) == 0


def test_generate_reports_bad_names(tmp_path, capsys):
    names = tmp_path / "names.txt"
    names.write_text("ok\nbad name\nOK\n", encoding="utf-8")
    assert main(["generate", "--names", str(names), "--out", str(tmp_path / "o")]) == 2
    err = capsys.readouterr().err
    assert "line 2" in err and "line 3" in err


def test_doctor_runs(capsys):
    assert main(["doctor"]) in (0, 1)
    assert "Python" in capsys.readouterr().out
