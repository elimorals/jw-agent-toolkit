# Decisiones de diseño

> Las decisiones que dan forma al proyecto, con el contexto que las motivó.

## 1. Monorepo con `uv workspace`

**Decisión**: cinco paquetes (`jw-core`, `jw-cli`, `jw-mcp`, `jw-rag`, `jw-agents`) viven en `packages/` bajo un único repo con `uv.lock` compartido.

**Por qué**:

- Los tipos de datos (`BibleRef`, `Verse`, `StudyNote`, `Article`) cambian con frecuencia en las primeras fases. Tenerlos en `jw-core` y refactorizarlos atómicamente a través de los consumidores es mucho más barato que coordinar PRs entre repos separados.
- Un único `uv.lock` garantiza instalables reproducibles en CI y entre contribuidores.
- Cada paquete sigue siendo **publicable independientemente** a PyPI cuando se estabilice.

**Trade-off**: el CI debe instalar siempre todo el workspace. Para un proyecto en esta escala (~8000 LOC) es despreciable.

## 2. Agentes procedurales, no LLM-driven

**Decisión**: los agentes en `jw-agents` son funciones async que orquestan parsers + clientes + RAG y devuelven `AgentResult` estructurado con `Finding`s + `Citation`s. **No invocan un LLM ellos mismos**.

**Por qué**:

- **Testeables sin mockear LLM**: las pruebas son rápidas y deterministas.
- **Cero coste**: ningún agente cobra tokens.
- **Reproducibles**: misma entrada → mismo `AgentResult`.
- **Componibles**: el LLM llamante (Claude Desktop o tu cliente) puede encadenar varios agentes desde su propia lógica.
- **Citas siempre verificables**: cada `Finding` lleva una URL de wol.jw.org. El LLM solo sintetiza prosa sobre evidencia ya cargada.

**Trade-off**: pipelines más rígidos que un agente LLM auto-orquestado. La decisión es consciente: preferimos rigidez verificable a flexibilidad alucinable.

## 3. Las superficies (CLI, MCP) son thin

**Decisión**: `jw-cli` y `jw-mcp` son envoltorios delgados sobre `jw-core` (+ agentes en el MCP). Toda la lógica vive más abajo.

**Por qué**:

- Si añadimos una nueva superficie (HTTP REST, gRPC, Telegram bot), no hay que duplicar lógica.
- Las herramientas MCP son básicamente *type adapters*: convierten parámetros JSON → llamadas a `jw-core` → resultado serializable.

## 4. Clientes HTTP que aceptan un `httpx.AsyncClient` opcional

**Decisión**: cada cliente (`CDNClient`, `WOLClient`, etc.) acepta `http: httpx.AsyncClient | None`. Si no se pasa, crea uno y rastrea si lo "posee" (`_owns_http`) para cerrarlo en `aclose()`.

**Por qué**:

- En el MCP server compartimos un único pool de conexiones entre clientes.
- En tests podemos inyectar un cliente mockeado o uno con interceptor.
- En scripts ad-hoc no nos preocupamos por la gestión: pasar nada también funciona.

```python
# Modo standalone — cliente crea su propio httpx
cdn = CDNClient()
await cdn.search("amor")
await cdn.aclose()

# Modo compartido — el MCP server pasa el mismo httpx a varios
shared_http = httpx.AsyncClient()
cdn = CDNClient(http=shared_http)
wol = WOLClient(http=shared_http)
topic = TopicIndexClient(cdn=cdn, wol=wol)
```

## 5. `FakeEmbedder` por defecto

**Decisión**: el `VectorStore` por defecto en el MCP server arranca con `FakeEmbedder(dim=64)`, un embedder hash-based determinista que **no es semánticamente útil**.

**Por qué**:

- El MCP debe arrancar **offline, sin API keys, sin descargas de modelos**.
- Los usuarios serios cablean su propio embedder (OpenAI, sentence-transformers) editando `_get_rag_store()` o aportando un extra `[openai]` / `[local]`.
- El `FakeEmbedder` garantiza que BM25 (que sí funciona bien) carga el peso real de la recuperación, mientras la similitud vectorial es solo decorativa.

**Trade-off**: la similitud vectorial está rota hasta que el usuario configure un embedder real. Es un default consciente: preferimos un MCP que arranque sin fricción a uno que requiera configuración previa.

## 6. Reciprocal Rank Fusion (RRF) en lugar de pesos lineales

**Decisión**: `VectorStore.hybrid_search` fusiona BM25 y resultados vectoriales con RRF (`1 / (k + rank)`), no con una combinación lineal de scores.

**Por qué**:

- BM25 y similitud por cosenos producen scores en escalas completamente distintas. Normalizarlos requiere asumir distribuciones; RRF solo requiere los rankings.
- RRF es robusto ante outliers de score.
- El parámetro `k=60` es el valor estándar de la literatura, suficiente para la mayoría de casos.

## 7. Reranking por título en `search_subjects`

**Decisión**: cuando se busca un tema en el Índice de Publicaciones (`TopicIndexClient.search_subjects`), por defecto rerankeamos los resultados por proximidad título → query antes de devolverlos.

**Por qué**:

- La búsqueda CDN trata el índice como otra fuente más; un query "Trinity" puede devolver "Hermas" arriba si "Trinity" aparece tangencialmente en su snippet.
- Hacemos un score 0-100 (100 = título == query, 80 = startswith, 60 = palabra completa, 40 = substring, 20 = token, 0 = nada).
- Empates rompen por el rank original del CDN.
- Es un toggle (`rerank_by_title_match=True` por defecto) para que los tests deterministas puedan apagarlo.

## 8. Restricción monotónica en notas de estudio

**Decisión**: al mapear `StudyNote.headword` a un versículo, cada match exitoso establece un suelo: el siguiente headword no puede mapear a un versículo anterior.

**Por qué**:

- Las notas de estudio aparecen en orden de versículo en el DOM.
- Sin monotonicidad, una colisión de headword (p.ej. "loved" aparece en versículos 3 y 16) puede romper la cadena entera.
- Con monotonicidad + fallback relajado + interpolación posicional, alcanzamos 100% de mapeo en John 3 (18/18 notas), 83% en versiones anteriores.

## 9. Resolución `code → URL` postergada (Phase 5+)

**Decisión**: las citas de publicaciones en el índice temático (p.ej. `"g05 4/22 7"` = Awake!, abril 22 2005, pág. 7) se devuelven como texto plano. **No las resolvemos a URLs**.

**Por qué**:

- Requiere un mapeo `pub-code → URL pattern` que solo es derivable consultando `GETPUBMEDIALINKS` para cada código.
- Por ahora el LLM consume el texto abreviado, suficiente para responder "esto está en Awake!, abril 22 2005".
- Cuando se implemente, será un módulo aparte (`jw_core/publication_codes.py`) reutilizable desde el MCP.

## 10. Sin cache persistente en disco (todavía)

**Decisión**: ninguna respuesta HTTP se cachea entre ejecuciones. Cada `WOLClient` arranca con `httpx.AsyncClient` virgen.

**Por qué**:

- Mantiene el toolkit sin estado entre sesiones.
- WOL es razonablemente rápido y no estamos cerca de límites de rate.
- En Fase 9 añadiremos cache SQLite con TTL.

## 11. Skills delgadas, MCP gordo

**Decisión**: los archivos `skills/jw-*/SKILL.md` son cortos (≤30 líneas). El conocimiento detallado vive en las descripciones de las herramientas MCP.

**Por qué**:

- Una skill solo necesita decirle al LLM cuándo usar el toolkit y qué herramienta MCP llamar.
- Las descripciones de las herramientas (en `server.py`) ya tienen Args/Returns que el cliente MCP ve.
- Duplicar la documentación es deuda.

## 12. Todo el código en español/inglés mixto, docs en español

**Decisión**: identificadores y docstrings en inglés. Documentación de usuario, README y guías en español.

**Por qué**:

- Inglés es el lingua franca de Python: librerías de terceros, traceback, mensajes de error.
- El usuario final del proyecto trabaja en español (esto es del autor).
- Mezclar identificadores en español rompería el patrón con `httpx`, `pydantic`, `typer`, etc.

## 13. JWPUB se descifra apoyándose en trabajo externo (Fase 5.5)

**Decisión**: en lugar de mantener la fase 5 abierta indefinidamente, integramos el algoritmo de derivación descubierto por [`gokusander/jwpub-toolkit`](https://github.com/gokusander/jwpub-toolkit) (MIT) con crédito explícito en el código y en la documentación.

**Por qué**:

- 4 scripts (`try_jwpub_decrypt[1-4].py`) probaron decenas de combinaciones SHA256/SHA1, AES-128/256, IVs varios, derivaciones por documento. Todas fallaron.
- La derivación correcta requiere conocer la **constante de XOR de 32 bytes** que solo se obtiene inspeccionando el binario de JW Library — un trabajo serio de reverse engineering que la comunidad ya hizo.
- Implementar `gokusander`'s solution con crédito conserva la cadena de licencias (MIT-compatible con GPL-3.0-only) y nos desbloquea para fase 6/7.

**Trade-off**: dependencia conceptual de un proyecto externo. Mitigación: el algoritmo es solo 4 líneas (`_compute_key_iv`), está testeado con vectores conocidos y queda blindado en nuestro repo.

## 14. Factory para producción, clientes sueltos para tests

**Decisión**: `jw_core.clients.factory.build_clients()` arma una `ClientSuite` con cache + throttler + telemetry **compartidos**. Para tests, los clientes siguen siendo construibles sin nada de eso.

**Por qué**:

- En tests unitarios, queremos clientes sin estado externo (no SQLite a limpiar, no rate-limiter que afecte timing).
- En producción, queremos UN cache, UN rate-limiter, UN telemetry — no seis instancias separadas que se pisen.
- El factory hace la decisión por el usuario; los flags `enable_cache/enable_throttling/enable_telemetry` permiten apagar individualmente.

**Trade-off**: dos APIs en paralelo (constructor directo vs factory). Mitigación: el factory es opt-in y opcional; los constructores siempre funcionan.

## 15. Telemetría opt-in en lugar de opt-out

**Decisión**: `JW_TELEMETRY_ENABLED` debe ser explícitamente `1`/`true`/`yes` para activar. Default: apagada.

**Por qué**:

- Telemetría debe ser predecible. Que un usuario empiece a generar JSONs en disco sin saberlo violaría el principio de menor sorpresa.
- Los baselines son específicos por instalación. Sin opt-in explícito, un drift event no aporta información útil.
- Cuando la API cambia, los maintainers (que tienen telemetría activada) reciben los warnings y actualizan los parsers. Los usuarios casuales no necesitan saberlo.

**Trade-off**: la detección de drift solo ayuda a quien la activa. Mitigación: la guía [`infraestructura-fase9.md`](../guias/infraestructura-fase9.md) explica cuándo encenderla.

## 16. CI con uv + Ruff + Mypy + Bandit (Fase 10)

**Decisión**: GitHub Actions workflow con stack moderno (`uv`, `ruff`, `mypy strict`, `pytest`, `bandit`). Mypy y Bandit corren con `continue-on-error: true`.

**Por qué**:

- `uv` da instalación reproducible con cache compartido. `ruff` reemplaza black + flake8 + isort.
- Mypy strict en FastMCP genera falsos positivos conocidos — preferimos verlos en logs sin romper el build a tener type checking apagado.
- Bandit es señal de seguridad informativa; los maintainers leen los hallazgos y deciden si actuar.
- El job `security` corre tras `test` para no gastar minutos si los tests fallan.

## 17. Cassettes pytest-recording para endpoints críticos

**Decisión**: 4 endpoints (mediator, weblang, cdn search, pub_media) tienen tests cassette-backed con YAMLs commiteados al repo.

**Por qué**:

- Los unit tests con fixtures HTML cubren los parsers, pero **no detectan cambios de shape** en la respuesta JSON.
- Cassettes congelan la shape exacta. Si jw.org cambia un campo, el test cassette puede seguir pasando (replay) pero el cassette en disco **es la documentación** de cómo era antes.
- Re-grabar (`--record-mode=rewrite`) es un acto consciente: el diff del YAML expone qué cambió.

**Trade-off**: cassettes deben mantenerse. Mitigación: solo grabamos los 4 endpoints más críticos; los demás están cubiertos con fixtures HTML estáticas.
