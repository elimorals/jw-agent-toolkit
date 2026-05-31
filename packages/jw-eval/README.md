# jw-eval

Doctrinal regression eval suite for the jw-agent-toolkit.

Three layers:
- **L1 — Structural** — agent contract regression (no network, no LLM).
- **L2 — Citations** — every URL resolves and supports the claim (snapshot or live).
- **L3 — Semantic** — agent answer ≈ golden answer (embeddings + LLM judge).

Run: `jw eval --layer 1,2`.
Spec: `docs/superpowers/specs/2026-05-30-fase-22-eval-doctrinal-design.md`.
