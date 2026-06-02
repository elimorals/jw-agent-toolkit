# Synth Judge (Fase 44)

Quality filter for synthesized Q&A pairs before they reach `data/train.jsonl`.
Three pluggable stages, configurable per recipe, transparent scoring.

## Pipeline

```
synthesize_chunk -> validators (cheap) -> judge stage 1 heuristics (always)
                                       -> judge stage 2 LLM pedagogical (opt-in)
                                       -> judge stage 3 NLI entailment (opt-in)
                                       -> kept / rejected verdict
```

## Quick start

```bash
# Default LOOSE mode (heuristics only, zero network)
uv run jw-finetune data extract --recipe doctrinal

# STRICT mode (heuristics + harder cutoff)
uv run jw-finetune data extract --recipe doctrinal --judge=strict

# Full pipeline (LLM judge via Anthropic + NLI via DeBERTa)
JW_SYNTH_JUDGE_LLM=anthropic JW_SYNTH_JUDGE_NLI=deberta \
  uv run jw-finetune data extract --recipe doctrinal --judge=strict
```

When the judge is wired the kept JSONL rows carry the score:

```json
{
  "question": "...",
  "answer": "...",
  "metadata": {
    "pub_code": "w23",
    "judge_score": "{\"cites_jw_publication\": true, \"has_minimum_substance\": true, \"overall\": 7.0, \"kept\": true}"
  }
}
```

## Modes and cutoffs

| Mode    | Cutoff overall | Default NLI policy   |
|---------|----------------|----------------------|
| `off`   | None (passes all) | n/a               |
| `loose` | 5.0            | NLI optional         |
| `strict`| 6.5            | requires `entails`   |

Per-recipe override (YAML):

```yaml
synth:
  judge:
    mode: strict
    overall_cutoff: 7.0
    require_nli_entails: true
```

## Scoring formula (transparent)

```
base 4.0
+ 1.5 if cites_jw_publication (regex on w/g/jt/bh/sjj/jy/rs/it/lff/lr/sjm... or wol.jw.org URL)
+ 1.5 if has_minimum_substance (length >= 40, not generic, not a question echo)
+ 2.0 * nli_score if nli_verdict == "entails"
- 3.0 if nli_verdict == "contradicts"
+ pedagogical_quality (0..3, returned by the LLM judge)
clamp [0, 10]
```

Hard rules that force `kept=False` regardless of `overall`:
- `has_minimum_substance == False`
- `nli_verdict == "contradicts"`
- strict mode + `nli_verdict == "neutral"`
- `pedagogical_quality == 0`

## Programmatic use

```python
from jw_finetune.synth.judge import build_judge, JudgeMode

judge = build_judge(mode=JudgeMode.STRICT)
score = judge.score(
    question="¿Qué enseña la Biblia sobre el reino?",
    answer="Como muestra w23.04 página 12, el reino de Dios...",
    language="es",
)
print(score.kept, score.overall, score.reasons)
```

## Environment

| Variable                       | Default          | Effect                                  |
|--------------------------------|------------------|-----------------------------------------|
| `JW_SYNTH_JUDGE_LLM`           | `off`            | `anthropic` / `ollama` enables stage 2  |
| `JW_SYNTH_JUDGE_OLLAMA_MODEL`  | `llama3.1:8b`    | Ollama model for stage 2                |
| `JW_SYNTH_JUDGE_NLI`           | `off`            | NLI provider name for stage 3           |

## Precision

Heuristic-only LOOSE accuracy on the bundled golden 50-pair fixture is **0.86**
(target 0.85, LLM+NLI pushes past 0.90). STRICT hits **1.00** because the
higher cutoff catches every no-citation row regardless of substance.

```bash
uv run python -c "
from pathlib import Path
from jw_finetune.synth.judge.eval_precision import evaluate_precision
from jw_finetune.synth.judge.thresholds import JudgeMode
r = evaluate_precision(
    Path('packages/jw-finetune/tests/synth/judge/fixtures/golden_50_pairs.jsonl'),
    mode=JudgeMode.LOOSE,
)
print('accuracy:', r.accuracy)
"
```

## Rejected dump (audit)

```bash
uv run jw-finetune data extract \
  --recipe doctrinal --judge=strict \
  --dump-rejected /tmp/rejected.jsonl

# Inspect why pairs were dropped:
jq -c '.judge_score.reasons | map(.code) | unique' /tmp/rejected.jsonl | sort -u
```
