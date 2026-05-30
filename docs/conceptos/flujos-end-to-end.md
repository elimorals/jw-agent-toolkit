# Flujos end-to-end

> Diagramas de secuencia textuales para los flujos más comunes. Útil para colaboradores nuevos y para depurar.

## 1. Resolución de una cita bíblica (`resolve_reference`)

```
Usuario / LLM
    │
    │  resolve_reference(text="Juan 3:16", language="es")
    ▼
[jw-mcp] resolve_reference
    │
    │  parse_reference("Juan 3:16")
    ▼
[jw-core.parsers.reference] ReferenceParser._singleton().parse_one()
    │
    │  _norm("Juan 3:16") → "juan 3:16"
    │  regex.search → match {book="juan", chapter="3", verse_start="16"}
    │  _index["juan"] → (43, "es", "John")
    │
    ▼
BibleRef(book_num=43, book_canonical="John", chapter=3,
         verse_start=16, detected_language="es", raw_match="juan 3:16")
    │
    │  ref.wol_url(lang="es")
    ▼
"https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3#study=discover&v=43:3:16"
    │
    ▼
{book_num: 43, chapter: 3, verse_start: 16, wol_url: "...", ...}
```

Sin I/O. Puro CPU. El singleton del parser se compila una sola vez por proceso.

## 2. Descarga + parseo de un capítulo bíblico (`get_chapter`)

```
LLM
    │  get_chapter(book_num=43, chapter=3, language="es")
    ▼
[jw-mcp] get_chapter
    │
    │  WOLClient.get_bible_chapter(43, 3, language="es")
    ▼
[jw-core.clients.wol] WOLClient
    │
    │  get_language("es") → Language(iso="es", wol_resource="r4",
    │                                lp_tag="lp-s", default_bible="nwt")
    │  url = "https://wol.jw.org/es/wol/b/r4/lp-s/nwt/43/3"
    │  httpx.GET(url)
    ▼
HTML del capítulo (≈195KB para John 3 nwtsty)
    │
    │  parse_article(html)
    ▼
[jw-core.parsers.article]
    │  BeautifulSoup → <article id="article">
    │  título: primer h1
    │  párrafos: todos los <p> con data-pid o id="pN"
    │  refs: todos los <a class="b">
    ▼
Article(title="...", paragraphs=[...], references=[...])
    │
    ▼
{title, paragraphs, references, source_url, language, publication}
```

## 3. Agente `verse_explainer` (Fase 7)

```
LLM
    │  verse_explainer(reference="Juan 3:16", language="es")
    ▼
[jw-agents.verse_explainer]
    │
    │  ref = parse_reference("Juan 3:16")     ← pure
    │  → BibleRef(book_num=43, chapter=3, verse_start=16, ...)
    │
    │  WOLClient.get_bible_chapter(43, 3, language="es")
    ▼─── HTTP request → wol.jw.org → HTML
    │
    │  parse_article(html) → Article(title, paragraphs, refs)
    │  parse_verses(html, book_num=43, chapter=3, language="es")
    │  → list[Verse]
    │
    │  Target verses: filtrar v.verse == 16
    │  → [Verse(text="Porque tanto amó Dios al mundo...", ...)]
    │
    │  if include_study_notes:
    │      parse_study_notes(html, book_num=43, chapter=3, language="es")
    │      study_notes_for_verse(notes, 16) → notas mapeadas al v.16
    │
    │  if include_cross_refs:
    │      parse_cross_references(html, ...) filtrado a verse==16
    ▼
AgentResult(
    query="Juan 3:16",
    agent_name="verse_explainer",
    findings=[
        Finding(summary="John 3:16", excerpt="Porque tanto amó...",
                citation=Citation(url=verse_url, kind="verse")),
        Finding(summary="Study note: world", excerpt="...",
                citation=Citation(url=chapter_url, kind="study_note")),
        Finding(summary="Cross-reference marker at John 3:16", ...)
    ],
    metadata={book_num, chapter, verse_start, chapter_title, ...}
)
```

El LLM recibe `findings` ordenados (target verse primero, study notes después, cross-refs al final) y sintetiza la respuesta usando los `excerpt` como evidencia con `citation.url` como cita verificable.

## 4. Agente `apologetics` con índice temático + Bible refs + RAG

```
LLM
    │  apologetics(question="¿Qué dice la Biblia sobre la Trinidad? ¿Y Juan 1:1?",
    │              language="S", use_rag=True)
    ▼
[jw-agents.apologetics]
    │
    │  ── Paso 0: Topic Index (autoritativo JW) ──────
    │  TopicIndexClient.search_subjects("¿Qué dice la Biblia sobre la
    │                                    Trinidad?", language="S")
    │     ├── CDN search (filter="indexes")
    │     ├── _flatten_search_results
    │     └── _rerank_by_title_match → "TRINITY" sube a top-1
    │  → [{title: "Trinity", docid: "1200275936", wol_url: "..."}]
    │
    │  Para top-1: TopicIndexClient.get_subject_page("1200275936", language="es")
    │     ├── HTTP GET subject page
    │     └── parse_subject_page(html) → TopicSubject con N subheadings
    │  Finding 1: "Topic index: Trinity" (kind=topic_subject)
    │  Finding 2-9: cada subheading top-N (kind=topic_subheading)
    │  metadata[source] = "topic_index" / "topic_index_entry"
    │
    │  ── Paso 1: Bible refs explícitas ──────────────
    │  parse_all_references(question) → [BibleRef(book_num=43, ch=1, vs=1)]
    │  Para cada ref:
    │     Finding: "User cited John 1:1" (kind=verse, source="question_refs")
    │     WOLClient.get_bible_chapter(43, 1, language="es")
    │     get_verse(html, 43, 1, 1) → Verse con texto
    │     Finding: verse text (source="verse_text")
    │     parse_study_notes(html, ...) filtrado a verse==1
    │     Finding por cada nota (source="study_note")
    │
    │  ── Paso 2: Búsqueda CDN + artículos ────────────
    │  CDNClient.search(question, filter="all", language="S", limit=6)
    │  Para cada top-3 con wol_url:
    │     WOLClient.fetch(url) → HTML
    │     parse_article(html) → Article
    │     Finding: top paragraph (source="cdn_search")
    │
    │  ── Paso 3: RAG (opcional) ──────────────────────
    │  if rag_store and not is_empty:
    │     rag_store.hybrid_search(question, top_k=5)
    │        → BM25 + vector → RRF fusion
    │     Finding por cada hit (source="rag")
    ▼
AgentResult con findings ordenados por autoridad:
    topic_index > topic_index_entry > question_refs > verse_text
    > study_note > cdn_search > rag
```

El LLM sintetiza priorizando fuentes en ese orden — la metadata `source` se lo dice explícitamente.

## 5. Ingest RAG desde búsqueda (`ingest_search_topk`)

```
LLM o usuario
    │  ingest_search_topk(query="amor", top_n=5, filter_type="all",
    │                     language="E")
    ▼
[jw-rag.ingest.ingest_search_topk]
    │
    │  CDNClient.search("amor", filter_type="all", language="E", limit=5)
    │  → JSON con resultados
    │
    │  _extract_article_urls(data, limit=5)
    │  → ["https://wol.jw.org/...", ...]
    │
    │  Para cada URL:
    │     WOLClient.fetch(url) → HTML
    │     parse_article(html) → Article(title, paragraphs, refs)
    │     chunk_paragraphs(paragraphs, source_id=f"article:{url}",
    │                     metadata={kind, title, source_url})
    │        ├── merge párrafos cortos
    │        ├── split párrafos largos
    │        └── → list[Chunk]
    │     store.add(chunks)
    │        ├── embedder.embed([c.text for c in chunks])
    │        ├── l2_normalize
    │        ├── vstack a self._vectors
    │        └── rebuild BM25Okapi
    ▼
store.save()
    │
    │  chunks.jsonl + vectors.npy + meta.json en path
    ▼
{ingested_articles: 5, chunks_added: 137, store_total: 412}
```

## 6. Búsqueda híbrida (`semantic_search` modo `hybrid`)

```
LLM
    │  semantic_search(query="día de Jehová", top_k=5, mode="hybrid")
    ▼
[jw-mcp] semantic_search → store.hybrid_search()
    │
    │  Vector search (candidate_pool=50):
    │     embedder.embed([query]) → vector (1, dim)
    │     l2_normalize
    │     similitud = self._vectors @ qvec   ← cosine == dot product (vectores normalizados)
    │     argpartition + argsort → top-50 índices ordenados
    │     → vec_hits: 50 SearchHit con source="vector"
    │
    │  BM25 search (candidate_pool=50):
    │     _tokenize(query) → tokens
    │     self._bm25.get_scores(tokens) → scores
    │     argpartition + argsort
    │     → bm25_hits: 50 SearchHit con source="bm25"
    │
    │  Reciprocal Rank Fusion:
    │     fused = {}
    │     for hit in vec_hits + bm25_hits:
    │         contribution = 1 / (rrf_k + hit.rank)    # rrf_k=60
    │         fused[hit.chunk.id] += contribution
    │     ordered = sorted(fused.items(), key=-score)
    │     → top_k SearchHit con source="hybrid"
    ▼
[
  {rank: 1, score: 0.034, source: "hybrid",
   chunk_id: "article:...#3",
   text: "El día de Jehová se acerca…",
   metadata: {kind: "article", title: "...", source_url: "..."}},
  ...
]
```

## 6b. GET wrapped con Fase 9 (`politely_get`)

```
Cliente.search("amor", language="S")
    │
    │  url = "https://b.jw-cdn.org/apis/search/results/S/all"
    │  params = {"q": "amor"}
    │  await auth.authorized_headers()    ← JWTManager (cached + lock)
    ▼
politely_get(http, url, params, headers,
             throttler=THROTTLER, cache=CACHE, telemetry=TELEMETRY,
             endpoint_id="cdn.search", cache_ttl_seconds=900,
             record_json_shape=True)
    │
    │  ┌─ Cache check ──────────────────────────┐
    │  │  cache_key = f"GET {url}?{sorted_params_json}"
    │  │  hit = cache.get(cache_key)
    │  │  if hit: return synthetic 200 con body cached
    │  └─────────────────────────────────────────┘
    │
    │  ┌─ Throttle ──────────────────────────────┐
    │  │  host = urlparse(url).hostname  = "b.jw-cdn.org"
    │  │  await throttler.acquire(host)  ← TokenBucket espera si no hay token
    │  └─────────────────────────────────────────┘
    │
    │  resp = await http.get(url, params, headers)
    │
    │  ┌─ Cache set (status 200) ────────────────┐
    │  │  cache.set(cache_key, resp.content, ttl_seconds=900)
    │  └─────────────────────────────────────────┘
    │
    │  ┌─ Telemetry (si record_json_shape y JSON) ┐
    │  │  shape = _shape_hash(resp.json())
    │  │  drift = telemetry.record("cdn.search", shape)
    │  │  if drift: WARN "API drift on cdn.search: shape changed"
    │  └─────────────────────────────────────────┘
    ▼
resp → JSON → truncate to limit → devuelve dict
```

Cuando los 3 deps están `None` (default), todo se degrada a un `http.get()` plano. **El "modo Fase 9" es opt-in**; usar `factory.build_clients()` lo activa de un golpe.

## 6c. Descifrado JWPUB (Fase 5.5)

```
parse_jwpub("ti_E.jwpub")
    │
    │  zipfile.ZipFile(path)
    │     manifest.json → parse JSON
    │     contents       → bytes del ZIP interno
    ▼
_compute_key_iv(language_index, symbol, year, issue_tag_number)
    │
    │  pub_string = "0_ti_1989"             ← ejemplo Trinity brochure
    │  digest     = SHA256(pub_string)       (32 bytes)
    │  material   = digest XOR _XOR_KEY     (constante magic 32-byte)
    │  key = material[:16]    iv = material[16:32]
    ▼
ZipFile(contents).read("ti_E.db") → SQLite bytes
    │
    │  sqlite3.connect(tmp) → SELECT Content FROM Document
    ▼
Para cada row:
    │  ciphertext = row["Content"]
    │  padded     = AES-128-CBC(key, iv).decryptor.decrypt(ciphertext)
    │  text_bytes = zlib.inflate(strip_pkcs7(padded))
    │  text       = text_bytes.decode("utf-8")
    │
    │  paragraphs = BeautifulSoup(text).find_all("p[data-pid]")
    ▼
JwpubMetadata(documents=[JwpubDocument(text="<xhtml>...", paragraphs=[...])])
```

Si una row individual falla (formato variante raro), se salta silenciosamente — `decrypted_text_available` queda True si al menos UNA tuvo éxito.

## 7. Conexión Claude Desktop → MCP server

```
Claude Desktop arranca
    │
    │  Lee ~/Library/Application Support/Claude/claude_desktop_config.json
    │  → {"mcpServers": {"jw": {"command": "uv", "args": [...]}}}
    │
    │  Spawn proceso: uv --directory /path run jw-mcp
    ▼
[jw-mcp.server.main]
    │
    │  logger.info("Starting jw-agent-toolkit MCP server")
    │  mcp = FastMCP("jw-agent-toolkit")
    │  mcp.run()    ← entra en loop stdio
    ▼
Stdio loop:
    │
    │  Cliente envía: list_tools → MCP responde con las 24 tools
    │  Cliente envía: call_tool(name="resolve_reference", args={text:..., language:...})
    │  → ejecuta el handler decorado con @mcp.tool
    │  → devuelve dict como JSON-RPC response
```

Los clientes (`WOLClient`, `CDNClient`, etc.) se crean **lazy** la primera vez que se usan (`_get_wol()` etc.) y comparten un `httpx.AsyncClient` cuando sea posible.

El store RAG se inicializa lazy desde `JW_RAG_STORE_PATH` (default `~/.jw-agent-toolkit/rag/`) con `FakeEmbedder(dim=64)` por defecto.
