# Estudio personal y notas (Módulo 4 — Fase 14)

> Cierra el ítem #4 de [VISION.md](../VISION.md): plan de lectura, notas personales con RAG, spaced-repetition, comparador entre traducciones, análisis de idiomas originales.

## Componentes

| Módulo | Archivo | Función |
|---|---|---|
| Plan de lectura | `jw_core/study/reading_plan.py` | 3 planes (año completo, NT 90 días, cronológico) + SQLite tracker |
| Notas personales | `jw_core/study/personal_notes.py` | Per-versículo, FTS5, export a RAG |
| Flashcards SM-2 | `jw_core/study/flashcards.py` | Spaced repetition con SuperMemo-2 |
| Idiomas originales | `jw_core/study/originals.py` | Strong's catalog + carga dinámica de dumps |
| Agente | `jw_agents/personal_study.py` | Une plan + notas + cards → AgentResult |

## Planes de lectura

```python
from jw_core.study import ReadingPlanTracker, list_reading_plans

# Ver catálogo
for p in list_reading_plans("es"):
    print(p["key"], "—", p["title"], f"({p['days']} días)")

# Trackear progreso
with ReadingPlanTracker() as t:
    t.mark_done("nt_90", 1, note="Mateo terminado")
    print(t.status("nt_90"))
    print(t.upcoming("nt_90", count=3))
```

Default DB: `~/.jw-agent-toolkit/study.db` (override `JW_STUDY_DB`).

### Cobertura

- `whole_bible_year`: 1189 capítulos / 365 días — ~3.26 capítulos/día.
- `nt_90`: 27 libros del NT en 90 días.
- `chronological`: Génesis + Éxodo + Job + resto AT + NT, en orden histórico aproximado.

## Notas personales

```python
from jw_core.study import PersonalNote, PersonalNoteStore

with PersonalNoteStore() as notes:
    notes.add(PersonalNote(
        book_num=43, chapter=3, verse=16,
        title="El amor de Dios", body="Notas sobre Juan 3:16...",
        tags=["amor", "salvación"], language="es",
    ))
    # Búsqueda FTS5 instantánea
    hits = notes.search("amor")
    # Filtro por anchor
    for_juan = notes.for_anchor(43, 3, 16)
```

**Privacidad:** SQLite local en `~/.jw-agent-toolkit/notes.db` (override `JW_NOTES_DB`). Cero red.

**Export a RAG:**
```python
from jw_core.study import notes_to_rag_chunks
from jw_rag import VectorStore, FakeEmbedder
from jw_rag.chunker import Chunk

store = VectorStore(".rag", FakeEmbedder(64))
with PersonalNoteStore() as notes:
    raw_chunks = notes_to_rag_chunks(notes.list_all())
    store.add([Chunk(**c) for c in raw_chunks])
```

## Flashcards (SM-2)

Implementa el algoritmo SuperMemo-2: quality 0-5, EF inicial 2.5, intervalos 1 → 6 → `interval × EF`.

```python
from jw_core.study import Flashcard, FlashcardDeck, review_card

with FlashcardDeck() as deck:
    card = deck.upsert(Flashcard(front="John 3:16", back="For God so loved..."))
    # Marca recall perfecto
    review_card(deck, card.card_id, quality=5)
    # Ver lo que toca hoy
    due_today = deck.due_today()
```

**Quality scale:**
- 5 — recall perfecto
- 4 — correcto con titubeo
- 3 — correcto con dificultad seria
- 2 — incorrecto, recordó al ver
- 1 — incorrecto, costó recordar
- 0 — blackout total

DB: `~/.jw-agent-toolkit/cards.db` (override `JW_CARDS_DB`).

## Idiomas originales (Strong's)

Catálogo built-in con los términos más citados en apologética JW:

| Strong's | Translit. | Original | Notas |
|---|---|---|---|
| `H3068` | YHWH | יְהוָה | Jehová |
| `H430` | elohim | אֱלֹהִים | Dios / dioses / jueces |
| `H5315` | nephesh | נֶפֶשׁ | Alma (criatura viviente, no separable) |
| `H7585` | sheol | שְׁאוֹל | Sepulcro común |
| `G86` | hadēs | ᾅδης | Sepulcro / lugar de los muertos |
| `G2962` | kyrios | κύριος | Señor |
| `G5590` | psychē | ψυχή | Alma mortal |

```python
from jw_core.study import get_strong_entry, register_strong_dump, StrongEntry

e = get_strong_entry("G5590")
print(e.gloss_for("es"))  # ['aliento', 'vida', 'alma (mortal)']

# Carga un dump completo
register_strong_dump([
    StrongEntry(strong_number="G26", transliteration="agapē", original="ἀγάπη",
                glosses={"en": ["love (selfless)"], "es": ["amor (desinteresado)"]}),
    # ...
])
```

## Comparador de traducciones (ya estaba en Fase 3)

La herramienta MCP `compare_translations(book_num, chapter, verse, languages=...)` ya existe. Para incluir traducciones no-NWT (Reina-Valera, etc.) en una próxima iteración se puede:

1. Añadir un cliente `BibleGatewayClient` o usar dumps locales.
2. Extender `compare_translations` para aceptar un campo `bible_code=...` por idioma.

Esto entra en el Módulo 4.5 cuando se decida priorizar apologética con interlocutores que solo aceptan su Biblia tradicional.

## Agente compuesto

```python
import asyncio
from jw_agents.personal_study import personal_study

result = asyncio.run(personal_study("whole_bible_year", language="es", max_chapters=2))
print(result.metadata["today"])
for f in result.findings:
    print(f.metadata.get("source"), "-", f.summary)
```

Output incluye: capítulo del día, notas guardadas para ese capítulo, flashcards due hoy.

## Tests

`packages/jw-core/tests/test_study_module.py` — 17 tests:

- Cobertura completa de planes (1189 capítulos, sólo NT, etc.).
- Tracker upserts + status + upcoming.
- Notas: add, search FTS, anchor filter, export RAG.
- SM-2: quality<3 reset, intervalos 1→6, due_iso correcto, persistencia.
- Strong's: lookup built-in, multiidioma, register_dump, list.

```bash
uv run pytest packages/jw-core/tests/test_study_module.py -v
```

## Pendiente

- Web app de revisión (Fase 15 / Módulo 10).
- Sync end-to-end-encryption (Módulo 11).
- Strong's dump completo desde dominio público (Brown-Driver-Briggs / Thayer's) — añadir como dependencia opcional.
