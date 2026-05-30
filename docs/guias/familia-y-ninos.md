# Familia y niños (Módulo 5)

> Cubre el ítem #5 de [VISION.md](../VISION.md): adoración familiar, recursos para niños, quiz bíblico interactivo por edad.

## Capas

| Archivo | Función |
|---|---|
| `jw_core/family/kids_resources.py` | Catálogo del libro "Aprende del Gran Maestro" (lf) — lecciones × edad × topic |
| `jw_core/family/family_worship.py` | Generador de planes semanales (`plan_family_worship`) |
| `jw_core/family/quiz.py` | Pool de preguntas bíblicas con edad y dificultad |

## Bandas de edad

Tres bandas siguiendo la segmentación oficial del libro:

- `younger` — 3-7 años
- `middle` — 8-11 años
- `older` — 12-15 años

## Catálogo de lecciones

9 lecciones del Gran Maestro indexadas con `topic` canónico + `scripture_anchors` + `age_bands`. **No contiene prosa** — para el cuerpo del texto descarga el EPUB:

```python
from jw_core.family import list_lessons_for_age, pick_lesson_by_topic

# Catálogo localizado
print(list_lessons_for_age("middle", language="es"))

# Búsqueda directa
lesson = pick_lesson_by_topic("ransom", language="en")
print(lesson["title"])  # "Why Did Jesus Die for Us?"
```

## Plan de adoración familiar

```python
from jw_core.family import plan_family_worship

plans = plan_family_worship(
    weeks=4,
    start_date="2026-06-01",
    age_band="middle",
    language="es",
)
for p in plans:
    print(p.week_of, "—", p.theme, "→", p.main_scripture)
```

El generador rota entre los topics prioritarios para esa edad y arma:
- `theme` (título de la lección)
- `main_scripture` + `secondary_scriptures`
- `activity_hook` localizado (dibujar, ejemplo personal, situación real)
- `song_suggestion` (curaduría hand-coded de Sing Out Joyfully)

## Quiz bíblico

```python
from jw_core.family import generate_quiz

quiz = generate_quiz(age_band="younger", n_questions=5, language="es", seed=1)
for q in quiz:
    print(q["prompt"], "→", q["answer"], f"({q['scripture_ref']})")
```

**Determinismo:** con `seed=...` se garantizan resultados reproducibles para testing.

## Tests

11 tests en `packages/jw-core/tests/test_family_module.py`:
- Catálogo no vacío, lookup por topic, fallback inexistente.
- Plan familiar con 4 semanas distanciadas exactamente 7 días.
- Topic overrides respetados.
- Quiz determinista con seed; count respetado.

```bash
uv run pytest packages/jw-core/tests/test_family_module.py -v
```

## Cómo extender

- **Más lecciones:** apendear a `GREAT_TEACHER_LESSONS`.
- **Nueva publicación infantil (p.ej. "caudal jw"):** crea un módulo `caudal_jw.py` con la misma forma y un `pick_*` localizado.
- **Topic → song mapping personalizado:** edita `_song_for_topic` en `family_worship.py`.
