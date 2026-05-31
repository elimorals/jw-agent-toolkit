# Generación ilustrativa con `jw-gen`

> **Política aprobada por el usuario (LOAD-BEARING):**
> "Solo personal/ilustrativo + presentaciones/discursos. Watermark obligatorio.
>  NO emulación contenido oficial JW."

## Qué hace y qué no hace

`jw-gen` genera **imágenes, audio y video ilustrativos para uso personal** (presentaciones
familiares, discursos públicos, repaso). Cada archivo escrito a disco lleva:
- Watermark visible + EXIF/XMP, ó al menos EXIF/XMP si se desactiva el visible.
- Disclaimer hermano `*.disclaimer.txt` en es / en / pt.
- Entrada en `~/.jw-gen/audit.log` con timestamp + hash del prompt.

`jw-gen` **no**:
- Distribuye pesos de modelos generativos.
- Publica automáticamente en jw.org ni redes.
- Emula logos, emblemas o identidad gráfica de Watchtower / Awake! / jw.org / Kingdom Hall.
- Clona voces de hermanos sin doble opt-in firmado.
- Genera rostros fotorrealistas por defecto.

## Uso típico

```bash
# Imagen ilustrativa para un slide.
jw gen image --prompt "ovejas pastoreadas en una colina al atardecer" --out slide_01.png

# Audio de fondo para un slide de oración.
jw gen audio --prompt "música suave instrumental 30s" --out bg.wav

# Video corto de transición.
jw gen video --prompt "amanecer simbólico" --duration 6 --out transition.mp4
```

## Flags de seguridad

| Flag | Efecto |
|---|---|
| `--no-visible-watermark` | Mantiene EXIF/XMP+disclaimer, retira el watermark visible. Loguea audit. |
| `--realistic-people` | Salta el sufijo anti-realismo. Loguea audit. |
| `--voice-clone --input voz.wav` | Requiere `voz.wav.consent.txt` firmado + confirmación. |

## Lista de keywords bloqueadas

Ver `packages/jw-gen/src/jw_gen/i18n/{en,es,pt}.json` clave `logo_keywords`. Cualquier prompt
que contenga estas frases (normalizadas: sin acentos, minúsculas) o cualquier brand-word JW
junto a "logo / emblema / oficial" dentro de una ventana corta es rechazado.

## Ejemplo de consent file para voice clone

```
voice_owner: Hermano Juan
date: 2026-05-31
purpose: ensayar discurso público antes de darlo en vivo
signature_sha256: <sha256 de las 3 líneas anteriores, sin la 4ª>
```

El hash se calcula sobre el texto literal `"voice_owner: ...\ndate: ...\npurpose: ...\n"`.
