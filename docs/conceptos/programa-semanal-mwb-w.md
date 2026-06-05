# Programa semanal mwb/w — análisis arquitectónico

> Observaciones públicas sobre cómo wol.jw.org expone los programas
> semanales de reuniones congregacionales. Base del parser de F57.
> Documento creado clean-room, sin lectura de código del proyecto
> upstream M³ (sircharlo/meeting-media-manager, AGPL-3.0).

## URLs canónicas

```
Workbook (Vida y Ministerio Cristianos):
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}

Watchtower de estudio:
    https://wol.jw.org/{lang}/wol/meetings/{resource}/{lp_tag}/{year}/{week_num}?wtsy=1
```

Donde `{resource}` y `{lp_tag}` vienen del registry de idiomas (F1,
`jw_core.languages.get_language`). Ejemplos:

| Idioma | resource | lp_tag |
|---|---|---|
| Inglés | `r1` | `lp-e` |
| Español | `r4` | `lp-s` |
| Portugués | `r5` | `lp-t` |
| Francés | `r30` | `lp-f` |

La URL de "meetings" funciona como un índice. Devuelve enlaces al
workbook (mwb) y a la Atalaya (w) de la semana, normalmente como
`<a class="jwac ... pub-mwb ...">` o similar. Para parsear el
contenido detallado del programa hay que seguir esos enlaces hasta el
documento JWPUB renderizado en `/wol/d/...`.

## Estructura HTML del workbook semanal observada

Inspeccionada con DevTools del browser sobre la página pública del
WOL (sin login). Elementos clave del documento workbook renderizado:

```html
<article id="article" class="article document ...">
  <header>
    <h2>JEREMÍAS 1-3</h2>
  </header>
  <div class="bodyTxt">
    <h3 id="p3" data-pid="3">Canción 84 y oración | Palabras de introducción (1 min.)</h3>

    <div id="tt7" class="dc-icon--gem ...">
      <h2>TESOROS DE LA BIBLIA</h2>
    </div>
    <div id="tt9" class="...">
      <h3>1. "No te dejes intimidar..."</h3>
      <p>... <a class="b" href="/wol/bc/...">Jer 1:8</a> ...</p>
      <img src="/es/wol/mp/.../200" alt="..." />
    </div>
    <h3 id="p10">2. Busquemos perlas escondidas</h3>
    ...

    <div id="tt30" class="dc-icon--wheat ...">
      <h2>SEAMOS MEJORES MAESTROS</h2>
    </div>
    ...

    <div id="tt38" class="dc-icon--sheep ...">
      <h2>NUESTRA VIDA CRISTIANA</h2>
    </div>
    ...
  </div>
</article>
```

Características útiles para parsear:

- `<article>` y `<div class="bodyTxt">` son el contenedor estable.
- Los **section headers** son `<h2>` envueltos en `<div>` con clases
  `dc-icon--gem` (Tesoros), `dc-icon--wheat` (Seamos), `dc-icon--sheep`
  (Nuestra Vida). Esa convención de icono+color sirve como discriminador.
- Los **items** del programa son `<h3>` con id `pNN` numerado por
  párrafo y `data-pid`. El número (1, 2, 3, …) aparece en el texto
  del h3.
- Las **canciones** aparecen como `<h3>` con clase `dc-icon--music`.
- El **título del documento** (cita bíblica, p.ej. `JEREMÍAS 1-3`)
  está en `<header><h2>`, no es una sección.

## Refs identificables

| Marcador | Significado | Cómo identificar |
|---|---|---|
| `<a class="b" href="/wol/bc/...">` | Cita bíblica | `class="b"` |
| `<a class="jsRef" href="/wol/d/...">` | Documento JWPUB | Anchor con `/wol/d/` y `lp-` en href |
| `<a href="/wol/mp/...">` | Media item (thumbnail/poster) | `href` con `/wol/mp/` |
| `<img src=".../wol/mp/...">` | Imagen ilustrativa | Imagen servida desde `/wol/mp/` o `imgp.jw-cdn.org` |

El parser de F57 (`MeetingProgramClient.parse_html`) busca esos
patrones para poblar `MediaRef` y `BibleRef` por item.

## Cambios de layout

El layout HTML del WOL ha cambiado entre 1 y 2 veces por año en
ciclos recientes. El parser de F57 mitiga el riesgo con:

- Selectores múltiples (preferimos `class="bodyTxt"` pero también
  el `<article>` directo como fallback).
- Detección por iconos `dc-icon--*` (gem/wheat/sheep/music) que han
  permanecido estables al menos desde el rediseño 2024.
- Fallback heurístico: cualquier `<h2>` dentro de un `<div>` cuyo
  texto esté en mayúsculas se trata como section header.
- Capturar fixture HTML real (`packages/jw-meeting-media/tests/fixtures/`)
  versionado por fecha cuando se redescubra un cambio.

## NO usado en F57 MVP

- Endpoints internos de `jw.org/apps/finder` o `jworg-search` que
  requieren JWT y no están documentados públicamente.
- API binaria de la app oficial JW Library (network capture muestra
  protobuf — propietario).
- WebSockets de `wol.jw.org` (no encontrados, no usados).

Esos endpoints quedan para sprints futuros si MVP necesita features no
cubrables vía parsing del HTML público del WOL.
