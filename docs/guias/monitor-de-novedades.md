# Monitor de novedades jw.org (`jw news digest`)

> Fase 25 — detector determinista de novedades en publicaciones, JW Broadcasting y programa mensual.
> Spec: `docs/superpowers/specs/2026-05-30-fase-25-news-monitor-design.md`.

## Para qué sirve

Te muestra qué hay nuevo en jw.org desde la última vez que ejecutaste el comando, sin tener que entrar manualmente a Atalaya, ¡Despertad!, tv.jw.org y WOL.

Tres canales:

| Canal | Qué detecta | TTL del catálogo |
|---|---|---|
| `publications` | Atalaya, ¡Despertad!, libros activos, brochures | 6h |
| `broadcasting` | Videos nuevos en tv.jw.org (raíz `VideoOnDemand`) | 24h |
| `programs` | Workbook `mwb_YYYYMM` y Atalaya estudio `w_YYYYMM` | 7 días |

## Uso

```bash
# Primera vez — marca todo como visto sin imprimir spam
jw news digest --since 2026-05-30 --languages en --channels publications --out /tmp/seed.md

# Uso normal — desde el último run
jw news digest

# Filtros
jw news digest --languages en,es --channels publications,programs

# Modo dry — no actualiza la base local
jw news digest --since epoch --no-update

# JSON para programar contra él
jw news digest --json > digest.json

# A archivo
jw news digest --out ~/Documents/jw-news/$(date +%F).md
```

### Argumentos clave

| Flag | Default | Notas |
|---|---|---|
| `--since` | `last_run` | También acepta `epoch` o una fecha ISO `2026-05-23` |
| `--languages` | `en,es,pt` | CSV de códigos ISO |
| `--channels` | `publications,broadcasting,programs` | CSV |
| `--out` | (stdout) | Path; crea padres |
| `--no-update` | `False` | No marca seen ni avanza `last_run` |
| `--json` | `False` | Emite envelope JSON en vez de markdown |

## Cron opcional

El toolkit **no** instala tareas automáticas. Si quieres digest semanal:

```cron
# Lunes 07:00 — digest a archivo
0 7 * * MON  /usr/local/bin/jw news digest --since last_run --out ~/Documents/jw-news/$(date +\%F).md
```

O con `systemd --user`:

```ini
# ~/.config/systemd/user/jw-news.timer
[Unit]
Description=Weekly JW news digest

[Timer]
OnCalendar=Mon 07:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# ~/.config/systemd/user/jw-news.service
[Unit]
Description=JW news digest

[Service]
Type=oneshot
ExecStart=/usr/local/bin/jw news digest --since last_run --out %h/Documents/jw-news/digest.md
```

## Tool MCP

Desde Claude Desktop / cualquier cliente MCP:

```
news_digest(since="last_run", languages=["en","es"], channels=["publications","programs"])
```

Devuelve un dict con `markdown` (ya formateado), `stats`, `findings` (con `citation.url` por item) y `warnings`.

## Estado local

- `~/.jw-agent-toolkit/news_seen.db` — SQLite con (channel, item_id, first_seen_at, last_seen_at). Override por env `JW_NEWS_SEEN_DB`.
- `~/.jw-agent-toolkit/cache.db` — caché HTTP de los clientes (compartido con el resto del toolkit).

Borra `news_seen.db` para resetear lo que ya viste (siguiente corrida tratará todo como nuevo).

## Troubleshooting

| Síntoma | Diagnóstico | Fix |
|---|---|---|
| Digest reporta cientos de items en la primera corrida | store vacío | Es lo esperado. Usa `--no-update` para inspeccionar o `--since 2026-05-30` para sellar la fecha como base. |
| Un `pub_code` da warning 404 | publicación descontinuada o pub_code antiguo en `seeds.py` | Sin acción; el warning es informativo. Audit anual de `seeds.py`. |
| `last_run` aparece como `None` | nunca corriste sin `--no-update` | Corre `jw news digest --since 2026-05-30` una vez. |
| Mismo día corrió 4 veces y satura la red | TTL del cache no se honra | Verifica que `DiskCache` no fue limpiada. Cache vive en `~/.jw-agent-toolkit/cache.db`. |
| `--since 2026-05-23` no filtra items "nuevos" | confusión esperada | `--since` afecta el header del digest. El diff real lo hace `news_seen.db`. |

## Política de privacidad

- Cero telemetría externa. Todo permanece en `~/.jw-agent-toolkit/`.
- El digest no contiene ningún dato personal — sólo metadata pública de jw.org.
