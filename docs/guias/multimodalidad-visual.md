# Multimodalidad visual (Módulo 7)

> Cubre el ítem #7 de [VISION.md](../VISION.md): OCR sobre fotos de la Biblia / publicaciones, mapas bíblicos, generación de slides para discursos.

## Tres subpiezas

| Archivo | Función |
|---|---|
| `jw_core/vision/ocr.py` | OCR opcional (pytesseract) + parser de referencias bíblicas sobre el texto |
| `jw_core/vision/maps.py` | Catálogo de lugares + journeys + búsqueda por distancia haversine |
| `jw_core/vision/slides.py` | Generador de decks (Markdown simple o Marp) |

## OCR

**Optional dependency** (`pytesseract` + `Pillow` + binario tesseract).

```python
from jw_core.vision import ocr_image, extract_bible_reference_from_image

text = ocr_image("page_photo.jpg", language="spa")

# Pipeline OCR → reference parser
info = extract_bible_reference_from_image("page_photo.jpg", language="es")
print(info["reference"])  # parsed BibleRef or None
```

Si no está instalado tesseract, `OCRError` con instrucciones (`brew install tesseract`).

## Mapas bíblicos

Catálogo built-in con 10 lugares clave (Jerusalén, Belén, Antioquía, Éfeso, Corinto, Atenas, Tesalónica, Filipos, Roma, Babilonia) y 3 journeys (segundo y tercer viaje de Pablo, exilio a Babilonia).

```python
from jw_core.vision import get_journey, list_journeys, locations_near

print(list_journeys("es"))

# Journey detalle
journey = get_journey("paul_2nd", language="es")
for w in journey["waypoints"]:
    print(w["name"], w["lat"], w["lon"])

# Localización por distancia
for loc in locations_near("jerusalem", radius_km=200, language="es"):
    print(loc["name"], "—", loc["distance_km"], "km")
```

## Slides

Dos flavours:

- `build_simple_deck(deck)` → Markdown puro con `---` separators.
- `build_marp_deck(deck)` → Marp directives, listo para `marp deck.md → pdf/pptx`.

```python
from jw_core.vision import outline_to_deck, build_marp_deck

deck = outline_to_deck(
    title="La esperanza de la resurrección",
    subtitle="Discurso público — 20 min",
    points=[
        {"heading": "Introducción",
         "bullets": ["Tema y texto", "Pregunta abridora"],
         "citation": "Job 14:14",
         "speaker_note": "Leer con sentimiento."},
        {"heading": "Punto 1: ¿Qué es la resurrección?",
         "bullets": ["Definición bíblica", "Ejemplos del Nuevo Testamento"],
         "citation": "Juan 5:28-29"},
    ],
    language="es",
    theme="default",
)
md = build_marp_deck(deck)
# Guardar en archivo y renderizar con `marp deck.md --pdf`
```

## Tests

10 tests en `packages/jw-core/tests/test_vision_module.py`:
- Journeys cargados + localizados.
- `locations_near` haversine retorna Belén cerca de Jerusalén.
- OCR raises clear error si pytesseract ausente.
- Marp deck contiene directivas + speaker notes.

```bash
uv run pytest packages/jw-core/tests/test_vision_module.py -v
```

## Pendiente

- Integrar OCR + `parse_all_references` para devolver TODAS las refs en una foto, no solo la primera.
- Detección de tablas/diagramas en mapas escaneados (requiere OpenCV).
- Generación de gráficos (matplotlib) para apoyar el deck.
