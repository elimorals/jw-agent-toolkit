# Visión: ecosistema completo de LLM/IA para Testigos de Jehová

> Roadmap a largo plazo — qué funcionalidades faltan para que `jw-agent-toolkit` sea un ecosistema completo, no solo una librería de acceso a contenido jw.org.

Este documento es **visión de producto**, no compromiso. La `docs/ROADMAP.md` cubre lo que ya se construyó (Fases 0-10). Esta es la siguiente capa.

## Punto de partida

A día de hoy el toolkit cubre:

- 6 clientes HTTP a la infraestructura jw.org (CDN, WOL, Mediator, PubMedia, TopicIndex, Weblang).
- 9 parsers (citas, artículos, texto diario, versículos, notas de estudio, índice temático, EPUB, JWPUB descifrado).
- 29 herramientas MCP + 4 agentes procedurales (`verse_explainer`, `research_topic`, `meeting_helper`, `apologetics`).
- RAG híbrido (BM25 + vector + RRF) con ingest de Biblia, artículos, búsqueda CDN, EPUB y JWPUB.
- Infraestructura Fase 9: cache SQLite, throttle, telemetría opt-in, factory unificado.
- CLI con 8 comandos, 5 skills Markdown para Claude.

Lo que sigue son los gaps para llegar a un **ecosistema completo**.

---

## 1. Reunión semanal (alto valor)

Lo más doloroso hoy: `meeting_helper` recibe URL o ref bíblica, pero no descubre por sí solo "lo que toca esta semana".

- **Scraper del Workbook** (`Vida y Ministerio Cristianos`) — descubre programa semanal automáticamente.
- **Cuaderno de Watchtower Study** con asignación sugerida de párrafos a discusantes.
- **Generador de comentarios cortos** (15-30 s) por párrafo, con tono natural y citas.
- **Asistente para discursos públicos** (10-20 min): outline con desarrollo bíblico, ilustraciones de publicaciones JW recientes.

## 2. Ministerio / predicación (alto valor, único)

- **Asistente de conversaciones**: objeciones comunes ("la Biblia se contradice", "el infierno", "Trinidad") con respuestas + citas verificables.
- **Generador de presentaciones por tema** adaptadas al interlocutor (católico, evangélico, ateo, joven, etc.).
- **Tracker de revisitas con notas, intereses y plan de siguiente visita** (privacidad: solo local).
- **Sugerencias contextuales por ubicación** (cultura local, idiomas hablados, festividades).
- **Buscador inverso**: "tengo una cita sobre X, ¿de qué publicación es?" — útil cuando recuerdas un párrafo pero no la fuente.

## 3. Audio y voz (multimodalidad)

- **TTS** para escuchar texto bíblico/artículos en cualquier idioma soportado por jw.org. (El toolkit ya descarga audios; no orquesta playback.)
- **Whisper local** para dictar notas durante estudio personal.
- **Búsqueda en transcripciones de JW Broadcasting** (videos + sermones).

## 4. Estudio personal (alto valor, retención)

- **Plan de lectura bíblica con tracking** (un año, cronológico, etc.).
- **Notas personales asociadas a versículos**, persistentes y buscables vía RAG.
- **Flashcards / spaced repetition** de pasajes clave.
- **Comparador entre traducciones** — ya está parcialmente; falta incluir traducciones no-NWT (Reina-Valera, etc.) para apologética.
- **Análisis de idiomas originales**: hebreo/griego, Strong's numbers, conexiones con interlineales (cuando hay).

## 5. Familia y niños

- **Adoración familiar** semanal con sugerencias adaptadas a edad de los hijos.
- **Recursos para niños**: `caudal jw`, lecciones del libro "Aprende del Gran Maestro", actividades.
- **Quiz bíblico interactivo** por edad.

## 6. Calendario y eventos

- **Memorial anual** con countdown + sugerencias de preparación.
- **Asambleas regionales/circuito**: detección automática de fechas + materiales relacionados.
- **Visita del superintendente**: checklist de preparación.

## 7. Multimodalidad visual

- **OCR sobre fotos** de la Biblia física o de páginas de publicaciones (útil cuando alguien comparte una foto y quieres saber qué dice).
- **Análisis de mapas bíblicos** (geografía: "¿por dónde viajó Pablo en su segundo viaje?").
- **Generación de slides/gráficos** para discursos.

## 8. Idiomas (la expansión más obvia)

- **Tier 1 actual**: `en`/`es`/`pt`. Falta francés, alemán, italiano, ruso, chino, japonés, coreano (todos con NWT publicada).
- **Lenguas de señas** (LSM, ASE, etc.): JW Broadcasting tiene horas de contenido; sería el primer agente que las indexa.
- **Traducción automática** entre idiomas preservando referencias bíblicas exactas.

## 9. Verificación y apologética avanzada

- **Fact-checker contra fuentes JW oficiales únicamente** (rechazar todo lo que no esté en jw.org / wol.jw.org).
- **Detector de información apócrifa** o atribuida falsamente a publicaciones JW.
- **Análisis de argumentos opositores** con respuestas estructuradas.
- **Refutación de "ex-TJ" sites** con citas verificables (uso defensivo, contextualizado).

## 10. Infraestructura operacional

Lo que ya está en TODO (Fase 9) o que el ecosistema necesita para escalar:

- **Logging estructurado** (mencionado pero no implementado en Fase 9).
- **Dashboard web** para monitoring del MCP (cache hit rate, drift events, throughput).
- **REST API** sobre el MCP para integraciones no-Claude (Telegram/Discord/WhatsApp bots).
- **Bot de Telegram/WhatsApp** para uso desde el móvil sin Claude Desktop.
- **App de escritorio** (Tauri) — empaqueta MCP + Claude Code en una sola UI.
- **Sync multi-dispositivo** (notas, RAG store) cifrado end-to-end.
- **Publicación a PyPI** (pendiente desde Fase 9).

## 11. Privacidad y local-first

Los TJ valoran este aspecto:

- **Modelo LLM local** (Ollama/Llama) opcional — Claude no es opción para todos (coste, política, conexión).
- **Cifrado de notas personales** y del RAG store por defecto.
- **Modo "sin telemetría externa"** garantizado (casi listo — falta auditar que nada salga sin opt-in).

## 12. Personalización y memoria

- **Profile del usuario**: idioma preferido, congregación, asignaciones típicas, intereses doctrinales.
- **Memoria persistente entre sesiones**: "ayer estábamos viendo X, continuamos".
- **Tono ajustable**: respetuoso/formal vs casual para diferentes contextos.

## 13. Accesibilidad

- **Audio en lengua materna** con voz natural (TTS de calidad).
- **Modo "texto fácil"** para nuevos lectores o personas con discapacidad cognitiva.
- **Alta accesibilidad visual** (contraste, tipografías).

---

## Lo que movería más la aguja (recomendación priorizada)

Si hay que priorizar para máximo impacto en menos esfuerzo:

1. **Scraper del Workbook + Watchtower Study** → desbloquea el caso de uso #1 de cualquier TJ (la reunión semanal).
2. **Asistente de conversaciones / objeciones** con citas verificables → caso de uso único, defensible, alto valor.
3. **TTS + audio playback** → multiplica el alcance (gente que escucha mientras maneja, hace ejercicio, etc.).
4. **Bot de Telegram/WhatsApp** sobre el MCP → quita la fricción de "tener que abrir Claude Desktop".
5. **Notas personales con RAG sobre ellas** → loop de retención: el sistema se vuelve más valioso a medida que lo usas.

## Nice-to-have, defendible

- Modelo local Ollama.
- Sync multi-dispositivo cifrado.
- OCR multimodal.
- JW Broadcasting indexing (subtítulos + transcripciones).

## Lo que conviene evitar

Estas líneas tienen riesgo legal, comunitario o ético sin un mandato claro:

- **Cualquier feature comunitaria que recolecte datos** sin que la organización JW lo bendiga oficialmente.
- **Tracker de hermanos** (directorio, asignaciones) sin opt-in explícito y consentimiento documentado.
- **Sustitución de la palabra de los ancianos** en consejería pastoral — los agentes pueden orientar/informar, no aconsejar pastoralmente.
- **Almacenamiento centralizado de notas personales sensibles** sin cifrado E2E.

---

## Alineamiento doctrinal e interpretabilidad mecanicista (F77–F80, ya entregadas)

A 2026-06, el toolkit cubre además el ciclo completo de alineamiento
para fine-tunes locales:

- **Constitutional AI supervisado (SL-CAI)** — el judge revisa cada par
  Q&A contra principios YAML versionados y reescribe violaciones antes
  de que entren al SFT. Cierra el problema de "el dataset enseña al
  modelo el shortcut".
- **RLAIF + DPO/ORPO** — preferencias generadas por el judge (no por
  humanos) alimentan trainers Unsloth sobre Qwen3.5-0.8B (Apache-2.0).
- **Interpretabilidad mecanicista** — probes lineales por principio
  responden si el modelo internalizó la doctrina o aprendió un
  shortcut estilístico. Steering vectors y activation patching validan
  causalidad. Adapters para Qwen-Scope (TopK SAE en residual) y Gemma
  Scope (JumpReLU SOTA en residual + MLP + attention) habilitan
  cross-family validation. El runtime `fidelity_wrap` Tier 4 anota
  evidencia interpretable por Finding sin vetar producción.

Filosofía de alineamiento: el material vigente publicado por la
organización es la fuente de verdad; el toolkit lo refleja, no legisla.
Probes y SAEs son herramientas de auditoría defendible internamente,
no clasificación de riesgo ni intervención política sobre la doctrina.

## Cómo se relaciona con el ROADMAP operacional

El [ROADMAP.md](ROADMAP.md) cubre Fases 0-80 (alineamiento doctrinal e
interpretabilidad mecanicista incluidos). Si en algún momento se decide
ejecutar piezas de este documento, irían como Fases 81+:

- **Fase 81+ — Distribución y polish** (PyPI, app de escritorio
  pulida, bots de mensajería, REST API estable).
- **Fase 81+ — Idiomas adicionales** (expansión a 6+ idiomas Tier 1,
  traducción preservando refs).
- **Fase 81+ — Local-first / privacidad** (modelo Ollama, cifrado
  E2E, sync multi-dispositivo).
- **Fase 81+ — Web/Web3 / contribución comunitaria** sin recolección
  de datos sensibles.

Esta numeración es ilustrativa — el orden real lo decide el valor
entregado por cada pieza al usuario.
