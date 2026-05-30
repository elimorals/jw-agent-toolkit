---
name: jw-verse-lookup
description: Resolve a Bible reference in any language to its canonical wol.jw.org URL with structured book/chapter/verse data. Use whenever the user mentions a verse like "Juan 3:16", "Heb 13", or "1 Corinthians 13:4-7".
---

# Bible verse lookup (jw.org)

When the user mentions a Bible reference, call the MCP tool `resolve_reference`
with the raw text. It returns the canonical book number, chapter, verses, the
detected language, and a wol.jw.org URL.

If the user wants the verse *text* (not just the link), follow up with
`get_chapter(book_num, chapter, language=...)` and locate the verse inside
the returned paragraphs.

## Examples

- "What does Juan 3:16 say?" → `resolve_reference("Juan 3:16", language="es")`
  then `get_chapter(43, 3, language="es")`
- "Open Hebrews 13" → `resolve_reference("Hebrews 13")` then `get_chapter(58, 13)`

## Boundaries

- This skill handles single-verse lookup. For multi-verse research across
  publications, use `jw-research` instead.
- Always cite the wol.jw.org URL returned by the tool.
