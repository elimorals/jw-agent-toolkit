"""Shared fixtures for jw-brain tests."""

from __future__ import annotations


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--neo4j-tests",
        action="store_true",
        default=False,
        help="Run Neo4j-backed tests (requires testcontainers Neo4j).",
    )


def pytest_generate_tests(metafunc) -> None:
    if "backend_name" in metafunc.fixturenames:
        params = ["duckdb"]
        if metafunc.config.getoption("--neo4j-tests", default=False):
            params.append("neo4j")
        metafunc.parametrize("backend_name", params, ids=params)
