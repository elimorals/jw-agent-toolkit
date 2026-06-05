# Bible Knowledge Graph (Fase 58)

> Hidrata `jw-brain` con un knowledge graph bíblico (personas, lugares,
> periodos, pasajes) construido desde fuentes JW puras: Estudio Perspicaz
> de las Escrituras (Insight on the Scriptures) y NWT/NWTsty.

## Por qué versión propia y no `theographic-bible-metadata`

El KG académico upstream incorpora datos de tradiciones no-JW (Catholic
Encyclopedia, Jewish Encyclopedia, ISBE). Para mantener el toolkit
doctrinalmente puro, derivamos los datos del Insight oficial Watch Tower,
así la cronología refleja la postura JW (p. ej. **destrucción de Jerusalén
en 607 a.E.C.**, NO en 587/586 a.E.C. del consenso académico).

## Atribución

Los datos generados localmente son derivados del Estudio Perspicaz de las
Escrituras (Insight on the Scriptures), © Watch Tower Bible and Tract
Society of Pennsylvania. El toolkit **no** redistribuye texto ni media;
solo procesa el JWPUB que el usuario descarga oficialmente de jw.org.

## Schema añadido

F58 amplía el `tj` domain de `jw-brain`:
- **Nodos**: `Period`, `Passage` (nuevos). `Person`, `Place` ya existían en F49.
- **Edges**: `LIVED_IN_PERIOD`, `ACTIVE_IN_PERIOD`, `MENTIONED_IN_PASSAGE`,
  `LOCATED_IN_PASSAGE`, `PASSAGE_BELONGS_TO_PERIOD`.

## Pipeline

1. `BibleLoader.import_periods()` — hidrata 10 nodos `Period` desde catálogo
   curado en código (`period_catalog.py`). Mutable solo editando ese archivo.
2. `BibleLoader.import_insight(jwpub_path)` — parsea cabezales del Insight,
   clasifica por catálogo (`PERSON_HEADWORDS`/`PLACE_HEADWORDS`), extrae
   primera-mención por regex sobre `<a class="b">`, emite `Person`/`Place`/
   `Passage` con edges `MENTIONED_IN_PASSAGE`/`LOCATED_IN_PASSAGE`.

## Uso

```bash
# 1) Inicializa un brain (si no existe)
jw brain init --domain tj --brain personal --vault ~/obs/jw

# 2) Importa solo el catálogo de periodos (siempre primero)
jw brain import-bible --brain personal --periods-only

# 3) Importa el Insight (descargado de jw.org)
jw brain import-bible --brain personal --insight ~/jwpubs/it_S.jwpub --symbol it --meps-language 3
```

## Queries habilitadas

Con el grafo poblado, queries antes imposibles ahora funcionan:

- *¿Qué personas se mencionan en el libro de Génesis?*  
  → `MATCH (p:Person)-[:MENTIONED_IN_PASSAGE]->(pa:Passage) WHERE pa.book_num=1 RETURN p.name`
- *¿Qué lugares estuvieron activos durante el Cautiverio Babilónico?*  
  → `MATCH (pl:Place)-[:ACTIVE_IN_PERIOD]->(p:Period) WHERE p.slug='babylonian_exile' RETURN pl.name`
- *¿Qué pasajes mencionan tanto a Abraham como a Jerusalén?*  
  (combinación de dos hops, ver `tests/test_imports_bible_e2e.py`)

## Idempotencia

`import-bible` es idempotente por `canonical_id` (`person:abraham`,
`place:jerusalem`, `period:patriarchal`, `passage:1:11:26`). Re-correr
sobre el mismo JWPUB no duplica nodos ni edges.

## Limitaciones

- El catálogo `PERSON_HEADWORDS`/`PLACE_HEADWORDS` cubre solo las entradas
  bíblicas más comunes (26 inicial). Se expande iterativamente.
- Conceptos teológicos (Trinidad, Reino, Espíritu Santo) **no** se importan
  como nodos — son artículos del Insight, pero no encajan en el schema
  `Person`/`Place`/`Period`/`Passage` y van a otro flujo (RAG semántico).
- Las geocoordenadas (`latitude`/`longitude`) están en el schema pero no
  se rellenan en F58. Se hidratarán en un sprint futuro desde otro
  catálogo curado.
