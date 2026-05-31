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
      "Librería principal: 6 clientes HTTP, 9 parsers, modelos Pydantic, registro de idiomas y la infraestructura de Fase 9 (cache, throttle, telemetría).",
    about:
      "El corazón del toolkit. Todo lo demás depende de jw-core, y jw-core no depende de nada del workspace. Aquí viven los clientes HTTP que hablan con jw.org, los parsers determinísticos que convierten HTML/JSON/EPUB/JWPUB en modelos Pydantic, y la infraestructura compartida: cache SQLite con TTL, throttle por host (token bucket), telemetría opt-in para drift de API y autenticación JWT aislada.",
    highlights: [
      "6 clientes · 9 parsers · 17 locales",
      "Cache · Throttle · Telemetría opt-in",
      "JWPUB decrypt AES-128-CBC",
      "Sin LLM en el camino crítico",
    ],
    features: [
      {
        title: "Clientes HTTP",
        body: "CDNClient (búsqueda + JWT), WOLClient (capítulos, texto diario, fetch arbitrario, cross-refs), MediatorClient (idiomas + finder), PubMediaClient (descargas), TopicIndexClient (guía de investigación), WeblangClient (catálogo de idiomas). Todos opcionalmente con cache + throttle + telemetría.",
      },
      {
        title: "Parsers determinísticos",
        body: "parse_reference (multiidioma), Article (HTML → modelo), DailyText, Verse (limpia pronunciación · marcas inline · asteriscos), StudyNote + CrossReference (matching headword↔versículo 100%), TopicIndex, Epub, JWPUB descifrado.",
      },
      {
        title: "Modelos Pydantic",
        body: "BibleRef · Verse · StudyNote · CrossReference · Article · Section · TopicSubject/Subheading/Citation · Epub · EpubDocument · JwpubMetadata · LanguageMetadata. Validación estricta en boundaries de sistema.",
      },
      {
        title: "Infraestructura Fase 9",
        body: "DiskCache (SQLite + TTL + WAL) · TokenBucket throttle (2 req/s, burst 5) · Telemetry (opt-in fingerprinting de respuesta para detectar drift) · JWTManager · factory unificado de clientes.",
      },
      {
        title: "Descifrado JWPUB",
        body: "Implementación AES-128-CBC sobre zlib con derivación de clave SHA256(lang_symbol_year) XOR magic constant. Descubierto por gokusander/jwpub-toolkit (MIT), portado a Python en parsers.jwpub desde Fase 5.5.",
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
      "parse_reference",
      "BibleRef · Verse · StudyNote · CrossReference",
      "CDNClient · WOLClient · MediatorClient · PubMediaClient",
      "DiskCache · Throttler · Telemetry · JWTManager",
      "Article · TopicSubject · Epub · JwpubMetadata",
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
      "CLI Typer + Rich con 8 comandos. Resuelve citas, descarga publicaciones, consulta el texto diario, busca y navega — sin abrir el navegador.",
    about:
      "Construida con Typer + Rich para que cualquier usuario que sepa abrir un terminal pueda usar el toolkit sin escribir Python. Cada comando es un wrapper directo sobre los métodos de jw-core, con output legible o pipeable a otras herramientas Unix.",
    highlights: [
      "8 comandos: verse · search · daily · ...",
      "Typer + Rich · 7 idiomas",
      "Pipeable a herramientas Unix",
      "Output JSON con --json",
    ],
    features: [
      {
        title: "8 comandos top-level",
        body: "jw verse <ref> · jw search <q> · jw daily · jw download <pub> · jw languages · jw chapter <ref> · jw jwpub <file> · jw topic <subject>. Cada uno con --lang, --json y flags específicos.",
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
      "Servidor Model Context Protocol que expone 40+ herramientas a Claude Desktop, Claude Code o cualquier cliente MCP. Tu IA habla con jw.org sin saber HTTP.",
    about:
      "El componente que convierte el toolkit en algo que tu agente de IA puede usar. Implementado con FastMCP, expone cada parser y cliente de jw-core (más el RAG y los agentes) como tools accesibles vía el protocolo MCP estándar. Funciona sobre stdio para Claude Desktop/Code o sobre SSE para otros clientes.",
    highlights: [
      "40+ tools sobre stdio MCP",
      "FastMCP · Claude/IDE compatible",
      "RAG y agentes integrados",
      "Cache + throttle compartido",
    ],
    features: [
      {
        title: "40+ herramientas registradas",
        body: "resolve_reference · get_chapter · get_daily_text · search_content · get_article · get_verse · get_study_notes · get_cross_references · compare_translations · list_languages · download_publication · jwpub_extract · topic_subjects · ... más 5 finetune tools.",
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
        body: "Una entrada en claude_desktop_config.json apuntando a 'uv run jw-mcp'. Reinicia Claude Desktop y ya tienes 40+ tools nuevas en tus conversaciones.",
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
      "40+ MCP tools sobre stdio",
      "Resources: file://jw/...",
      "Agentes: verse_explainer · research_topic · ...",
      "RAG: search_corpus con BM25 + vector + RRF",
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
      "fusion: rrf · linear · max",
    ],
    referenceHref: "/docs/referencia/jw-rag",
    guideHref: "/docs/guias/indexar-y-buscar-con-rag",
  },
  {
    slug: "jw-agents",
    name: "jw-agents",
    tagline: "Orquestación multipaso",
    color: "amber",
    short:
      "Agentes procedurales determinísticos: verse_explainer, research_topic, meeting_helper, apologetics. Sin LLM en el camino crítico.",
    about:
      "Agentes hechos a mano, no LLM-orchestrated. Cada uno orquesta múltiples llamadas a jw-core + jw-rag para producir findings estructurados con citas verificables a wol.jw.org. La síntesis del lenguaje natural ocurre fuera del toolkit (Claude Desktop, Claude Code, tu propio cliente).",
    highlights: [
      "4 agentes procedurales",
      "Findings citables · wol.jw.org",
      "Sin LLM en camino crítico",
      "Composición con fine-tuned",
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
];

export const packageBySlug = (slug: string): PackageInfo | undefined =>
  packages.find((p) => p.slug === slug);

export const otherPackages = (slug: string): PackageInfo[] =>
  packages.filter((p) => p.slug !== slug);
