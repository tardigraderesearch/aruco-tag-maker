"""Settings, limits and input validation shared by the UI, the CLI and the tests."""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, fields
from typing import Any

MIN_TAGS = 1
MAX_TAGS = 99
PAGE_SIZE = 20
MAX_NAME_LENGTH = 32
MIN_TAG_MM = 5.0
MAX_TAG_MM = 300.0

# name -> (bits per side, number of ids). Only dictionaries with >= 100 ids are
# offered, so every count the UI accepts (1..99) fits in every dictionary.
DICTIONARIES: dict[str, tuple[int, int]] = {
    "DICT_4X4_100": (4, 100),
    "DICT_4X4_250": (4, 250),
    "DICT_4X4_1000": (4, 1000),
    "DICT_5X5_100": (5, 100),
    "DICT_5X5_250": (5, 250),
    "DICT_5X5_1000": (5, 1000),
    "DICT_6X6_100": (6, 100),
    "DICT_6X6_250": (6, 250),
    "DICT_6X6_1000": (6, 1000),
    "DICT_7X7_100": (7, 100),
    "DICT_7X7_250": (7, 250),
    "DICT_7X7_1000": (7, 1000),
    "DICT_ARUCO_ORIGINAL": (5, 1024),
}
DEFAULT_DICTIONARY = "DICT_4X4_100"

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class ValidationError(ValueError):
    """Raised with a human-readable message and optional per-field details."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


@dataclass(frozen=True)
class Settings:
    dictionary: str = DEFAULT_DICTIONARY
    start_id: int = 0
    tag_size_mm: float = 30.0
    quiet_zone_modules: int = 1
    base_thickness_mm: float = 2.0
    relief_mm: float = 0.4
    engrave_names: bool = True
    engrave_depth_mm: float = 0.4

    # ---- derived geometry -------------------------------------------------
    @property
    def bits(self) -> int:
        return DICTIONARIES[self.dictionary][0]

    @property
    def dictionary_size(self) -> int:
        return DICTIONARIES[self.dictionary][1]

    @property
    def marker_modules(self) -> int:
        """Modules across the marker itself: data bits plus the black border."""
        return self.bits + 2

    @property
    def total_modules(self) -> int:
        return self.marker_modules + 2 * self.quiet_zone_modules

    @property
    def module_mm(self) -> float:
        return self.tag_size_mm / self.marker_modules

    @property
    def marker_size_mm(self) -> float:
        """Side of the black square (== tag_size_mm). Use this for pose estimation."""
        return self.tag_size_mm

    @property
    def tile_size_mm(self) -> float:
        """Outer printed tile: the black square plus the white quiet zone."""
        return self.module_mm * self.total_modules

    @property
    def quiet_zone_mm(self) -> float:
        return self.module_mm * self.quiet_zone_modules

    @property
    def total_height_mm(self) -> float:
        return self.base_thickness_mm + self.relief_mm

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Settings":
        """Build validated settings from untrusted input (JSON body or CLI)."""
        data = dict(data or {})
        known = {f.name: f for f in fields(cls)}
        unknown = sorted(set(data) - set(known))
        if unknown:
            raise ValidationError(f"unknown setting(s): {', '.join(unknown)}")
        errors: dict[str, str] = {}
        values: dict[str, Any] = {}
        defaults = cls()
        for name in known:
            raw = data.get(name, getattr(defaults, name))
            try:
                values[name] = _coerce(name, raw)
            except ValueError as exc:
                errors[name] = str(exc)
        if errors:
            raise ValidationError("invalid settings", {"settings": errors})
        settings = cls(**values)
        settings.check()
        return settings

    def check(self) -> None:
        errors: dict[str, str] = {}
        if self.dictionary not in DICTIONARIES:
            errors["dictionary"] = f"unsupported dictionary {self.dictionary!r}"
        if not MIN_TAG_MM <= self.tag_size_mm <= MAX_TAG_MM:
            errors["tag_size_mm"] = f"tag size must be between {MIN_TAG_MM:g} and {MAX_TAG_MM:g} mm"
        if not 1 <= self.quiet_zone_modules <= 4:
            errors["quiet_zone_modules"] = "quiet zone must be 1 to 4 modules"
        if not 0.6 <= self.base_thickness_mm <= 20.0:
            errors["base_thickness_mm"] = "base thickness must be between 0.6 and 20 mm"
        if not 0.1 <= self.relief_mm <= 5.0:
            errors["relief_mm"] = "relief height must be between 0.1 and 5 mm"
        if not 0.1 <= self.engrave_depth_mm <= 5.0:
            errors["engrave_depth_mm"] = "engrave depth must be between 0.1 and 5 mm"
        elif self.engrave_names and self.engrave_depth_mm > self.base_thickness_mm - 0.4:
            errors["engrave_depth_mm"] = (
                "engrave depth must leave at least 0.4 mm of base under the marker"
            )
        if self.start_id < 0:
            errors["start_id"] = "start id must be 0 or more"
        if errors:
            raise ValidationError("invalid settings", {"settings": errors})


def _coerce(name: str, raw: Any) -> Any:
    if name == "dictionary":
        if not isinstance(raw, str):
            raise ValueError("must be a dictionary name")
        return raw.strip().upper()
    if name == "engrave_names":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.lower() in {"true", "1", "yes", "on"}:
            return True
        if isinstance(raw, str) and raw.lower() in {"false", "0", "no", "off", ""}:
            return False
        raise ValueError("must be true or false")
    if name in {"start_id", "quiet_zone_modules"}:
        if isinstance(raw, bool):
            raise ValueError("must be a whole number")
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise ValueError("must be a whole number") from None
        if not math.isfinite(value) or value != int(value):
            raise ValueError("must be a whole number")
        return int(value)
    if isinstance(raw, bool):
        raise ValueError("must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError("must be a number") from None
    if not math.isfinite(value):
        raise ValueError("must be a finite number")
    return value


# ---- tag count ------------------------------------------------------------
def validate_count(raw: Any) -> int:
    """Parse the "how many tags" field. Accepts 1..99 whole numbers only."""
    if isinstance(raw, bool):
        raise ValidationError("enter a whole number from 1 to 99")
    if isinstance(raw, str):
        raw = raw.strip()
        if not re.fullmatch(r"\d+", raw):
            raise ValidationError("enter a whole number from 1 to 99")
        raw = int(raw)
    if isinstance(raw, float):
        if not raw.is_integer():
            raise ValidationError("enter a whole number from 1 to 99")
        raw = int(raw)
    if not isinstance(raw, int):
        raise ValidationError("enter a whole number from 1 to 99")
    if not MIN_TAGS <= raw <= MAX_TAGS:
        raise ValidationError(f"number of tags must be between {MIN_TAGS} and {MAX_TAGS}")
    return raw


# ---- names ----------------------------------------------------------------
def name_error(name: Any) -> str | None:
    """Return why a single name is unusable, or None if it is fine on its own."""
    if not isinstance(name, str) or not name.strip():
        return "name is required"
    if name != name.strip():
        return "remove leading/trailing spaces"
    if len(name) > MAX_NAME_LENGTH:
        return f"at most {MAX_NAME_LENGTH} characters"
    if not _NAME_RE.match(name):
        return "use letters, digits, - and _ only (start with a letter or digit)"
    if name.upper() in _WINDOWS_RESERVED:
        return "reserved file name on Windows"
    return None


def validate_names(names: Any, settings: Settings | None = None) -> list[str]:
    """Validate a full list of names.

    Raises ValidationError whose details["names"] maps list index -> message.
    Duplicates are compared case-insensitively because macOS and Windows file
    systems are case-insensitive and the names become file names.
    """
    if not isinstance(names, list):
        raise ValidationError("names must be a list")
    count = validate_count(len(names))
    errors: dict[int, str] = {}
    first_seen: dict[str, int] = {}
    for index, name in enumerate(names):
        problem = name_error(name)
        if problem:
            errors[index] = problem
            continue
        key = name.lower()
        if key in first_seen:
            errors[index] = f"duplicate of tag #{first_seen[key] + 1}"
            errors.setdefault(first_seen[key], "duplicate name")
        else:
            first_seen[key] = index
    if settings is not None:
        if settings.start_id + count > settings.dictionary_size:
            raise ValidationError(
                f"{settings.dictionary} has {settings.dictionary_size} ids; "
                f"start id {settings.start_id} + {count} tags does not fit",
                {"settings": {"start_id": "too high for this many tags"}},
            )
        if settings.engrave_names:
            from .font import engrave_layout  # local import keeps this module light

            for index, name in enumerate(names):
                if index in errors:
                    continue
                if engrave_layout(name, settings) is None:
                    errors[index] = (
                        "too long to engrave legibly at this tile size "
                        "(shorten it, enlarge the tile, or turn engraving off)"
                    )
    if errors:
        raise ValidationError(
            f"{len(errors)} name(s) need attention", {"names": {str(k): v for k, v in sorted(errors.items())}}
        )
    return list(names)


# ---- pagination -----------------------------------------------------------
def page_count(count: int, page_size: int = PAGE_SIZE) -> int:
    if count <= 0:
        return 0
    return (count + page_size - 1) // page_size


def page_bounds(page: int, count: int, page_size: int = PAGE_SIZE) -> tuple[int, int]:
    """Half-open [start, end) indices for a 0-based page number."""
    pages = page_count(count, page_size)
    if not 0 <= page < max(pages, 1):
        raise ValueError(f"page {page} out of range for {pages} page(s)")
    start = page * page_size
    return start, min(start + page_size, count)


def page_of(index: int, page_size: int = PAGE_SIZE) -> int:
    return index // page_size
