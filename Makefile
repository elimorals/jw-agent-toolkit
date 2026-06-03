# Makefile for jw-agent-toolkit cross-language parity targets.
# F56.4 — central place for "regenerate the shared fixture from Python ground truth"
# so CI and developers run the same command.

.PHONY: dump-shared-data test-parity help

help:
	@echo "Targets:"
	@echo "  dump-shared-data  Regenerate shared/data/bible_references_golden.json"
	@echo "                    from the Python parser (jw_core.parsers.reference)."
	@echo "  test-parity       Run Python + TypeScript golden fixture parity suites."

dump-shared-data:
	uv run python scripts/dump_shared_fixture.py

test-parity:
	uv run pytest packages/jw-core/tests/test_golden_fixture_parity.py -v
	cd packages/jw-core-js && npm test
