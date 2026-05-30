---
name: jw-daily-text
description: Fetch today's daily text (texto diario) from wol.jw.org. Use when the user asks for "el texto diario", "today's text", "texto de hoy", or to share/explain today's scripture and commentary.
---

# Daily text (jw.org)

Call the MCP tool `get_daily_text(language=...)`. It returns the date,
scripture reference + verse text, and a short commentary.

Default to Spanish (`language="es"`) for this user unless they specify
otherwise.

## Boundaries

- This skill only returns today's text. For a different date, this is not
  supported yet (Phase 2 will add it).
- The scripture is already cited within the response. Quote it verbatim.
