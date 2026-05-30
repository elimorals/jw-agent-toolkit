#!/usr/bin/env bash
# Bootstrap (or refresh) the pytest-recording cassettes for the critical API
# shape tests. Run when:
#   - cassettes don't exist yet (first time)
#   - JW.org changes a response shape (drift detected via telemetry)
#
# Usage:
#   ./scripts/record_cassettes.sh
#
# After this runs, the cassettes are checked into the repo and the
# corresponding tests run offline.
set -euo pipefail

cd "$(dirname "$0")/.."

CASSETTE_DIR="packages/jw-core/tests/cassettes/test_cassettes"
mkdir -p "$CASSETTE_DIR"

# Create empty placeholder cassettes so the skipif gate in the test file
# allows the test to run; --record-mode=rewrite then overwrites them with
# real recordings.
for name in \
    test_mediator_languages_shape \
    test_weblang_languages_shape \
    test_cdn_search_shape \
    test_pub_media_catalog_shape; do
    touch "$CASSETTE_DIR/$name.yaml"
done

# Strip the macOS UF_HIDDEN flag that breaks editable installs.
if [[ "$OSTYPE" == "darwin"* ]]; then
    chflags nohidden .venv/lib/python3.13/site-packages/*.pth 2>/dev/null || true
fi

uv run pytest packages/jw-core/tests/test_cassettes.py \
    --record-mode=rewrite -v

echo "Recorded cassettes:"
ls -lh "$CASSETTE_DIR"
