"""Tests for the block-extraction function (no pytest plumbing)."""

from __future__ import annotations

from pytest_cookbook.plugin import _extract_test_blocks


def test_extracts_block_with_test_marker() -> None:
    md = """# Recipe

```python
# test
assert 1 + 1 == 2
```
"""
    blocks = _extract_test_blocks(md)
    assert len(blocks) == 1
    assert "1 + 1 == 2" in blocks[0]["code"]
    assert blocks[0]["marker"] is None


def test_ignores_python_block_without_test_marker() -> None:
    md = """```python
print("no marker")
```
"""
    assert _extract_test_blocks(md) == []


def test_extracts_slow_marker() -> None:
    md = """```python
# test slow
import time
time.sleep(0.01)
```
"""
    blocks = _extract_test_blocks(md)
    assert blocks[0]["marker"] == "slow"


def test_extracts_skip_until_fase_marker() -> None:
    md = """```python
# test skip-until-fase=47
from foo import bar
```
"""
    blocks = _extract_test_blocks(md)
    assert blocks[0]["marker"] == "skip-until-fase=47"


def test_extracts_multiple_blocks() -> None:
    md = """```python
# test
x = 1
```

text in between

```python
# test
y = 2
```
"""
    blocks = _extract_test_blocks(md)
    assert len(blocks) == 2


def test_ignores_non_python_fence() -> None:
    md = """```bash
# test
echo "shell"
```
"""
    assert _extract_test_blocks(md) == []


def test_test_marker_must_be_first_non_empty_line() -> None:
    md = """```python
print("first")
# test
assert True
```
"""
    # Marker is not on the first non-empty line → not collected
    assert _extract_test_blocks(md) == []
