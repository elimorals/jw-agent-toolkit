# pytest-cookbook

pytest plugin that collects runnable Python blocks from cookbook-style Markdown files.

A block is collected when:

1. Inside a ` ```python ` fenced code block.
2. Its first non-empty line is `# test` (optionally with a marker, e.g. `# test slow`).

Usage:

```bash
pytest --cookbook-dir=docs/cookbook
```

Markers:

- `# test` — always run.
- `# test slow` — collected only with `-m slow`.
- `# test skip-until-fase=N` — skipped (with a reason) unless Fase N is marked done.

Internal tool only. Not published to PyPI.
