# wol_snapshots

Minified HTML snapshots used by the L2 (citations) evaluator in offline mode.

## Build

```bash
uv run python packages/jw-eval/scripts/build_eval_snapshots.py
```

The script:
1. Reads every `*.yaml` under `../golden_qa/l2/`.
2. Collects unique URLs from `expected.expected_citations`.
3. Downloads each URL with `httpx`, strips `<script>`/`<style>` and runs of
   whitespace, and writes `<sha256(URL)>.html`.

## Why offline?

In CI we cannot rely on `wol.jw.org` being reachable or unchanged. The
snapshots are committed so the L2 evaluator is deterministic and blocking
on PRs. The weekly `eval-l2-live` job re-fetches the URLs and opens GitHub
issues if the live page no longer contains the expected phrases.

## Initial state

These snapshots were **not** auto-built in the same commit as the YAML
cases — the original implementation session was offline. The L2 evaluator
returns `skip` (not `fail`) when a snapshot is missing, so the suite stays
green until the snapshots are built. Run the build script above to
populate them before flipping `eval-fast` to a blocking gate.
