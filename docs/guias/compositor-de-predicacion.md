# Compositor de carta / teléfono / carrito

> Agente: `letter_composer` (Fase 29).
> Tool MCP: `compose_witnessing`.
> CLI: `jw letter --kind {letter|phone|cart} --topic "..." --audience ... --lang ...`.

## Qué hace

Produce un **andamiaje estructurado** para tres modalidades del servicio del campo:

- **`letter`** — carta personal (~150 palabras orientativas).
- **`phone`** — guion telefónico (~75 segundos orientativos).
- **`cart`** — micro-guion de carrito (~30 segundos orientativos).

Cada salida tiene 4 secciones obligatorias: `opener · bridge · scripture · closing`. Una 5ª opcional (`topic_anchor`) se añade si se pasa `TopicIndexClient`.

## Qué NO hace

- **No** escribe la carta / la llamada por usted. Le da un punto de partida calibrado para que usted lo lea con su voz, su contexto y su buen juicio.
- **No** sustituye la consejería de los ancianos.
- **No** almacena el `territory_hint`, la audiencia, ni el tema. El toolkit es stateless por invocación.
- **No** copia texto bíblico ni párrafos de jw.org. Solo emite la **referencia + URL canónica**. El texto del versículo lo abre usted en jw.org / JW Library.

## Audiencias soportadas

| Clave | Para quién |
|---|---|
| `default` | Persona del público sin contexto previo. |
| `new` | Vecino al que aún no ha contactado. |
| `religious` | Persona de fe (cualquier denominación). |
| `atheist` | Ateo / agnóstico — registro de evidencia. |
| `grieving` | Persona en duelo / con pérdida reciente. |
| `young` | Joven / adolescente — registro coloquial. |
| `parents` | Persona con responsabilidades de crianza. |

> **Aviso**: la audiencia es una **sugerencia del publicador**, no una etiqueta asignada a la persona real. Úsela con discernimiento.

## Familias temáticas (auto-detectadas)

`family`, `suffering`, `hope`, `science`, `peace`, `identity`, `addictions`, `generic`. La función `resolve_topic_family(text, language)` mira palabras clave en el texto y elige la más representada. Si nada matchea → `generic`.

## Política de copyright

- La prosa de las plantillas en `letter_templates.py` / `phone_templates.py` / `cart_templates.py` está **escrita por el autor del paquete** (paráfrasis neutra). No es texto de jw.org.
- El bloque `scripture` **no** copia el versículo: solo emite `Citation.url` apuntando a wol.jw.org. El consumidor abre la URL y lee el texto allí.
- El enlace sugerido (`suggested_jw_link`) apunta siempre a una URL pública de jw.org.

## Política de PII

- `territory_hint` es **cosmético**. Se concatena al opener tal cual. No filtra contenido. No se persiste.
- Use solo zona / ciudad. **Nunca** dirección, nombre completo, o teléfono. El toolkit no inspecciona el valor, pero usted no debe poner PII de terceros.
- Audiencia, tema, idioma — nada se persiste. Cada invocación es independiente.

## Ejemplos

### CLI

```bash
# Carta para una madre en duelo en Lima
jw letter --kind letter \
          --topic "Una madre que perdió a su hijo" \
          --audience grieving \
          --lang es \
          --territory "Lima, Perú"

# Llamada telefónica sobre ansiedad
jw letter --kind phone --topic "ansiedad" --audience default --lang es

# Carrito para padres anglohablantes
jw letter --kind cart --topic "raising kids today" --audience parents --lang en
```

### Python

```python
import asyncio
from jw_agents.letter_composer import letter_composer

result = asyncio.run(letter_composer(
    kind="letter",
    language="es",
    topic_or_question="esperanza para una persona enferma",
    audience="grieving",
))
for f in result.findings:
    print(f.metadata["section"], "→", f.summary)
print("URL sugerido:", result.metadata["jw_link_suggested"])
print("Versículo:", result.metadata["suggested_scripture"])
```

### MCP (Claude Desktop)

```
Usuario: compose_witnessing kind=cart language=es topic="paz" audience=default
```

## Cómo se calibró

- 7 audiencias × 8 familias temáticas = hasta 56 combinaciones por modalidad.
- No están todas escritas — fallback en cadena: `(audience, family)` → `(audience, 'generic')` → `('default', 'generic')`.
- Tres familias específicas implementadas hoy: `(grieving, suffering)`, `(atheist, science)`, `(parents, family)`. PRs bienvenidos para añadir variantes.

## Para añadir una plantilla nueva

1. Edite el módulo apropiado (`letter_templates.py`, `phone_templates.py` o `cart_templates.py`).
2. Añada un `LetterTemplate` con las tres traducciones (`en`/`es`/`pt`).
3. Regístrelo en `TEMPLATES` con la clave `(audience, family)`.
4. Añada un caso L1 en `packages/jw-eval/fixtures/golden_qa/l1/` que valide la estructura.
5. Revise que pasa: `uv run jw eval --layer 1 --filter agent=letter_composer`.

## Métricas de uso

Tiempo y palabras objetivo son **datos informativos**, no reglas. El CLI los muestra con prefijo `~`. La métrica real la lleva usted: tiempo de pie en el carrito, longitud de la carta enviada.
