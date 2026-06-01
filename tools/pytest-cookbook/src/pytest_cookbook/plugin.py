"""pytest plugin: collect runnable Python blocks from cookbook Markdown.

Activation: `pytest --cookbook-dir=docs/cookbook`.

A block is collected when:
  1. Inside a ```python fenced code block.
  2. Its first non-empty line is `# test` (possibly with a marker).

Recognized markers on the `# test` line:
  - `# test`                     — always run.
  - `# test slow`                — collected only if `-m slow` is passed.
  - `# test skip-until-fase=N`   — always skipped (with a reason).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest


_FENCE = re.compile(
    r"^```python\s*$(?P<body>.*?)^```\s*$",
    re.DOTALL | re.MULTILINE,
)
_TEST_MARKER = re.compile(
    r"^\s*#\s*test(\s+(?P<marker>.+))?\s*$",
)


@dataclass(frozen=True)
class CookbookBlock:
    source_path: Path
    block_index: int
    code: str
    marker: str | None  # None = always-run; "slow" or "skip-until-fase=N"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--cookbook-dir",
        action="store",
        default=None,
        help="Path to a directory of cookbook Markdown recipes.",
    )


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    # Marker registration handled below via pytest_configure.
    return


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "cookbook(path,index): A test extracted from a cookbook recipe.",
    )
    config.addinivalue_line(
        "markers",
        "slow: Marks a slow cookbook test (skipped unless -m slow is passed).",
    )


def pytest_collect_file(parent, file_path: Path):
    cookbook_dir = parent.config.getoption("--cookbook-dir")
    if cookbook_dir is None:
        return None
    cookbook_root = Path(cookbook_dir).resolve()
    if file_path.suffix.lower() != ".md":
        return None
    try:
        file_path.resolve().relative_to(cookbook_root)
    except ValueError:
        return None
    return CookbookFile.from_parent(parent, path=file_path)


class CookbookFile(pytest.File):
    def collect(self):
        text = self.path.read_text(encoding="utf-8")
        for idx, block in enumerate(_extract_test_blocks(text)):
            yield CookbookItem.from_parent(
                self,
                name=f"block_{idx}",
                block=CookbookBlock(
                    source_path=self.path,
                    block_index=idx,
                    code=block["code"],
                    marker=block["marker"],
                ),
            )


class CookbookItem(pytest.Item):
    def __init__(self, *, name, parent, block: CookbookBlock):
        super().__init__(name, parent)
        self.block = block
        # Apply pytest markers based on the cookbook marker.
        if block.marker:
            if block.marker.startswith("skip-until-fase"):
                self.add_marker(
                    pytest.mark.skip(reason=f"cookbook block requires {block.marker}")
                )
            elif block.marker.strip() == "slow":
                self.add_marker(pytest.mark.slow)

    def runtest(self) -> None:
        local_ns: dict = {"__name__": "__cookbook__"}
        try:
            exec(compile(self.block.code, str(self.block.source_path), "exec"), local_ns)
        except Exception as exc:
            raise CookbookError(self.block, exc) from exc

    def repr_failure(self, excinfo, style=None):  # noqa: ARG002
        if isinstance(excinfo.value, CookbookError):
            ce = excinfo.value
            return (
                f"\n{ce.block.source_path}:block #{ce.block.block_index}\n"
                f"  {type(ce.cause).__name__}: {ce.cause}\n"
            )
        return super().repr_failure(excinfo)

    def reportinfo(self):
        return (
            self.path,
            self.block.block_index,
            f"cookbook[{self.block.source_path.name}#{self.block.block_index}]",
        )


class CookbookError(Exception):
    def __init__(self, block: CookbookBlock, cause: BaseException) -> None:
        self.block = block
        self.cause = cause
        super().__init__(f"cookbook block {block.block_index} failed: {cause}")


def _extract_test_blocks(text: str) -> list[dict]:
    """Yield `{'code': str, 'marker': str|None}` for each ` ```python ` block
    whose first non-empty line is `# test`."""

    out: list[dict] = []
    for m in _FENCE.finditer(text):
        body = m.group("body")
        # Find first non-empty line.
        lines = body.splitlines()
        first_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first_idx is None:
            continue
        first = lines[first_idx]
        marker_match = _TEST_MARKER.match(first)
        if marker_match is None:
            continue
        # Strip the marker line from the executable code.
        code = "\n".join(lines[first_idx + 1 :])
        marker = marker_match.group("marker")
        out.append({"code": code, "marker": marker.strip() if marker else None})
    return out
