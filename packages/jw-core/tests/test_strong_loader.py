"""Tests for the Strong's dump loader (Gap 7)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jw_core.study.originals import (
    catalog_size,
    get_strong_entry,
    load_strong_dir,
    load_strong_json,
)

OPENSCRIPTURES_FRAGMENT = {
    "H7225": {
        "lemma": "רֵאשִׁית",
        "translit": "reshith",
        "strongs_def": "the first, in place, time, order or rank",
        "kjv_def": "beginning, chief, choice part, first, firstfruits, principal thing",
    },
    "H8064": {
        "lemma": "שָׁמַיִם",
        "translit": "shamayim",
        "strongs_def": "the sky (as aloft)",
        "kjv_def": "air, heaven, heavens",
    },
}


def test_load_openscriptures_format() -> None:
    base_count = catalog_size()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "hebrew.json"
        path.write_text(json.dumps(OPENSCRIPTURES_FRAGMENT))
        loaded = load_strong_json(path)
    assert loaded == 2
    entry = get_strong_entry("H7225")
    assert entry is not None and entry.transliteration == "reshith"
    assert "beginning" in (entry.glosses.get("en") or [])[0]
    assert catalog_size() == base_count + 2


def test_load_internal_list_format() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "compact.json"
        path.write_text(
            json.dumps(
                [
                    {
                        "strong_number": "G0001",
                        "transliteration": "alpha",
                        "original": "Α",
                        "glosses": {"en": ["alpha"], "es": ["alfa"]},
                    }
                ]
            )
        )
        loaded = load_strong_json(path)
    assert loaded == 1
    entry = get_strong_entry("G0001")
    assert entry is not None and "alfa" in entry.gloss_for("es")


def test_load_strong_dir_skips_bad_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dir_p = Path(tmp)
        (dir_p / "ok.json").write_text(json.dumps(OPENSCRIPTURES_FRAGMENT))
        (dir_p / "broken.json").write_text("not-valid-json{")
        loaded = load_strong_dir(dir_p)
    assert loaded == 2  # ok.json loaded, broken.json swallowed
