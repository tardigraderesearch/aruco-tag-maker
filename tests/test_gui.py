"""Smoke test: build the real window, drive it, export. Skipped without a display."""

import os
import sys

import pytest

tk = pytest.importorskip("tkinter")


@pytest.fixture
def app():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("no X display (run under xvfb-run)")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk cannot open a window here: {exc}")
    root.withdraw()
    from aruco_tag_maker.gui import TagMakerApp

    application = TagMakerApp(root)
    # The real success dialog grabs input on a withdrawn root, which can block
    # the event loop on macOS; record the call instead.
    application.success_calls = []
    application._success_dialog = lambda folder, count: application.success_calls.append(count)
    yield application
    root.destroy()


def test_count_pagination_and_validation(app):
    app.count_var.set("25")
    app.root.update()
    assert len(app.names) == 25 and app.pages == 2
    assert app.page_label.get() == "Page 1 of 2"
    app.go_page(1)
    visible = [w for w in app.row_widgets if w["frame"].winfo_manager()]
    assert len(visible) == 5
    app.count_var.set("100")
    assert app.count_error.get() and len(app.names) == 25
    app.count_var.set("25")
    assert app.validate_all() is None  # names are empty
    assert app.page == 0  # jumped to first page with errors
    assert "required" in app.row_widgets[0]["error"].cget("text")


def test_fill_names_and_export(app, tmp_path):
    app.count_var.set("3")
    app.row_widgets[0]["var"].set("left")
    app.row_widgets[1]["var"].set("LEFT")
    assert "duplicate" in app.row_widgets[1]["error"].cget("text")
    app.row_widgets[1]["var"].set("right")
    app.fill_empty()
    assert app.names == ["left", "right", "tag_03"]
    app.folder_var.set(str(tmp_path / "out"))
    app.generate()
    for _ in range(600):
        app.root.update()
        if not app.busy:
            break
        app.root.after(20)
    assert not app.busy
    assert (tmp_path / "out" / "stl" / "tag_03.stl").is_file()
    assert "verified" in app.status.get()
    assert app.success_calls == [3]
