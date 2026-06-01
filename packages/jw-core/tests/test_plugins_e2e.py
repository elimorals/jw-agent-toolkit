"""End-to-end: install plugin_sample with `uv pip install -e` in a subprocess
that creates an ephemeral venv, then run discovery from inside that venv.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "plugin_sample"
REPO_ROOT = Path(__file__).resolve().parents[3]


def _have_uv() -> bool:
    return shutil.which("uv") is not None


pytestmark = pytest.mark.skipif(not _have_uv(), reason="uv not installed")


@pytest.fixture(scope="module")
def plugin_venv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create an isolated venv with jw-core + plugin_sample installed editable."""

    venv = tmp_path_factory.mktemp("plugin_venv")
    subprocess.run(["uv", "venv", str(venv)], check=True, capture_output=True)

    py = venv / ("Scripts" if sys.platform == "win32" else "bin") / "python"

    subprocess.run(
        [
            "uv", "pip", "install", "--python", str(py),
            "-e", str(REPO_ROOT / "packages" / "jw-core"),
            "packaging",
            "cryptography",  # transitive used by jw_core.parsers.jwpub
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["uv", "pip", "install", "--python", str(py), "-e", str(FIXTURE)],
        check=True,
        capture_output=True,
    )
    return py


def _run_in_venv(py: Path, code: str, env: dict[str, str] | None = None) -> str:
    full_env = {**os.environ, **(env or {})}
    out = subprocess.run(
        [str(py), "-c", code],
        check=True,
        capture_output=True,
        env=full_env,
        text=True,
    )
    return out.stdout.strip()


def test_e2e_agent_discovered(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "plugins = get_plugins('jw_agent_toolkit.agents')\n"
        "print(json.dumps(sorted(plugins.keys())))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    names = json.loads(out)
    assert "plugin_sample_agent" in names


def test_e2e_all_five_groups_discovered(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "groups = ["
        "  'jw_agent_toolkit.agents',"
        "  'jw_agent_toolkit.parsers',"
        "  'jw_agent_toolkit.embedders',"
        "  'jw_agent_toolkit.vlm_providers',"
        "  'jw_agent_toolkit.gen_providers',"
        "]\n"
        "out = {g: sorted(get_plugins(g).keys()) for g in groups}\n"
        "print(json.dumps(out))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    parsed = json.loads(out)
    assert "plugin_sample_agent" in parsed["jw_agent_toolkit.agents"]
    assert "plugin_sample_parser" in parsed["jw_agent_toolkit.parsers"]
    assert "plugin_sample_embedder" in parsed["jw_agent_toolkit.embedders"]
    assert "plugin_sample_vlm" in parsed["jw_agent_toolkit.vlm_providers"]
    assert "plugin_sample_gen" in parsed["jw_agent_toolkit.gen_providers"]


def test_e2e_verify_plugin_reports_ok(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import verify_plugin\n"
        "rep = verify_plugin('plugin_sample_agent', 'jw_agent_toolkit.agents')\n"
        "print(json.dumps({"
        "  'ok': rep.ok,"
        "  'required_present': list(rep.required_present),"
        "  'required_missing': list(rep.required_missing),"
        "  'optional_present': list(rep.optional_present),"
        "  'dist_name': rep.dist_name,"
        "  'version_satisfied': rep.version_satisfied,"
        "}))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    rep = json.loads(out)
    assert rep["ok"]
    assert "__call__" in rep["required_present"]
    assert "languages" in rep["optional_present"]
    assert rep["dist_name"] == "plugin-sample"


def test_e2e_disabled_env_short_circuits(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "print(json.dumps(list(get_plugins('jw_agent_toolkit.agents').keys())))\n"
    )
    out = _run_in_venv(plugin_venv, code, env={"JW_PLUGINS_DISABLED": "1"})
    assert json.loads(out) == []


def test_e2e_allow_list_filters(plugin_venv: Path) -> None:
    code = (
        "import json\n"
        "from jw_core.plugins import get_plugins\n"
        "print(json.dumps(sorted(get_plugins('jw_agent_toolkit.agents').keys())))\n"
    )
    out = _run_in_venv(
        plugin_venv, code, env={"JW_PLUGINS_ALLOW_LIST": "nonexistent_only"}
    )
    assert json.loads(out) == []


def test_e2e_resolve_runs_callable(plugin_venv: Path) -> None:
    code = (
        "import asyncio, json\n"
        "from jw_core.plugins import get_plugins\n"
        "spec = get_plugins('jw_agent_toolkit.agents')['plugin_sample_agent']\n"
        "fn = spec.resolve()\n"
        "got = asyncio.run(fn(question='hi'))\n"
        "print(json.dumps({'agent': got['agent'], 'q': got['echo']['question']}))\n"
    )
    out = _run_in_venv(plugin_venv, code)
    parsed = json.loads(out)
    assert parsed["agent"] == "plugin_sample_agent"
    assert parsed["q"] == "hi"
