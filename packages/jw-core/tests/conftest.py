"""Shared pytest configuration for jw-core tests.

Provides the `pytest-recording` cassette directory under
`packages/jw-core/tests/cassettes/`. To re-record cassettes (e.g. after
the jw.org API shape changes), run:

    uv run pytest packages/jw-core/tests/test_cassettes.py --record-mode=rewrite

To run normally (replay cassettes only, no network):

    uv run pytest packages/jw-core/tests/test_cassettes.py
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """Place all cassettes under tests/cassettes/{module_basename}/."""
    test_dir = Path(request.module.__file__).parent
    name = Path(request.module.__file__).stem
    return str(test_dir / "cassettes" / name)


@pytest.fixture(scope="module")
def vcr_config() -> dict[str, object]:
    """Strip identifying headers so cassettes are reproducible across machines."""
    return {
        "filter_headers": [
            "authorization",
            "cookie",
            "user-agent",
            "x-client-id",
        ],
        # Default to replay-only; re-record explicitly via --record-mode=rewrite.
        "record_mode": "none",
    }

from tests.conftest_plugins import _clear_plugin_cache  # noqa: F401

