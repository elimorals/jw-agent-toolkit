# Verificación y apologética avanzada (Módulo 9)

> Cubre el ítem #9 de [VISION.md](../VISION.md): fact-checker contra fuentes JW oficiales, detector de información apócrifa, análisis de argumentos opositores.

## Dos agentes nuevos

### `fact_checker(claim)`

Verifica una afirmación SOLO contra `jw.org` / `wol.jw.org` / RAG local construido desde fuentes oficiales. Emite un veredicto:

- **SUPPORTED** — varias fuentes oficiales alinean.
- **DISPUTED** — evidencia mixta o solo RAG/no publicado.
- **REJECTED** — encontramos contradicciones explícitas y nada de soporte.
- **UNVERIFIABLE** — jw.org no tiene material sobre el tema (no fabricamos veredicto).

```python
import asyncio
from jw_agents.fact_checker import fact_checker

result = asyncio.run(fact_checker(
    "Jehovah's Witnesses celebrate Easter.",
    language="E",
    require_published=True,
))
print(result.metadata["verdict"], "—", result.metadata["rationale"])
```

**Cómo detecta contradicciones:** busca frases marcadoras (`"not biblical"`, `"no es bíblico"`, `"is unscriptural"`) en los párrafos de los artículos. No es NLU profundo, pero es **explicable** y conservador.

### `apocrypha_detector(text)`

Identifica citas falsamente atribuidas a publicaciones JW. Algoritmo:

1. Extrae cada `"... quoted ..."` (mínimo 20 chars).
2. Detecta framings sospechosos: `"the Watchtower said"`, `"los Testigos enseñan"`, etc.
3. Para cada cita, corre `reverse_citation_lookup` (overlap de bigramas contra publications de jw.org).
4. Veredictos:
   - **GENUINE** — overlap ≥ 0.55.
   - **APOCRYPHAL** — framing presente + overlap < 0.55.
   - **SUSPICIOUS** — sin framing pero sin match fuerte.

```python
result = asyncio.run(apocrypha_detector(
    'My friend said the Watchtower said "we are God\'s only true church".',
    language="E",
))
for f in result.findings:
    print(f.metadata["verdict"], "→", f.summary)
```

## Ranking de autoridad (refresher)

Recordatorio: los findings de ambos agentes carry `metadata['source']` siguiendo la jerarquía global del toolkit:

```
topic_index > question_refs > verse_text > study_note > cdn_search > rag
```

El LLM consumidor debe priorizar en ese orden cuando sintetice una respuesta final.

## Tests (sin red)

11 tests en `packages/jw-agents/tests/test_apologetics_advanced.py`:

- `_judge` con cada permutación de evidencia (supported/disputed/rejected/unverifiable).
- Downgrade de RAG-only a DISPUTED cuando `require_published=True`.
- Detección de framings ("Watchtower said") en español/inglés.
- `_extract_candidates` capturando comillas con ≥20 chars.
- `_verdict` con tabla de casos límite.

```bash
uv run pytest packages/jw-agents/tests/test_apologetics_advanced.py -v
```

## Política de rechazo a fuentes externas

`require_published=True` (default) implementa la regla VISION.md: si no está en `jw.org`/`wol.jw.org`, no cuenta como prueba. Esto previene contaminación por sites apóstatas con look-alike URLs.

Si el usuario insiste en RAG local-only (para offline), `require_published=False` permite veredictos basados solo en el corpus indexado, pero el toolkit ya no garantiza que las refs sean verificables externamente.

## Cómo extender

- **Más frases marcadoras de contradicción:** edita `_CONTRADICTION_HINTS` en `fact_checker.py`.
- **Más framings apócrifos:** edita `_SUSPICIOUS_FRAMING` en `apocrypha_detector.py`.
- **Veredicto explicado con cuotas:** envolver `fact_checker` con un agente "advanced" que llame al LLM solo para parafrasear el `rationale`.

## Pendiente

- Análisis de páginas opositoras conocidas (uso defensivo) — requiere blocklist URL + scraping autorizado.
- Detector multilingüe de framings (añadir alemán/francés cuando BOOKS los soporte).
