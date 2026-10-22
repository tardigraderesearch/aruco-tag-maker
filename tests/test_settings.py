import pytest

from aruco_tag_maker.settings import (
    DICTIONARIES,
    PAGE_SIZE,
    Settings,
    ValidationError,
    name_error,
    page_bounds,
    page_count,
    page_of,
    validate_count,
    validate_names,
)


@pytest.mark.parametrize("value, expected", [(1, 1), (99, 99), ("1", 1), (" 42 ", 42), (25.0, 25)])
def test_count_accepts_1_to_99(value, expected):
    assert validate_count(value) == expected


@pytest.mark.parametrize("value", [0, 100, -1, "0", "100", "", "abc", "2.5", 2.5, None, True, "1e2"])
def test_count_rejects_out_of_range_and_junk(value):
    with pytest.raises(ValidationError):
        validate_count(value)


@pytest.mark.parametrize("name", ["a", "A1", "left_gripper", "cam-03", "x" * 32, "9lives"])
def test_good_names(name):
    assert name_error(name) is None


@pytest.mark.parametrize(
    "name, fragment",
    [
        ("", "required"),
        ("   ", "required"),
        (None, "required"),
        (" pad", "spaces"),
        ("x" * 33, "at most"),
        ("has space", "letters"),
        ("a/b", "letters"),
        ("a\\b", "letters"),
        ("a:b", "letters"),
        ("what?", "letters"),
        ("star*", "letters"),
        ("dot.name", "letters"),
        ("_lead", "letters"),
        ("-lead", "letters"),
        ("ünïcode", "letters"),
        ("CON", "reserved"),
        ("nul", "reserved"),
        ("Com1", "reserved"),
        ("lpt9", "reserved"),
    ],
)
def test_bad_names(name, fragment):
    assert fragment in name_error(name)


def test_duplicates_are_case_insensitive_and_both_flagged():
    with pytest.raises(ValidationError) as info:
        validate_names(["arm", "leg", "ARM"])
    errors = info.value.details["names"]
    assert set(errors) == {"0", "2"}
    assert "duplicate of tag #1" in errors["2"]


def test_name_list_length_limits():
    with pytest.raises(ValidationError):
        validate_names([])
    with pytest.raises(ValidationError):
        validate_names([f"t{i}" for i in range(100)])
    assert len(validate_names([f"t{i}" for i in range(99)])) == 99


def test_ids_must_fit_dictionary():
    settings = Settings(start_id=95)
    with pytest.raises(ValidationError) as info:
        validate_names([f"t{i}" for i in range(10)], settings)
    assert "start_id" in info.value.details["settings"]


def test_engraving_fit_is_checked():
    tiny = Settings(tag_size_mm=6.0)
    with pytest.raises(ValidationError) as info:
        validate_names(["a_rather_long_name_for_tiny_tag"], tiny)
    assert "engrave" in info.value.details["names"]["0"]
    validate_names(["a_rather_long_name_for_tiny_tag"], Settings(tag_size_mm=6.0, engrave_names=False))


@pytest.mark.parametrize(
    "count, pages", [(0, 0), (1, 1), (19, 1), (20, 1), (21, 2), (40, 2), (41, 3), (99, 5)]
)
def test_page_count(count, pages):
    assert page_count(count) == pages


def test_page_bounds_cover_every_index_once():
    for count in (1, 20, 25, 99):
        seen = []
        for page in range(page_count(count)):
            start, end = page_bounds(page, count)
            assert 0 < end - start <= PAGE_SIZE
            seen.extend(range(start, end))
        assert seen == list(range(count))
    assert page_bounds(4, 99) == (80, 99)
    with pytest.raises(ValueError):
        page_bounds(5, 99)
    assert page_of(0) == 0 and page_of(19) == 0 and page_of(20) == 1 and page_of(98) == 4


def test_settings_defaults_and_derived_sizes():
    s = Settings()
    assert s.dictionary == "DICT_4X4_100"
    assert DICTIONARIES[s.dictionary][1] >= 100
    assert s.marker_size_mm == s.tag_size_mm == 30.0
    assert s.module_mm == pytest.approx(5.0)
    assert s.tile_size_mm == pytest.approx(40.0)


def test_settings_from_untrusted_input():
    s = Settings.from_dict({"tag_size_mm": "50", "quiet_zone_modules": "2", "engrave_names": "false",
                            "dictionary": "dict_5x5_250"})
    assert s.tag_size_mm == 50 and s.quiet_zone_modules == 2 and not s.engrave_names
    assert s.dictionary == "DICT_5X5_250"
    for bad in ({"tag_size_mm": 2}, {"tag_size_mm": 1000}, {"tag_size_mm": "nan"},
                {"dictionary": "DICT_4X4_50"}, {"quiet_zone_modules": 1.5}, {"bogus": 1},
                {"engrave_depth_mm": 1.9}, {"relief_mm": 0}):
        with pytest.raises(ValidationError):
            Settings.from_dict(bad)
