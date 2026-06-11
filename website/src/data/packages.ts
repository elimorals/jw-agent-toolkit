export type PackageColor = "cyan" | "warm" | "neutral" | "violet" | "amber" | "green";

export interface PackageInfo {
  slug: string;
  name: string;
  tagline: string;
  short: string;
  about: string;
  color: PackageColor;
  highlights: string[];
  features: { title: string; body: string }[];
  install: string;
  usage: { language: string; code: string; caption?: string };
  dependsOn: string[];
  exports: string[];
  referenceHref: string;
  guideHref?: string;
}

export const packages: PackageInfo[] = [
  {
    slug: "jw-core",
    name: "jw-core",
    tagline: "El núcleo determinístico",
    color: "cyan",
    short:
      "Librería principal: 6 clientes HTTP, 10 parsers, writers JWPUB/.jwlibrary, 6 providers ASR (Omnilingual 1672 idiomas + whisperX diarizado), NLLB-200, schemas organized-app, voiceprints, infra F9 + multimodal end-to-end (talk-lab F68, broadcasting/visual F69, image-quote F70, book-camera F71), drift diacrónico F72 y voz familiar consentida F76.",
    about:
      "El corazón del toolkit. Todo lo demás depende de jw-core, y jw-core no depende de nada del workspace. Aquí viven los clientes HTTP que hablan con jw.org, los parsers determinísticos que convierten HTML/JSON/EPUB/JWPUB en modelos Pydantic, los writers que generan .jwpub y .jwlibrary nativos para JW Library, los providers de ASR (Deepgram, Whisper, Omnilingual 1672 idiomas via venv Python 3.12, whisperX diarizado F64) y traducción (NLLB-200 CC-BY-NC con preservación de refs), los schemas Pydantic de sws2apps/organized-app, el voiceprint store opt-in (F64.7) y la infraestructura compartida: cache SQLite con TTL, throttle por host, telemetría opt-in y autenticación JWT.",
    highlights: [
      "6 clientes · 10 parsers · 3 writers · 17 locales",
      "ASR 1672 idiomas + whisperX diarizado",
      "Multimodal: talk-lab · visual index · image-quote · book-camera",
      "Voz familiar consentida + Fernet opt-in",
    ],
    features: [
      {
        title: "Clientes HTTP",
        body: "CDNClient (búsqueda + JWT), WOLClient (capítulos, texto diario, fetch arbitrario, cross-refs), MediatorClient (idiomas + finder), PubMediaClient (descargas), TopicIndexClient (guía de investigación), WeblangClient (catálogo de idiomas). Todos opcionalmente con cache + throttle + telemetría.",
      },
      {
        title: "Parsers + Writers determinísticos",
        body: "Parsers: parse_reference (multiidioma), Article, DailyText, Verse, StudyNote + CrossReference, TopicIndex, Epub, JWPUB descifrado (F5.5), .jwlibrary backup (F19) y wol_url (F58.4: BibleRef.from_wol_url, port del lado JS F56.5). Writers: jwpub builder (F50, simétrico al descifrador) y jw_library_backup writer (F52, cierra el read-write loop con JW Library nativo).",
      },
      {
        title: "Modelos Pydantic + schemas organized-app",
        body: "Modelos propios: BibleRef · Verse · StudyNote · Article · Epub · JwpubMetadata · LanguageMetadata. F51 portó verbatim los schemas de sws2apps/organized-app (MIT) — PersonType, SchedWeekType, WeekType, AssignmentCode, MeetingAttendanceType, FieldServiceGroupType, UserFieldServiceMonthlyReportType — con envelope CRDT Timestamped[T].",
      },
      {
        title: "Audio: ASR + TTS multi-provider (F34 + F53 + F64)",
        body: "ASR providers con auto-routing por idioma: Deepgram (~16 idiomas, streaming), faster-whisper (local), Omnilingual ASR (1672 idiomas via venv Python 3.12 dedicado, F53), whisperX (F64, word-level timestamps + diarización pyannote, opt-in via extras [asr-whisperx]). DiarizedSegment + DiarizedResult extienden TranscriptionResult sin breaking. Speakers (F64.7): VoiceprintStore sqlite con Fernet opt-in JW_VOICEPRINT_KEY + SpeakerNameMapper cosine sim — mapea speaker_id → nombre real opt-in. TTS: Kokoro · Edge · System · ElevenLabs · Piper · XTTSv2 · F5. Routers F55.1 escogen el mejor disponible.",
      },
      {
        title: "Traducción NLLB-200 con preservación de refs (F54)",
        body: "translate_preserving_references() enmascara cada cita bíblica antes del modelo y la restaura en el idioma destino — cero alucinación numérica. NLLBProvider con CTranslate2 INT8 (200 idiomas, CC-BY-NC). is_commercial_safe=False chequeable a runtime; el router F55.1 filtra estructuralmente.",
      },
      {
        title: "Infraestructura Fase 9 + crypto compartido",
        body: "DiskCache (SQLite + TTL + WAL) · TokenBucket throttle · Telemetry opt-in · JWTManager · factory unificado de clientes. F50 añadió jwpub_crypto: XOR_KEY, compute_key_iv, encrypt_blob (nuevo), decrypt_blob — una sola fuente de verdad compartida por parser y writer JWPUB.",
      },
      {
        title: "Multimodal end-to-end (F68 talk-lab · F69 broadcasting/visual · F70 image-quote · F71 book-camera)",
        body: "talk_lab/: coach de oratoria local-first con WhisperX F64 + prosodia + 6 counsel points TOML es/en/pt, SVG timeline (report_to_svg) y F31 PDF export (talklab_to_studysheet + export_talk_lab_pdf). broadcasting/visual/: sampler de frames + VLM captioning + CLIP + RRF + OCR de frames vía F70 (enrich_frames_with_ocr). verification/image_quote/: VLM + OCR + RAG + NLI F39 con default_rag_retriever (env JW_IMAGE_QUOTE_STORE_PATH) y default_nli adapter sobre F39; engine.use_real_defaults=True. book_camera/: classifier procedural (verse / question / Watchtower paragraph / plain) + suggested_actions (read_aloud/open_in_jw_library/open_in_wol/show_answer).",
      },
      {
        title: "ML predictivo + voz familiar (F72 doctrinal-drift · F76 family-voice-clone)",
        body: "drift/: análisis diacrónico con partition_by_era + DBSCAN cosine en numpy puro + cluster_alignment + significance (minor/moderate/major). Nota Prov 4:18 trilingüe SIEMPRE inyectada. Wire-up F49 Second Brain con chunks_from_brain() y SVG drift timeline (drift_to_svg). audio/voice_clone/: TTS con voz familiar consentida + license gate 3 capas (deny list nombres + consent activo + non-commercial 5 regex) + FakeVoiceProvider determinista. Cifrado opt-in Fernet en encryption.py (JW_VOICE_KEY): encrypt_weights / decrypt_to_tempfile / generate_key. Audit hook emit_trace=fn compatible F43.",
      },
    ],
    install: "uv sync --package jw-core",
    usage: {
      language: "python",
      caption: "Resolver una cita y obtener su URL canónica en wol.jw.org.",
      code: `from jw_core import parse_reference

ref = parse_reference("Juan 3:16")
ref.display()             # 'John 3:16'
ref.wol_url(lang="es")    # 'https://wol.jw.org/es/wol/b/r4/...'
ref.book.code             # 'JHN'
ref.chapter, ref.verses   # (3, [16])`,
    },
    dependsOn: [],
    exports: [
      "parse_reference · translate_preserving_references",
      "BibleRef · Verse · StudyNote · CrossReference",
      "parsers.wol_url.parse_wol_url · BibleRef.from_wol_url",
      "CDNClient · WOLClient · MediatorClient · PubMediaClient",
      "writers.jwpub.JwpubBuilder · writers.jw_library_backup.write_backup",
      "audio.transcription.get_asr_provider · OmnilingualProvider · WhisperXProvider",
      "audio.speakers.VoiceprintStore · SpeakerNameMapper · DiarizedSegment",
      "audio.voice_clone.{synthesize_with_voice, registry, encryption.{encrypt_weights, decrypt_to_tempfile}}",
      "talk_lab.{analyze_recording, svg.report_to_svg, pdf_export.export_talk_lab_pdf}",
      "broadcasting.visual.{indexer, search.hybrid_search, ocr_frame.enrich_frames_with_ocr}",
      "verification.image_quote.{verify_image_quote, factories.{default_rag_retriever, default_nli}}",
      "book_camera.{analyze_capture, classify_content}",
      "drift.{analyze_doctrinal_drift, brain_source.chunks_from_brain, svg.drift_to_svg}",
      "translation_providers.get_translation_provider · NLLBProvider",
      "models_organized.PersonType · SchedWeekType · WeekType",
      "DiskCache · Throttler · Telemetry · JWTManager",
    ],
    referenceHref: "/docs/referencia/jw-core",
    guideHref: "/docs/guias/usar-clientes-http",
  },
  {
    slug: "jw-cli",
    name: "jw-cli",
    tagline: "Terminal para mortales",
    color: "warm",
    short:
      "CLI Typer + Rich con 13+ comandos top-level (verse · search · daily · download · jwpub build · library · omnilingual · translate · transcribe · …). Wrapper directo sobre jw-core con output Rich o JSON.",
    about:
      "Construida con Typer + Rich para que cualquier usuario que sepa abrir un terminal pueda usar el toolkit sin escribir Python. Cada comando es un wrapper directo sobre los métodos de jw-core, con output legible o pipeable a otras herramientas Unix. Tras F55, los subcomandos cubren todo el workflow multilingüe: generar publicaciones nativas, escribir backups de JW Library, transcribir en 1672 idiomas y traducir preservando refs bíblicas.",
    highlights: [
      "13+ comandos: verse · search · daily · …",
      "F55: jw jwpub build · library · omnilingual · translate",
      "Typer + Rich · 7 idiomas",
      "Output JSON con --json",
    ],
    features: [
      {
        title: "Comandos top-level (13+)",
        body: "Núcleo: jw verse · search · daily · download · languages · chapter · jwpub inspect · topic. F55 multilingüe: jw jwpub build (empaquetar HTML+media como .jwpub), jw library {inspect, re-export, from-notes} (escribir .jwlibrary), jw omnilingual {install, status, transcribe, supports} (1672 idiomas), jw translate (NLLB con preservación refs), jw transcribe (router automático).",
      },
      {
        title: "Output bonito o legible-por-máquinas",
        body: "Por defecto, panels y tablas Rich con colores. Con --json devuelve el modelo Pydantic serializado para encadenar con jq, fzf o cualquier pipeline.",
      },
      {
        title: "Multiidioma",
        body: "Auto-detecta idioma de la cita ('Juan 3:16' → es, 'John 3:16' → en) o lo fuerzas con --lang. Soporta 7 idiomas tier-1: en, es, pt, fr, de, it, ru.",
      },
      {
        title: "Sin red en CI",
        body: "Los tests de la CLI corren contra cassettes pytest-recording — cero llamadas a jw.org en pipelines.",
      },
    ],
    install: "uv tool install jw-cli",
    usage: {
      language: "bash",
      caption: "Workflow típico: buscar, leer y descargar.",
      code: `# Resolver una cita
jw verse "Juan 3:16" --lang es

# Buscar contenido
jw search "amor" --type article | head -20

# Texto diario de hoy
jw daily

# Descargar una publicación
jw download w23 --lang es --format epub

# Pipe a otra herramienta
jw search "fe" --json | jq '.results[].title'`,
    },
    dependsOn: ["jw-core"],
    exports: [
      "verse · search · daily · download",
      "chapter · languages · jwpub · topic",
      "Flags: --lang · --json · --output · --format",
    ],
    referenceHref: "/docs/referencia/jw-cli",
    guideHref: "/docs/guias/resolver-citas-biblicas",
  },
  {
    slug: "jw-mcp",
    name: "jw-mcp",
    tagline: "Puente con tu agente",
    color: "violet",
    short:
      "Servidor Model Context Protocol que expone ~135 herramientas a Claude Desktop, Claude Code o cualquier cliente MCP. Cubre F57-F76: meeting, brain, ingest, ASR diarizado, memoria, meta-orchestrator, sparring, reasoner, talk-lab, broadcasting visual, book-camera (con REST endpoints), drift, voice-clone.",
    about:
      "El componente que convierte el toolkit en algo que tu agente de IA puede usar. Implementado con FastMCP, expone cada parser y cliente de jw-core (más el RAG, los agentes, el second-brain F49+F66, los loaders externos F62, la memoria persistente F61, el ASR diarizado F64, la reunión-en-vivo F57 y toda la capa F65-F76 agéntica + multimodal + predictivo + voz familiar consentida) como tools accesibles vía el protocolo MCP estándar. Funciona sobre stdio para Claude Desktop/Code o sobre SSE para otros clientes. F71 añade además REST endpoints opt-in mountables sobre FastAPI: jw_mcp.rest.book_camera.router expone POST /api/v1/book_camera/{analyze, tts, rag_answer}.",
    highlights: [
      "~135 tools sobre stdio MCP",
      "FastMCP · Claude/IDE compatible",
      "RAG + agentes + brain + meeting + agéntica F65-F76",
      "REST opt-in book-camera (/analyze /tts /rag_answer)",
    ],
    features: [
      {
        title: "~135 herramientas registradas",
        body: "resolve_reference · get_chapter · get_daily_text · search_content · get_article · get_verse · get_study_notes · get_cross_references · compare_translations · list_languages · download_publication · jwpub_extract · topic_subjects · ... más 5 finetune tools.",
      },
      {
        title: "F57-F66 tools (16 nuevas)",
        body: "second_brain_status/query/compile/lint/snapshot (F49+F66) · ingest_pdf + ingest_office_doc (F62) · transcribe_audio_diarized (F64) · memory_record/recall/forget_session + recap_previous_session (F61+F61.8) · meeting_discover_week/download_media/list_programs/open_presenter/list_congregations/add_congregation (F57+F57.16). Plus drift fix _EXPECTED_TOOLS (get_trace F43 + translate_preserving_refs F54).",
      },
      {
        title: "F65-F76 tools (15+ nuevas) + REST endpoints",
        body: "Meta-orchestrator F65: meta_plan/run/replay. Sparring F66: spar_personas/start/turn/close (memoria SQLite cross-process opt-in). Reasoner F67: doctrinal_reason. Talk-lab F68: talklab_analyze + history/compare. Broadcasting visual F69: visual_index + visual_search. Image-quote F70: verify_image_quote. Book-camera F71: book_camera_analyze + REST jw_mcp.rest.book_camera.router (POST /api/v1/book_camera/{analyze,tts,rag_answer} — opt-in via APIRouter.include_router). Drift F72: drift_analyze. Voice-clone F76: voice_clone_list/synthesize/audit (license gate 3 capas + Fernet opt-in via JW_VOICE_KEY).",
      },
      {
        title: "Agentes high-level",
        body: "verse_explainer · research_topic · meeting_helper · apologetics. Cada uno orquesta múltiples llamadas y devuelve findings citables.",
      },
      {
        title: "RAG global",
        body: "El único componente que liga el RAG: search_corpus busca sobre todo el contenido indexado (Biblia + artículos + EPUB + JWPUB) con BM25 + vector + RRF.",
      },
      {
        title: "Setup en Claude Desktop",
        body: "Una entrada en claude_desktop_config.json apuntando a 'uv run jw-mcp'. Reinicia Claude Desktop y ya tienes 100+ tools nuevas en tus conversaciones.",
      },
    ],
    install: "uv sync --package jw-mcp && uv run jw-mcp",
    usage: {
      language: "json",
      caption: "claude_desktop_config.json (macOS: ~/Library/Application Support/Claude/).",
      code: `{
  "mcpServers": {
    "jw": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/jw-agent-toolkit",
        "run",
        "jw-mcp"
      ]
    }
  }
}`,
    },
    dependsOn: ["jw-core", "jw-rag", "jw-agents"],
    exports: [
      "~135 MCP tools sobre stdio",
      "Resources: file://jw/...",
      "Agentes: verse_explainer · research_topic · ...",
      "RAG: search_corpus con BM25 + vector + RRF",
      "Brain: second_brain_* · Meeting: meeting_*",
      "Memory: memory_record/recall + recap_previous_session",
      "Meta F65: meta_plan/run/replay · Sparring F66: spar_*",
      "Reasoner F67 · Talk-lab F68 · Visual F69 · Image-quote F70",
      "Book-camera F71 + REST jw_mcp.rest.book_camera.router",
      "Drift F72 · Voice-clone F76 (license gate + Fernet opt-in)",
    ],
    referenceHref: "/docs/referencia/jw-mcp",
    guideHref: "/docs/guias/conectar-mcp-a-claude-desktop",
  },
  {
    slug: "jw-rag",
    name: "jw-rag",
    tagline: "Recuperación híbrida",
    color: "green",
    short:
      "Indexación vectorial + búsqueda híbrida BM25 + cosenos + Reciprocal Rank Fusion. Sobre Biblia, publicaciones, EPUB y JWPUB descifrados.",
    about:
      "El componente de recuperación. Indexa cualquier fuente de jw-core (capítulos bíblicos, artículos WOL, EPUBs descargados, JWPUBs descifrados) y los hace buscables por similitud semántica + keyword. La fusión RRF combina los rankings sin perder relevancia ni precisión.",
    highlights: [
      "BM25 + vector + RRF",
      "Sync incremental por source_id",
      "Embeddings configurables",
      "SQLite + sqlite-vec por defecto",
    ],
    features: [
      {
        title: "Stores intercambiables",
        body: "VectorStore (sqlite-vec por defecto, también soporta Pinecone/Qdrant/Chroma) y BM25Store (sqlite FTS5). Composición vía HybridStore.",
      },
      {
        title: "Ingesta unificada",
        body: "ingest_bible_chapters, ingest_articles, ingest_epub, ingest_jwpub. Todos producen Chunks con source_id para delete incremental.",
      },
      {
        title: "Loaders externos (F62)",
        body: "pdf_marker.ingest_pdf con marker-pdf (Apache-2.0, ~9 GB modelos opt-in via JW_MARKER_USE_GPU/JW_MARKER_USE_LLM) para Atalayas históricas escaneadas. docs_markitdown.ingest_office_doc (MIT) para .docx/.pptx/.xlsx compartidos en hermandad. Idempotencia sha256 con source_id pdf:<hash8> y doc:<ext>:<hash8>. JW signature regex (watch tower|jw.org|atalaya|kingdom hall) marca metadata.is_jw=True. Opt-in via extras [pdf-marker], [doc-markitdown], [loaders-all].",
      },
      {
        title: "Reciprocal Rank Fusion",
        body: "Combina ranking de BM25 con ranking vectorial usando RRF (k=60 por defecto). Mejor que pesos lineales en boundaries de relevancia.",
      },
      {
        title: "Sync incremental",
        body: "delete_by_source_ids permite re-indexar solo lo que cambió en jw.org sin reconstruir todo el corpus.",
      },
    ],
    install: "uv sync --package jw-rag",
    usage: {
      language: "python",
      caption: "Indexar Juan completo y buscar.",
      code: `from jw_rag import HybridStore, ingest_bible_book

store = HybridStore.open("./jw-corpus.db")

# Indexar
await ingest_bible_book(
    store, book="JHN", lang="es",
)

# Buscar
results = store.search(
    "amor incondicional de Dios",
    top_k=5, fusion="rrf",
)
for r in results:
    print(r.score, r.chunk.text[:80])`,
    },
    dependsOn: ["jw-core"],
    exports: [
      "HybridStore · VectorStore · BM25Store",
      "Chunk · SearchResult",
      "ingest_bible_book · ingest_article · ingest_epub · ingest_jwpub",
      "ingest_pdf (marker) · ingest_office_doc (markitdown)",
      "fusion: rrf · linear · max",
    ],
    referenceHref: "/docs/referencia/jw-rag",
    guideHref: "/docs/guias/indexar-y-buscar-con-rag",
  },
  {
    slug: "jw-agents",
    name: "jw-agents",
    tagline: "Orquestación multipaso + agéntica verificable",
    color: "amber",
    short:
      "Agentes procedurales determinísticos + meta-orchestrator F65 con planner+critic NLI, conversation-sparring F66 con 6 personas y doctrinal-reasoner F67 con ReAct + golden set. Sin LLM en el camino crítico.",
    about:
      "Agentes hechos a mano, no LLM-orchestrated. Cada uno orquesta múltiples llamadas a jw-core + jw-rag para producir findings estructurados con citas verificables a wol.jw.org. La síntesis del lenguaje natural ocurre fuera del toolkit (Claude Desktop, Claude Code, tu propio cliente). F65-F67 añaden una capa agéntica verificable: el meta-orchestrator decompone objetivos en DAGs de tools, ejecuta en orden topológico y crítica con NLI F39 antes de devolver; conversation-sparring simula 6 personas para práctica de predicación; doctrinal-reasoner emite chain-of-thought con árbol de pruebas exportable.",
    highlights: [
      "4 agentes procedurales + meta-orchestrator",
      "Conversation sparring · 6 personas",
      "Reasoner ReAct con NLI crítico",
      "Sin LLM en camino crítico",
    ],
    features: [
      {
        title: "verse_explainer",
        body: "Dada una cita bíblica, devuelve el versículo objetivo + notas de estudio nwtsty mapeadas + cross-references panel (lazy). 100% matching headword↔versículo desde Fase 3.5.",
      },
      {
        title: "research_topic",
        body: "Dado un tema en lenguaje natural, busca en TopicIndex (Guía de Investigación) y devuelve subjects/subheadings/citations estructurados.",
      },
      {
        title: "meeting_helper",
        body: "Dada una URL del Workbook o una ref bíblica, prepara material para reunión semanal: outline, citas, sugerencias de discusión.",
      },
      {
        title: "apologetics",
        body: "Dada una objeción común ('Trinidad', 'infierno', 'Biblia se contradice'), devuelve respuesta estructurada con citas bíblicas + notas de estudio + texto enriquecido.",
      },
      {
        title: "Memoria persistente opt-in (F61)",
        body: "MemoryStore Protocol + 3 backends: FakeMemoryStore (in-memory, default tests), SqliteMemoryStore (default user, Fernet opt-in via JW_MEMORY_KEY siguiendo precedente F25 RevisitStore), LettaMemoryStore (opt-in para multi-device via letta-client, extra [memory-letta]). conversation_assistant ahora acepta param memory: MemoryStore | None — preserva compat 100% (memory=None → comportamiento legacy). build_memory_store() factory env-driven.",
      },
      {
        title: "Auto-recap entre sesiones (F61.8)",
        body: "Agente nuevo recap_session.recap_previous_session() NO usa LLM (decisión arquitectónica: procedural y determinístico). Agrupa records de MemoryStore por session_id, filtra la sesión actual, ordena por last_timestamp desc, devuelve findings con summary corto + excerpts_by_kind en metadata. Útil al arrancar nueva sesión: 'continuemos con la sesión X de ayer'.",
      },
      {
        title: "Meta-orchestrator (F65)",
        body: "Planner LLM con JSON-schema validation + executor topológico + critique NLI F39 con replan opt-in. Reusa Plugin SDK F41 y los 12 adapters reales en builtin_tools.py. Factories LLM (Anthropic + Ollama + Fake) y NLI env-driven con degradación grácil. Tracing F43 via tracer= opt-in. Persistencia --save-plan/--save-result JSON + replay determinista con MetaOrchestrator.run_plan(plan). Export Mermaid del DAG (plan_to_mermaid + result_to_mermaid). CLI jw meta {tools,plan,run,replay} + --mermaid + jw plan-sunday.",
      },
      {
        title: "Conversation sparring (F66)",
        body: "Simulador de interlocutor para predicación: 6 personas (atheist · jw_student · biblical_scholar · evangelical · agnostic · returning) × 3 idiomas en 18 TOMLs con resolución multi-idioma. Voice mode jw spar voice-turn (ASR → LLM → TTS, audio nunca sale del disco). Persistencia SQLite cross-process en spar/persistence.py + autosave opt-in JW_SPAR_PERSIST=1. Markdown export del transcript. Golden conversations con FakeSparLLM determinista. Tool spar.session para uso desde el meta-orchestrator F65.",
      },
      {
        title: "Doctrinal reasoner (F67)",
        body: "Chain-of-thought verificable: reformulator de framing tóxico (12 patrones es/en/pt) + planner Jinja2 multi-idioma + ReAct executor con NLI F39 (modes off/warn/reject). Tool dispatcher real wireado a verse_explainer/research_topic/apologetics/life_topics (use_real_dispatcher=True). Golden set 10 preguntas multi-paso en fixtures/golden.jsonl. Summary prose determinista trilingüe. CLI jw reason {ask,languages} + MCP doctrinal_reason. Integrado en F65 como reason.doctrinal.",
      },
    ],
    install: "uv sync --package jw-agents",
    usage: {
      language: "python",
      caption: "Resolver y enriquecer una cita con notas de estudio.",
      code: `from jw_agents import verse_explainer

result = await verse_explainer.run(
    "Juan 3:16", lang="es",
)
for f in result.findings:
    print(f.kind, f.verse_ref, f.url)

# Output:
# verse Juan 3:16 https://wol.jw.org/es/.../3:16
# study_note Juan 3:16 https://wol.jw.org/es/.../sn-3-16
# cross_ref Juan 3:16 https://wol.jw.org/es/.../bc-...`,
    },
    dependsOn: ["jw-core", "jw-rag"],
    exports: [
      "verse_explainer · research_topic",
      "meeting_helper · apologetics",
      "Finding · AgentResult",
      "memory.MemoryStore · SqliteMemoryStore · LettaMemoryStore",
      "build_memory_store · recap_session.recap_previous_session",
      "meta.MetaOrchestrator · meta.mermaid (plan_to_mermaid / result_to_mermaid)",
      "spar.{SparSession, FakeSparLLM, persistence.save_session/load_session}",
      "reasoner.{Engine, dispatchers.real_tool_dispatcher}",
      "Composición con agent_pipeline",
    ],
    referenceHref: "/docs/referencia/jw-agents",
    guideHref: "/docs/guias/construir-un-agente",
  },
  {
    slug: "jw-finetune",
    name: "jw-finetune",
    tagline: "Tu modelo, tus datos",
    color: "neutral",
    short:
      "Plataforma local estilo Unsloth Studio: extrae JWPUB/EPUB, genera Q&A sintéticos, entrena LoRA y exporta a GGUF/MLX. Sin distribuir pesos.",
    about:
      "Diseñado como plataforma local — cada usuario entrena su propio modelo con sus propias publicaciones legalmente obtenidas. Los pesos nunca se distribuyen desde este repositorio. Pipeline completo de 5 fases que reutiliza los parsers y chunker de jw-core para extraer Q&A reales o sintetizados.",
    highlights: [
      "Extract → Synth → Train → Export",
      "Unsloth · LoRA · GGUF · MLX",
      "Textual TUI + WebSocket monitor",
      "GPU opt · async-synth · cache",
    ],
    features: [
      {
        title: "Extracción",
        body: "JWPUB descifrado · EPUB · Atalaya study questions · workbooks · study notes · objections · topics · library backup. Q&A reales extraídos cuando aplique (preset synth_provider=None), sintéticos cuando no.",
      },
      {
        title: "Recetas y CLI",
        body: "11 comandos: data, recipes, train, eval, export, monitor, mcp, studio, doctor, diff, progress. 3 presets out-of-the-box optimizados para Apple Silicon, NVIDIA y CPU.",
      },
      {
        title: "Stack Unsloth",
        body: "chat-template · train-responses-only · rsLoRA · multi-quant (Q4_K_M, Q5_K_M, Q8_0) · model-cache · GRPO/RL agents opcional.",
      },
      {
        title: "Observabilidad",
        body: "WebSocket monitor para training en vivo · Textual TUI (jw-finetune tui-wizard, tui-monitor) · Studio web UI para review de datasets · sample diff entre runs.",
      },
      {
        title: "Composición agéntica",
        body: "El modelo finetuned se integra con jw-agents vía agent_pipeline: enricher procedural primero (jw-core/jw-rag) + fine-tuned después. Lo mejor de ambos.",
      },
    ],
    install: "uv sync --package jw-finetune",
    usage: {
      language: "bash",
      caption: "Pipeline mínimo: dataset → entrenamiento → export.",
      code: `# 1. Extraer dataset desde tus JWPUBs
jw-finetune data extract \\
  --source ./mis-jwpub \\
  --preset apple-silicon

# 2. Entrenar
jw-finetune train \\
  --recipe lora-q4 \\
  --dataset ./datasets/extracted

# 3. Evaluar
jw-finetune eval \\
  --model ./runs/latest \\
  --suite parse_reference,embed-sim

# 4. Exportar GGUF
jw-finetune export gguf \\
  --quant Q4_K_M --quant Q5_K_M`,
    },
    dependsOn: ["jw-core"],
    exports: [
      "11 CLI commands · 5 fases",
      "Extractors: jwpub · epub · watchtower · workbook · ...",
      "Recipes: lora-q4 · lora-q5 · qlora · grpo",
      "Exports: GGUF · MLX · HF Hub",
    ],
    referenceHref: "/docs/guias/fine-tuning-local",
    guideHref: "/docs/guias/fine-tuning-local",
  },
  {
    slug: "jw-eval",
    name: "jw-eval",
    tagline: "Red de seguridad doctrinal",
    color: "amber",
    short:
      "Suite de evaluación con regresión: 3 capas (estructural, citas, semántico) que gating cada PR contra 47 golden Q&A. Convierte 'confío en mí' en métrica.",
    about:
      "Construido en la Fase 22 — la última en ser implementada porque sirve para medir todas las demás. Tres capas independientes: L1 verifica el contrato estructural de cada agente (sin red, sin LLM, bloqueante en CI); L2 valida que cada URL emitida resuelva y respalde su afirmación (snapshot offline + live weekly); L3 compara la respuesta del agente contra una respuesta dorada via sentence-transformers + escalada a Ollama/Claude cuando el score cae en zona ambigua (0.55–0.78). Cada nueva fase debe añadir ≥3 golden cases al merge.",
    highlights: [
      "47 golden cases · 6 agentes",
      "L1 estructural · L2 citas · L3 semántico",
      "Embeddings + LLM judge híbrido",
      "Snapshots offline en CI · live weekly",
    ],
    features: [
      {
        title: "Capa 1 — Estructural",
        body: "Verifica que cada agente devuelva la forma esperada: tipos de fuente (topic_index, verse_text, etc.), número mínimo de findings, orden de prioridad, presencia de citation_metadata, keywords prohibidas. 100% determinista, sin red, sin LLM. Bloquea CI si <100%.",
      },
      {
        title: "Capa 2 — Citas",
        body: "Modo snapshot (siempre activo): HTML congelado en fixtures/wol_snapshots/ valida que las URLs producidas existan y contengan el texto que sustenta la cita. Modo live (cron weekly): re-descarga, compara fingerprint y abre issues de drift automáticamente.",
      },
      {
        title: "Capa 3 — Semántico",
        body: "sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) calcula cosine entre la respuesta del agente y la respuesta dorada. Threshold 0.78 pasa, <0.55 falla, en medio escala a LLM judge (Ollama default / Claude / OpenAI vía env JW_EVAL_LLM).",
      },
      {
        title: "47 Golden Cases",
        body: "25 L1 + 13 L2 + 9 L3 cubriendo apologetics, verse_explainer, research_topic, meeting_helper, conversation_assistant, life_topics, study_conductor, news_monitor, student_part_helper, letter_composer. Política: cada nueva fase añade ≥3 al merge.",
      },
      {
        title: "Integración CI",
        body: "Tres jobs nuevos: eval-fast (L1+L2 offline, bloquea PRs), eval-l2-live (weekly cron, abre issues de drift), eval-nightly (L1+L2+L3 con Ollama, no bloquea). Reporte markdown + JSON; tool MCP run_eval_suite expuesto para clientes externos.",
      },
    ],
    install: "uv sync --package jw-eval",
    usage: {
      language: "bash",
      caption: "Correr la suite localmente y filtrar por agente.",
      code: `# L1+L2 offline (rápido, bloqueante en CI)
uv run jw eval --layer 1,2

# L1+L2+L3 con LLM judge Ollama
JW_EVAL_LLM=ollama uv run jw eval --layer 1,2,3

# Filtrar por agente
uv run jw eval --filter-agent apologetics

# Modo live (red real)
uv run jw eval --layer 2 --live

# Reporte a archivo
uv run jw eval --report md --out report.md`,
    },
    dependsOn: ["jw-core", "jw-rag", "jw-agents"],
    exports: [
      "Suite · GoldenCase · LayerResult · SuiteReport",
      "evaluate_structural · evaluate_citations · evaluate_semantic",
      "EmbeddingsJudge · LLMJudge (Ollama/Claude/OpenAI)",
      "47 golden cases (L1+L2+L3) · 6 agentes",
    ],
    referenceHref: "/docs/guias/eval-doctrinal",
    guideHref: "/docs/guias/eval-doctrinal",
  },
  {
    slug: "jw-gen",
    name: "jw-gen",
    tagline: "Generación con difusión, uso personal",
    color: "violet",
    short:
      "Octavo paquete del monorepo. Genera imagen / audio / video para presentaciones y discursos personales. Watermark obligatorio + metadata EXIF/XMP + safety filters anti-emulación-JW-oficial.",
    about:
      "Construido en la Fase 38 con política LOAD-BEARING: cada output a disco pasa por watermark + EXIF/XMP + disclaimer.txt sibling. Tres safety filters no-negociables: anti-logos-JW, voice-cloning con doble opt-in, realistic-faces stylized por defecto. MCP tool fuerza watermark=True silenciosamente — un cliente remoto no puede desactivarlo. Audit log guarda sha256(prompt), nunca prompt en claro. Property test con 100 prompts adversariales detectó (y corrigió) un bypass real durante desarrollo: 'Despertai logo'.",
    highlights: [
      "Image · Audio · Video — APIs SOTA",
      "Watermark + EXIF + disclaimer obligatorio",
      "3 safety filters no-negociables",
      "Audit log con sha256(prompt)",
    ],
    features: [
      {
        title: "Image providers (5)",
        body: "NanoBanana 2 (Gemini), Flux 2 Pro (BFL), Recraft v4, Ideogram v3, Imagen 4. Cada uno con FakeImageProvider hermano para tests offline. Default routing por env JW_GEN_IMAGE_PROVIDER.",
      },
      {
        title: "Audio providers (3)",
        body: "ElevenLabs (TTS+music), Suno (music), MusicGen (Meta local). Voice cloning gateado por safety.refuse_voice_cloning_without_double_optin: requiere --voice-clone flag AND signed input.txt sibling.",
      },
      {
        title: "Video providers (5)",
        body: "Veo 3 (Gemini), Kling Video O3, Seedance 2.0, Higgsfield MCP, Runway. Generación long-running con poll loop bounded a 5min.",
      },
      {
        title: "Policy fail-closed",
        body: "policy.finalize_output: si falta watermark o disclaimer no escribe el archivo. policy.apply_watermark + embed_metadata + write_disclaimer_sibling encadenados. PIL para visible watermark, piexif para EXIF, python-xmp-toolkit (opcional) para XMP.",
      },
      {
        title: "Safety filters property-tested",
        body: "Hypothesis con 100 prompts adversariales en en/es/pt. Bloquea: Watchtower logo, JW brand, kingdom hall sign, awake/despertai/despertad/betel. Encontró el bypass 'Despertai' durante test → vocabulario extendido.",
      },
    ],
    install: "uv sync --package jw-gen",
    usage: {
      language: "bash",
      caption: "Generar una ilustración para un discurso público.",
      code: `# Default offline (FakeProvider): produce un PNG placeholder
jw gen image \\
  --prompt "ilustración pacífica al amanecer" \\
  --out /tmp/illustration.png

# Con NanoBanana real (requiere GEMINI_API_KEY)
JW_GEN_IMAGE_PROVIDER=nanobanana \\
GEMINI_API_KEY=... \\
jw gen image \\
  --prompt "..." \\
  --out illustration.png

# Output siempre lleva:
#   illustration.png                       (con watermark visible)
#   illustration.png.disclaimer.txt        (en/es/pt)
#   audit log JSONL en ~/.jw-agent-toolkit/jw-gen-audit.jsonl`,
    },
    dependsOn: ["jw-core"],
    exports: [
      "policy.apply_watermark · embed_metadata · write_disclaimer_sibling",
      "safety.refuse_jw_logo_emulation · *_voice_cloning · *_realistic_faces",
      "factory.get_provider (image/audio/video) + 13 adapters",
      "MCP tool: generate_illustration (watermark forzado)",
    ],
    referenceHref: "/docs/guias/jw-gen",
    guideHref: "/docs/guias/jw-gen",
  },
  {
    slug: "jw-brain",
    name: "jw-brain",
    tagline: "Second-brain + Bible Knowledge Graph",
    color: "violet",
    short:
      "Karpathy-style second-brain con compiler dual-backend (DuckDB/Neo4j) + Wiki sobre Obsidian. F58 añadió BibleKnowledgeGraph JW-puro: 250 personas, 150 lugares con geocoordenadas, 10 periodos según cronología JW (607 a.E.C. para Jerusalén), CLI jw brain {init, compile, query, lint, import-bible, learn-headwords}.",
    about:
      "Construido en la Fase 49 como compiler que extrae el conocimiento del toolkit a un grafo consultable. La Fase 58 añadió el Bible Knowledge Graph JW-puro — versión propia derivada del Estudio Perspicaz de las Escrituras y NWT, NO portada de catálogos académicos inter-religiosos. Schema extendido con Period y Passage + 5 edges temporales (LIVED_IN_PERIOD, ACTIVE_IN_PERIOD, MENTIONED_IN_PASSAGE, LOCATED_IN_PASSAGE, PASSAGE_BELONGS_TO_PERIOD). Cronología JW estricta: 607 a.E.C. para destrucción de Jerusalén, no 587/586 a.E.C. del consenso académico. Atribución explícita a Watch Tower Bible and Tract Society of Pennsylvania.",
    highlights: [
      "GraphRAG DuckDB + Neo4j",
      "BibleKG JW-puro (607 a.E.C.)",
      "475 personas + 259 lugares + 16 geocoords",
      "MCP tools second_brain_*",
    ],
    features: [
      {
        title: "Second-brain compiler (F49)",
        body: "Compiler async dual-backend: DuckDB (zero-config, single-file) o Neo4j (relación-pesada, queries Cypher). Wiki sobre Obsidian con human_edited honored (re-compiles no sobreescriben ediciones manuales). Multi-tenant via registry ~/.jw-brain/registry.toml. BrainDomain plugins via F41 entry-points: TJ builtin + financial fixture.",
      },
      {
        title: "Bible Knowledge Graph JW-puro (F58)",
        body: "Schema extendido: Person, Place, Period (nuevo), Passage (nuevo). 5 edges nuevas LIVED_IN_PERIOD, ACTIVE_IN_PERIOD, MENTIONED_IN_PASSAGE, LOCATED_IN_PASSAGE, PASSAGE_BELONGS_TO_PERIOD. Loader procedural (NO LLM): BibleLoader.import_periods() materializa los 10 periodos curados; import_insight(jwpub) parsea cabezales del Insight on the Scriptures con catálogo PERSON_HEADWORDS+EXPANDED_PERSON_HEADWORDS (~250 figuras canon × ES+EN) y PLACE_HEADWORDS+EXPANDED_PLACE_HEADWORDS (~150 lugares × ES+EN).",
      },
      {
        title: "Place geocoords + Period catalog (F58.13 + F58)",
        body: "16 lugares principales con lat/lon, region, modern_name y eras_active: Jerusalem (31.78N, 35.24E, Judea), Babylon (32.54N, 44.42E, Mesopotamia, modern_name='Hillah, Iraq'), Rome, Athens, Ephesus, Nazareth, Bethlehem, etc. 10 periodos JW chronology: Era Patriarcal (2018-1657 a.E.C.), Cautiverio Egipcio, Jueces, Reino Unido, Reino Dividido, Cautiverio Babilónico (607-537 a.E.C., NO 587/586), Era Persa, Era Helenística, Era Romana, Era Cristiana Primitiva.",
      },
      {
        title: "CLI 8 comandos + audit headwords (F58.14)",
        body: "jw brain {init, compile, query, lint, status, snapshot, list, import-bible, learn-headwords}. import-bible --insight <jwpub> hidrata el grafo desde un JWPUB del Insight. learn-headwords --insight <jwpub> extrae cabezales del JWPUB del usuario y los persiste LOCALMENTE en <brain>/extracted_headwords.json (no se redistribuyen) — útil para auditar cobertura del catálogo built-in contra el Insight completo del usuario. Reporta % cobertura.",
      },
      {
        title: "MCP tools expuestas (F66)",
        body: "second_brain_status, second_brain_query, second_brain_compile, second_brain_lint, second_brain_snapshot — exponen el knowledge graph del jw-brain a Claude/Cursor/cualquier cliente MCP. Firma usa brain_path: str (path absoluto). Modo 'degraded' cuando jw-brain no instalado o no hay brain configurado.",
      },
      {
        title: "Consumer F72 doctrinal-drift",
        body: "El módulo jw_core.drift.brain_source.chunks_from_brain() lee los Publication nodes de cualquier backend que implemente list_nodes(node_type=...) y los convierte en Chunks aptos para analyze_doctrinal_drift — sin que jw-core dependa de jw-brain. Year extraction prioriza props year/published_year/pub_year y si falta cae a published_date[:4]. Language filter opt-in. Embedding inyectable (cualquier provider compatible F33). Cierra el loop write-read entre el grafo y el análisis diacrónico.",
      },
      {
        title: "Cobertura legal y atribución",
        body: "Built-in headword catalogs usan solo nombres del canon bíblico (hechos factuales públicos, no copyright). User-extracted desde JWPUB del usuario se queda LOCAL — el toolkit no redistribuye. Cronología JW (607 a.E.C.) triple-anclada en código, comentarios y guía. Atribución obligatoria Watch Tower Bible and Tract Society of Pennsylvania visible en docs/guias/bible-knowledge-graph.md.",
      },
    ],
    install: "uv sync --package jw-brain",
    usage: {
      language: "bash",
      caption: "Inicializa un brain + importa Bible KG + query Cypher-style.",
      code: `# 1. Init brain TJ
jw brain init --brain personal --vault ~/obs/jw

# 2. Importar periodos + Insight JWPUB
jw brain import-bible --brain personal --periods-only
jw brain import-bible --brain personal \\
  --insight ~/jwpubs/it_S.jwpub --symbol it --meps-language 3

# 3. Query: qué personas se mencionan en Génesis
jw brain query "¿Qué personas viven en Jerusalén durante el reinado de Ezequías?" --brain personal

# 4. Auditar cobertura del catálogo built-in
jw brain learn-headwords --insight ~/jwpubs/it_S.jwpub --brain personal
# → Built-in catalog covers 1842 / 2873 (64%)`,
    },
    dependsOn: ["jw-core"],
    exports: [
      "Compiler async + GraphBackend Protocol",
      "DuckDBBackend · Neo4jBackend",
      "BibleLoader · ALL_PERIODS · ALL_PLACES",
      "InsightParser · EXPANDED_PERSON_HEADWORDS · EXPANDED_PLACE_HEADWORDS",
      "CLI 9 comandos + MCP second_brain_* tools",
    ],
    referenceHref: "/docs/guias/bible-knowledge-graph",
    guideHref: "/docs/guias/bible-knowledge-graph",
  },
  {
    slug: "jw-meeting-media",
    name: "jw-meeting-media",
    tagline: "Reunión-en-vivo · clean-room",
    color: "amber",
    short:
      "Descubrimiento programa semanal mwb/w desde WOL, descarga media (imágenes/videos/audio/JWPUB), presenter Tauri con drag-drop + monitor externo automático + multi-congregación. Implementación clean-room (NO portada del repo M³ AGPL-3.0).",
    about:
      "Construido en la Fase 57 como implementación clean-room (estricta política de NO leer src/ del proyecto AGPL-3.0 sircharlo/meeting-media-manager). Parser HTML del WOL diseñado inspeccionando DOM real con DevTools, no copiando código M³. Stack: Python (jw-core PubMediaClient + WOLClient) + Tauri 2.x vanilla JS para presenter. F57.14 añadió drag-drop UI (sidebar + reorder + add file), F57.15 monitor externo automático (Tauri windows API), F57.16 multi-congregación (TOML registry con backwards-compat).",
    highlights: [
      "Clean-room (no port AGPL)",
      "Presenter Tauri + drag-drop",
      "Monitor externo automático",
      "Multi-congregación TOML",
    ],
    features: [
      {
        title: "MeetingProgramClient (F57)",
        body: "HTTP client para wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}. Parser BeautifulSoup sobre HTML del WOL con selectores semánticos (article.bodyTxt, h2, div.docSubContent, a.b, a.jsRef). Extrae secciones (Tesoros, Seamos mejores, Vida cristiana), items con bible_refs (parse_reference) y media_refs (imágenes CDN + videos jwbroadcasting + JWPUB linkeados).",
      },
      {
        title: "Pipeline media: Resolver → Downloader → Storage",
        body: "MediaResolver wrappea PubMediaClient para resolver video/audio refs con pub_code+track a URLs directas con sha256. Downloader idempotente: path scheme <cache>/<lang>/<year>/<week>/<filename>, skip si sha256 matches. MeetingStorage sqlite local: save_program(prog) + load_program(language, year, week, kind), mark_downloaded, get_download_info.",
      },
      {
        title: "Presenter Tauri (F57 + F57.14)",
        body: "Window declarativa Tauri 2.x en apps/desktop/src-tauri/tauri.conf.json. Frontend vanilla JS (sin Vue/React) sincronizado con PresenterManager Python vía REST (/presenter/sessions/{sid}/{state,play,pause,next,prev,stop,reorder,add,jump}). F57.14 añadió sidebar con cola de items, drag-drop nativo HTML5 para reordering + drop de archivos externos.",
      },
      {
        title: "Monitor externo automático (F57.15)",
        body: "Tauri commands en Rust: list_monitors devuelve MonitorInfo[] con name, width, height, x/y, scale, is_primary. move_presenter_to_monitor(name, fullscreen) reposiciona la ventana + set_fullscreen + focus. UI selector con dropdown menu en sidebar; fallback gracioso si solo 1 monitor.",
      },
      {
        title: "Multi-congregación (F57.16)",
        body: "Registry ~/.jw-agent-toolkit/meetings/congregations.toml. Comandos jw meeting congregation {add,list,remove}. Flag --congregation/-c en discover/download/list. resolve_congregation rules: name dado → lookup; sin name + 1 entry → auto; sin name + multiple → ValueError. Backwards-compat: sin registry → Congregation('default') con legacy cache root (no migration needed).",
      },
      {
        title: "MCP tools + CLI (F57.10 + F57.12 + F57.16)",
        body: "MCP tools: meeting_discover_week, meeting_download_media, meeting_list_programs, meeting_open_presenter, meeting_list_congregations, meeting_add_congregation. CLI: jw meeting {discover, download, list, congregation {add, list, remove}}. REST endpoints /presenter/* expuestos en jw_mcp.rest_api para que la ventana Tauri controle el estado.",
      },
    ],
    install: "uv sync --package jw-meeting-media",
    usage: {
      language: "bash",
      caption: "Workflow típico: registrar congregación, descubrir, descargar.",
      code: `# 1. Registrar congregaciones
jw meeting congregation add norte --language es --notes "Sala del Reino Norte"
jw meeting congregation add sur --language en --notes "Bilingual ward"

# 2. Descubrir el programa de la semana
jw meeting discover --congregation norte --year 2026 --week 23

# 3. Descargar toda la media de esa semana
jw meeting download --congregation norte --year 2026 --week 23

# 4. Abrir presenter Tauri
# (en apps/desktop: yarn tauri dev)
# Drag-drop archivos externos en el sidebar
# Selector 🖥 mueve a monitor proyector + fullscreen`,
    },
    dependsOn: ["jw-core", "jw-mcp"],
    exports: [
      "MeetingProgramClient · MediaResolver · Downloader",
      "MeetingStorage · Thumbnailer · PresenterManager",
      "Congregation · load_registry · resolve_congregation",
      "CLI: jw meeting {discover, download, list, congregation}",
      "REST: /presenter/* · MCP: meeting_*",
    ],
    referenceHref: "/docs/guias/meeting-media",
    guideHref: "/docs/guias/meeting-media",
  },
];

export const packageBySlug = (slug: string): PackageInfo | undefined =>
  packages.find((p) => p.slug === slug);

export const otherPackages = (slug: string): PackageInfo[] =>
  packages.filter((p) => p.slug !== slug);
