---
name: jw-meeting-prep
description: Prepare comments and study material for the weekly Watchtower Study or midweek meeting. Use when the user asks for "preparar la Atalaya", "preparar la reunión", "comentarios para la reunión", "estudio de esta semana", or shares a wol.jw.org article URL and asks for meeting prep.
---

# Meeting prep helper (jw.org)

Call the MCP tool `meeting_helper(input_text, language="es", max_paragraphs=8)`:

- If the user gives a **wol.jw.org URL** (the week's study article), pass it as is.
- If the user gives a **Bible reference** (e.g. "Juan 3:16"), pass that — the
  agent resolves it to the chapter and uses that as the source.

The tool returns `findings` (one per paragraph) and `metadata.prep_prompts`
(question stems for the user to think through). For each paragraph finding,
`metadata.suggest_comment` flags whether it's good for an early brief
comment or richer content for a longer one.

## Output for the user

Produce a structured prep document:

1. **Theme** — the article/chapter title (from `metadata.title` or `metadata.resolved_reference`).
2. **Paragraph-by-paragraph guide** — for each finding:
   - Paragraph number
   - The key point in 1 sentence
   - A comment suggestion if `metadata.suggest_comment` is non-empty
3. **Cross-references** — from `metadata.cross_references`, list the top 5.
4. **Questions to consider** — from `metadata.prep_prompts`.

Always cite the `citation.url` of every paragraph you reference.

## Boundaries

- For doctrinal Q&A use `jw-apologetics` instead.
- For a single-verse lookup use `jw-verse-lookup`.
- Default language is Spanish (`es`) for this user.
