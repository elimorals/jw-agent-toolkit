# Extrapolar el toolkit a otras religiones

> Manual conceptual y visión de futuro. Analiza qué capas del proyecto
> son agnósticas de religión, qué capas son específicas de TJ, y
> propone tres caminos posibles para reutilizar la arquitectura con
> otras organizaciones religiosas (católico, ortodoxo, judío, islámico,
> mormón, evangélico, budista, ecumenismo académico).
>
> **Estado**: idea estratégica, no compromiso. Pre-requisito a Fase 65+.
> Las decisiones operacionales viven en [`ROADMAP.md`](../ROADMAP.md)
> y [`VISION.md`](../VISION.md).

## Resumen ejecutivo (TL;DR)

- **Sí es extrapolable**. Entre el 60-75% del código útil ya es
  agnóstico de religión por diseño: infraestructura Fase 9 (cache,
  throttle, JWT, telemetría), Plugin SDK Fase 41 con 5 entry-points,
  Second Brain Fase 49 (`BrainDomain` plugins), multi-tenant Fase
  57.16 (`congregations.toml`), audio Omnilingual ASR 1672 idiomas,
  traducción NLLB-200, semantic chunking, RAG híbrido, MCP server,
  CLI Typer/Rich, presenter Tauri.
- **Lo específico de TJ** son ~6-9 piezas concretas: endpoints
  `wol.jw.org`, formato JWPUB cifrado, catálogo MEPS, registro de 66
  libros NWT, skills doctrinales (Trinity, blood, 1914, Memorial),
  vocabulario (Atalaya, Workbook, ancianos).
- **Recomendación**: refactor a `faith-core` con `jw` como plugin
  builtin. El patrón ya existe en la arquitectura — no es invento.
- **Religión piloto sugerida**: islam vía `quran.com` (API REST limpia,
  multi-idioma nativo, sin formatos cifrados). Demuestra el camino
  sin entrar en política intra-cristiana.

## Mapa de capas: agnóstico vs específico

```
┌────────────────────────────────────────────────────────────────────┐
│ D. SKILLS Y VOCABULARIO DOCTRINAL                       TJ 100%    │
│    apologetics rules, memorial countdown, workbook                 │
│    student assignments, ministerio, Atalaya / Watchtower           │
├────────────────────────────────────────────────────────────────────┤
│ C. ENDPOINTS + PARSERS + FORMATOS PROPIETARIOS          TJ 100%    │
│    6 clientes HTTP de jw.org / wol.jw.org / b.jw-cdn.org           │
│    9 parsers HTML específicos, descifrado JWPUB AES-128-CBC        │
│    catálogo MEPS docid<->pub_code, deep links jwlibrary://         │
├────────────────────────────────────────────────────────────────────┤
│ B. VERTICALES DE SUPERFICIE                             Mixto      │
│    CLI Typer/Rich, MCP server FastMCP, RAG híbrido,                │
│    agentes procedurales, website Astro, presenter Tauri,           │
│    plugin Obsidian, extensión navegador WOL, fine-tuning           │
│    (shell agnóstico; contenidos TJ desacoplables)                  │
├────────────────────────────────────────────────────────────────────┤
│ A. NÚCLEO TÉCNICO                              Agnóstico 100%      │
│    cache SQLite + TTL, TokenBucket throttle per-host,              │
│    JWT manager, telemetry opt-in, Plugin SDK F41 con 5             │
│    entry-points, NLI fidelity F39, content provenance F40,         │
│    agent tracing F43, semantic chunking F45, constrained           │
│    decoding F35, Second Brain Karpathy-style F49 con               │
│    BrainDomain plugins, scaffolder create-jw-agent F42,            │
│    Omnilingual ASR 1672 idiomas F53, NLLB-200 traducción           │
│    F54, WhisperX diarización F64, memoria persistente F61,         │
│    multi-tenant congregations F57.16, versification F46            │
│    (nwt/masoretic/lxx/vulgate ya soporta 4 tradiciones)            │
└────────────────────────────────────────────────────────────────────┘
```

**Métrica clave**: de ~2,600 LOC útiles (1,887 tests passing tras Fase
55), la capa A es 100% reutilizable y la B es 80% reutilizable
cambiando contenidos. Solo C+D son verdaderamente atados a TJ.

## Tres caminos posibles

Ordenados por esfuerzo creciente y reutilización creciente.

### Camino 1 — Plantilla "fork-and-rename"

**Esfuerzo**: semanas por religión.
**Reutilización**: divergente — cada fork se vuelve un proyecto separado.

Documentar cómo terceros forken el repo y reemplacen:

- `packages/jw-core/src/jw_core/clients/*` → clientes a la editorial de
  la otra religión (`vatican.va`, `bibliaonline.com.br`,
  `monergism.com`, `sefaria.org`, `quran.com`, `sunnah.com`,
  `accesstoinsight.org`, etc.).
- `packages/jw-core/src/jw_core/data/books.py` → canon propio:
  - Católico: 73 libros (RSV-CE / DRC con deuterocanónicos)
  - Tanaj judío: 24 libros con orden hebreo
  - Corán: 114 suras
  - Tipiṭaka budista: estructura pali
- `skills/jw-*` → skills doctrinales propios.
- `packages/jw-finetune` → ya diseñado como **plataforma local
  agnóstica** (cada usuario entrena su modelo con su corpus; ver
  memoria de proyecto sobre platform design).

**Cuándo conviene**: maximizar velocidad para una religión nueva sin
contaminar el upstream TJ.

### Camino 2 — Refactor a `faith-agent-toolkit` con plugins por religión

**Esfuerzo**: 1-2 trimestres.
**Reutilización**: máxima sin sacrificar separación.

El proyecto **ya tiene la maquinaria** para esto:

- `jw_core/plugins/` con 5 entry-points (Fase 41).
- `BrainDomain` plugins en Fase 49 (TJ builtin + financial fixture
  demuestran el patrón multi-dominio).
- `congregations.toml` multi-tenant en Fase 57.16.
- `versification` en Fase 46 ya conoce nwt/masoretic/lxx/vulgate.
- `create-jw-agent` scaffolder en Fase 42.

Pasos del refactor:

1. Renombrar paquete `jw-core` → `faith-core` (o `scripture-core`).
   Migrar imports con compatibility shim por un sprint.
2. Mover todo lo TJ a un plugin builtin `faith-jw` (66 libros, WOL,
   JWPUB, MEPS, deep links, skills doctrinales, workbook scraper).
3. Añadir **dos entry-points nuevos** al Plugin SDK:
   - `faith_agent_toolkit.corpora` — declara canon + libros + idiomas.
   - `faith_agent_toolkit.endpoints` — clientes HTTP + parsers.
4. Plugin `faith-catholic`: 73 libros (DRC/RSV-CE), `vatican.va` +
   `bibliaonline.com.br`, deep links a Hallow/Magnificat.
5. Plugin `faith-islamic`: 114 suras, `quran.com` + `sunnah.com`,
   audio recitación, calendario hijri.
6. Plugin `faith-jewish`: 24 libros Tanaj, `sefaria.org`, parashat
   semanal, calendario hebreo.
7. El monorepo principal queda **neutro**. El website actual se vuelve
   "vitrina del builtin TJ" igual que el resto.

**Cuándo conviene**: si el objetivo es un patrón sostenible que
escale a 3+ religiones sin múltiples codebases.

### Camino 3 — Multi-tenant interreligioso en runtime

**Esfuerzo**: trimestre+.
**Reutilización**: máxima, pero con superficie comparativa nueva.

Un solo install corre múltiples religiones simultáneamente, igual que
el patrón multi-congregación de Fase 57.16. Configuración por TOML:

```toml
[faiths.jw]
canon = "nwt-66"
endpoints = "wol.jw.org"
languages = "en,es,pt,fr,de,it,ja,ko,zh"

[faiths.cath]
canon = "drc-73"
endpoints = "vatican.va,bibliaonline.com.br"
languages = "la,it,es,en,pt"

[faiths.islam]
canon = "quran-114"
endpoints = "quran.com,sunnah.com"
languages = "ar,en,es,ur,id,tr"
```

Útil para uso académico (religious studies, ecumenismo, apologética
comparada). Permite features novedosas como **`compare_doctrine`**:
"¿qué dice cada tradición sobre X?".

**Cuándo conviene**: si el target son investigadores o un SaaS
multi-religión.

## Religiones piloto candidatas

Análisis de fricción esperada por religión. Score: 1 = trivial, 5 =
muy complejo.

| Religión   | Corpus público | Idiomas | Formato | Doctrina | Score |
|------------|----------------|---------|---------|----------|-------|
| Islam suní | `quran.com` REST público, sin auth | ar, en, +30 | JSON limpio | Estable, well-documented | **2** |
| Judaísmo   | `sefaria.org` API REST + bilingüe | he, en, es | JSON + texto | Estable, plural | **2** |
| Católico   | `vatican.va` scraping + `bibliaonline` | la, it, es, en, pt | HTML mixto | Magisterio centralizado | **3** |
| Ortodoxo   | Fuentes fragmentadas por jurisdicción | gr, ru, en | HTML disperso | Plural por jurisdicción | **4** |
| Evangélico | Multi-editorial, sin canon de fuentes | en dominante | Heterogéneo | Muy plural | **4** |
| Mormón     | `churchofjesuschrist.org` + scriptures | en, es, pt | HTML limpio | Centralizada | **2** |
| Budismo    | `accesstoinsight.org`, `suttacentral.net` | pali, en, +20 | Texto crudo | Plural por escuela | **3** |
| Hinduismo  | Sin editorial central | sa, hi, en | Muy disperso | Extremadamente plural | **5** |

**Recomendación**: empezar por **islam vía `quran.com`** o **judaísmo
vía `sefaria.org`**. Ambos tienen APIs REST limpias, multi-idioma
nativo, sin formatos cifrados, sin política intra-cristiana. El PoC
demuestra el camino del refactor sin abrir frentes doctrinales.

## Plantillas que se podrían crear

Si se ejecuta el Camino 2, estos son los entregables tangibles:

### Plantilla `create-faith-plugin` (extiende F42)

Scaffolder PyPI standalone que genera un plugin religioso en <10 min,
análogo al actual `create-jw-agent`:

```bash
pipx run create-faith-plugin

? Faith name (kebab-case): catholic
? Canon: 73-book RSV-CE
? Primary endpoints: vatican.va, bibliaonline.com.br
? Languages: la, it, es, en, pt
? Entry-points to register: corpora, endpoints, agents, skills
```

Genera estructura con stubs:

```
faith-catholic/
  pyproject.toml          (entry-points pre-cableados)
  src/faith_catholic/
    canon.py              (73 libros stubbed)
    endpoints/
      vatican.py          (httpx client + parser stub)
      bibliaonline.py
    skills/
      apologetics_*.md
      lectionary.py       (lectionary semanal análogo a workbook)
  tests/
    test_canon.py
    test_endpoints.py     (cassettes vacíos para grabar)
```

### Plantilla `docs/guias/creating-a-faith-plugin.md`

Guía paso a paso de 6 capítulos:

1. Definir el canon (libros, capítulos, versículos).
2. Mapear endpoints públicos y respetar TOS.
3. Implementar parser HTML/JSON con cassettes.
4. Escribir skills doctrinales con citas verificables.
5. Tests de fidelidad (NLI Fase 39 con premisas de la tradición).
6. Publicar a PyPI bajo namespace `faith-*`.

### Plantilla `docs/conceptos/faith-plugin-architecture.md`

Manual conceptual paralelo a [`decisiones-de-diseno.md`](decisiones-de-diseno.md)
que documenta las decisiones específicas multi-religión:
trade-offs de canon, versification ya existente F46 como precedente,
política "una religión por plugin", política de skills doctrinales,
límites éticos.

### Plantilla `examples/faith-islamic-poc/`

Plugin completo de referencia. Misma función que `BrainDomain
financial fixture` cumple para F49: demuestra que el patrón funciona
fuera del builtin.

### Religious Knowledge Graph multi-tradición

Extensión natural del Bible Knowledge Graph de Fase 58, que **ya
contempla separación inter-religiosa** según la guía existente:
"atribución y separación del KG académico inter-religioso".

## Riesgos y consideraciones

### Doctrinales / éticos

- **Posicionamiento**: ¿la herramienta es **neutral** (presenta varias
  interpretaciones) o **partisana** por religión (cada plugin defiende
  su doctrina)? Esto define cómo se estructuran skills y apologetics.
  Recomendación: el toolkit es neutral, los plugins son partisanos en
  su propio scope, los plugins de comparación (`faith-compare`) son
  neutrales.
- **Apologética cruzada**: prohibir que un plugin haga apologética
  contra otra religión por defecto. Habilitar solo con opt-in
  explícito del usuario.
- **Sensibilidad cultural**: islam exige cuidado con `Allah` /
  `prophet PBUH`, judaísmo con el Tetragrámaton, hinduismo con el
  pluralismo. Las skills deben respetar las convenciones de cada
  tradición.
- **No sustituir consejería pastoral / rabínica / imamato**. Ya está
  documentado para TJ en `temas-de-vida.md` (Fase 32); el patrón
  aplica a todas las religiones.

### Legales

- **TOS de cada editorial**: jw.org permite acceso público análogo a
  un navegador. Otras editoriales pueden exigir API keys, rate limits
  estrictos, o prohibir scraping. Cada plugin debe documentar su
  política de acceso.
- **Licencias de corpus**: NWT es propietaria de Watch Tower; RSV-CE
  tiene su propia licencia; el Corán es de dominio público pero las
  traducciones modernas no; Sefaria es CC-BY. Cada plugin debe
  declarar licencia de corpus por separado del plugin code.
- **Marcas registradas**: "Watchtower", "Jehovah's Witnesses",
  "Vatican", "Holy See" están registradas. Los plugins no pueden
  llevar nombres que sugieran endorsement oficial. Usar prefijos
  como `faith-` o `unofficial-`.

### Técnicos

- **Versification**: ya parcialmente resuelto en Fase 46 (4
  tradiciones). Extender a numeración islámica (suras + ayat),
  Tanaj (orden hebreo), citas patrísticas (PG/PL), Bhagavad Gita
  (capítulo + verso), Tipiṭaka (Nikāya + Sutta).
- **Idiomas no-latinos**: árabe RTL, hebreo RTL+niqud, mandarín CJK,
  tibetano. La infraestructura Omnilingual + NLLB ya cubre los
  modelos; falta UI/CLI sane defaults para RTL.
- **Calendarios**: hijri (islam), hebreo (judaísmo), gregoriano TJ,
  litúrgico católico. Necesita un `jw_core/calendar/` reescrito como
  `faith_core/calendars/` con cada plugin aportando su tradición.

### De producto

- **Audiencia divergente**: hermanos de congregación / fieles laicos
  (UI simple, móvil-first) vs investigadores académicos (CLI + RAG
  sofisticado). Hoy el toolkit es claramente lo segundo. Pivotear
  hacia lo primero implica priorizar website + Tauri app + bot
  mensajería.
- **Modelo de negocio**: ¿SaaS multi-religión, plantilla open-source
  para terceros, o toolkit interreligioso académico? Cada uno cambia
  la arquitectura de plugins (privado/público, partisano/neutral,
  hosted/self-hosted).

## Plan de fases ilustrativo (Fase 65-75)

Numeración ilustrativa siguiendo la convención del proyecto. El orden
real lo decide el valor entregado.

- **Fase 65 — Estrategia y PoC neutral**
  - Decisión de Camino 1/2/3 (este documento + AskUserQuestion al
    autor sobre objetivo de negocio).
  - PoC `faith-islamic` o `faith-jewish` como plugin standalone sobre
    el repo actual sin refactorizar (prueba que el Plugin SDK F41
    soporta el caso de uso interreligioso).

- **Fase 66 — Extender Plugin SDK con `corpora` + `endpoints`**
  - Dos entry-points nuevos. Backwards-compatible.
  - Test fixture con dos canones registrados.

- **Fase 67 — Renombrar `jw-core` → `faith-core`**
  - Compatibility shim por 1 sprint.
  - Migración de imports automática vía codemod.
  - `jw` se mueve a plugin builtin.

- **Fase 68 — `create-faith-plugin` scaffolder**
  - Hermano de `create-jw-agent` (F42).
  - 5 tipos: corpus / endpoints / agent / skill / brain_domain.

- **Fase 69 — Documentación**
  - `docs/guias/creating-a-faith-plugin.md`.
  - `docs/conceptos/faith-plugin-architecture.md`.
  - Localizar guías existentes para ejemplo neutro.

- **Fase 70 — Plantilla `faith-islamic` completa**
  - PoC convertido en plugin de referencia publicado a PyPI.
  - Cookbook con 12 recetas verificadas (análogo a F42 cookbook).

- **Fase 71 — Versification multi-tradición**
  - Extender Fase 46 a numeración islámica + hebrea + patrística.

- **Fase 72 — Multi-faith en runtime (Camino 3)**
  - `faiths.toml` análogo a `congregations.toml`.
  - Agente `compare_doctrine` neutral.

- **Fase 73-75 — Plugins adicionales y SaaS**
  - `faith-catholic`, `faith-jewish`, `faith-mormon`.
  - App de escritorio multi-religión.
  - Bot Telegram/WhatsApp con switch por slash command.

## Preguntas abiertas que bloquean el plan

Antes de comprometerse a cualquier fase, responder:

1. **Objetivo de negocio**: ¿SaaS multi-religión, plantilla
   open-source para terceros, o toolkit interreligioso académico?
2. **Religión piloto**: ¿islam, judaísmo, católico, mormón? ¿Hay una
   razón estratégica para preferir una?
3. **Compromiso con la base TJ**: ¿se acepta renombrar paquetes y
   romper imports (con shim), o se prefiere repo nuevo desde cero?
4. **Posicionamiento doctrinal**: ¿toolkit neutral con plugins
   partisanos, o toolkit partisano con un plugin TJ y plugins
   "competidores" desactivados por defecto?
5. **Acceso a corpus**: ¿se tiene relación con alguna editorial
   no-TJ que facilite acceso oficial (API keys, partnerships)?
6. **Audiencia**: ¿fieles laicos (UI simple) o investigadores (CLI
   + RAG sofisticado)?

Responder estas seis convierte este documento en un plan ejecutable
con cronograma real.

## Ver también

- [VISION.md](../VISION.md) — Roadmap de visión TJ (Fases 11-18+ ya
  ejecutadas).
- [decisiones-de-diseno.md](decisiones-de-diseno.md) — Por qué
  monorepo, plugin SDK, agentes procedurales (las decisiones que
  hacen este refactor barato).
- [`docs/plugin-sdk/overview.md`](../plugin-sdk/overview.md) —
  Mecanismo de entry-points sobre el que se construiría todo.
- [`docs/guias/scaffolding.md`](../guias/scaffolding.md) — F42
  `create-jw-agent` como precedente del futuro
  `create-faith-plugin`.
- [`docs/guias/second-brain.md`](../guias/second-brain.md) — F49
  `BrainDomain` plugins como precedente arquitectónico de
  multi-dominio.
- [`docs/guias/versification.md`](../guias/versification.md) — F46
  ya soporta 4 tradiciones de numeración bíblica; precedente
  arquitectónico para multi-canon.
- [`docs/guias/meeting-media.md`](../guias/meeting-media.md) — F57.16
  multi-congregación como precedente del patrón multi-tenant.
