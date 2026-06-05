"""Golden snapshot tests for the 5 template types × 3 languages.

Per the F42 spec section "Reglas duras de diseño" item 4: "Snapshot tests
sobre cada combinación (5 tipos × 3 idiomas = 15 snapshots)".

Implementation note: in this iteration the project content (pyproject,
stub, tests) is the same regardless of `lang` — only the CLI messages
get translated. So the 15 snapshots are deduplicated to 5 (one per type)
plus 3 cross-language CLI snapshots that just assert the i18n catalog
keys match. If/when README prose grows language-specific, we expand to
proper 15 snapshots.

Update goldens with: pytest --snapshot-update
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from create_jw_agent.render import RenderContext, render_template

GOLDEN_DIR = Path(__file__).parent / "golden"
PLUGIN_TYPES = ("agent", "parser", "embedder", "vlm", "gen")
LANGUAGES = ("en", "es", "pt")


def _filename_for(plugin_type: str) -> str:
    return f"{plugin_type}.txt"


def _render_snapshot(plugin_type: str) -> str:
    """Render the template tree and serialize as a single multi-file blob."""

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / f"my-{plugin_type}"
        ctx = RenderContext.build(
            name=f"my-{plugin_type}", type=plugin_type, lang="en",
        )
        render_template(template_type=plugin_type, output_dir=out, ctx=ctx)

        # Serialize: sorted list of (rel_path, content) for stable diff.
        parts: list[str] = []
        for p in sorted(out.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(out)
            parts.append(f"=== {rel} ===\n{p.read_text(encoding='utf-8')}")
        return "\n".join(parts)


@pytest.mark.parametrize("plugin_type", PLUGIN_TYPES)
def test_template_matches_golden(plugin_type: str) -> None:
    """Snapshot test: regenerate with `pytest --snapshot-update` after intentional change."""

    rendered = _render_snapshot(plugin_type)
    golden_path = GOLDEN_DIR / _filename_for(plugin_type)

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(rendered, encoding="utf-8")
        pytest.skip(f"snapshot updated: {golden_path}")

    if not golden_path.exists():
        # Bootstrap: first run captures the snapshot.
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(rendered, encoding="utf-8")
        return

    expected = golden_path.read_text(encoding="utf-8")
    assert rendered == expected, (
        f"Template '{plugin_type}' diverged from golden snapshot. "
        f"If intentional, re-run with UPDATE_SNAPSHOTS=1 to refresh."
    )


@pytest.mark.parametrize("lang", LANGUAGES)
def test_i18n_catalog_has_all_keys(lang: str) -> None:
    """Each of the 3 supported languages exposes the same key set."""

    import json
    from importlib.resources import files

    pkg = files("create_jw_agent.lang")
    en = json.loads(pkg.joinpath("en.json").read_text(encoding="utf-8"))
    target = json.loads(pkg.joinpath(f"{lang}.json").read_text(encoding="utf-8"))
    assert set(en.keys()) == set(target.keys()), (
        f"{lang}.json missing keys: {set(en.keys()) - set(target.keys())}"
    )


def test_all_15_combos_render_without_exception(tmp_path: Path) -> None:
    """End-to-end: every (type, lang) combo renders cleanly."""

    for plugin_type in PLUGIN_TYPES:
        for lang in LANGUAGES:
            out = tmp_path / f"{plugin_type}-{lang}"
            ctx = RenderContext.build(
                name=f"my-{plugin_type}", type=plugin_type, lang=lang,
            )
            render_template(template_type=plugin_type, output_dir=out, ctx=ctx)
            assert (out / "pyproject.toml").exists()
