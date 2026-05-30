# jw-cli

CLI de terminal sobre `jw-core`. Implementado con [Typer](https://typer.tiangolo.com/) + [Rich](https://rich.readthedocs.io/).

## Comandos

| Comando | Descripción |
|---|---|
| `jw verse "<ref>"` | Parsea una referencia bíblica y muestra estructura canónica + URL de wol.jw.org |
| `jw chapter <book_num> <chapter>` | Descarga y muestra un capítulo bíblico |
| `jw daily` | Muestra el texto diario de hoy |
| `jw search "<query>"` | Búsqueda en jw.org vía la API CDN |
| `jw languages` | Lista los idiomas soportados por jw.org |
| `jw download <pub_code>` | Descarga una publicación en el formato pedido |
| `jw jwpub <path>` | Inspecciona un JWPUB local (TOC) o decrypta su texto con `--extract` |
| `jw topic <query>` | Busca temas en el Índice de Publicaciones Watch Tower y fetcha el top subject |

## Ejemplos

```bash
# Resolver una cita y mostrar la URL canónica en español
jw verse "Juan 3:16" --lang es

# Descargar el capítulo 3 de Juan (libro 43) en español
jw chapter 43 3 --lang es

# Texto diario en portugués
jw daily --lang pt

# Buscar "amor" en publicaciones en español
jw search "amor" --filter publications --lang es

# Listar idiomas con contenido web disponible
jw languages --web

# Descargar el folleto "Good News" en EPUB español
jw download fg --lang S --format EPUB --out ./descargas/

# Inspeccionar la TOC de un JWPUB descargado
jw jwpub ./descargas/ti_E.jwpub

# Decryptar y mostrar los primeros 3 documentos del JWPUB
jw jwpub ./descargas/ti_E.jwpub --extract --max 3

# Buscar el tema "Trinity" y mostrar el top subject con sus subheadings
jw topic "Trinity" --lang E --limit 5 --max-sub 15

# Sólo el ranking de candidatos, sin descargar la página de tema
jw topic "Trinity" --no-fetch
```

## Instalación local

```bash
uv sync --all-packages
uv run jw --help
```

## Referencia detallada

Ver [`docs/referencia/jw-cli.md`](../../docs/referencia/jw-cli.md) para la documentación exhaustiva de cada comando, opciones y códigos de salida.
