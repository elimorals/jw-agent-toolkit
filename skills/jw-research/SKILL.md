---
name: jw-research
description: Multi-step research on jw.org content — search publications, fetch articles, cross-reference verses, summarize with verified citations. Use when the user asks an open-ended doctrinal or topical question that needs more than one verse lookup.
---

# JW research (multi-step)

Workflow for open-ended research:

1. Call `search_content(query, filter_type="all", language=...)` with the
   user's topic stripped of question framing
   (e.g. "what does the Bible say about peace?" → search `"peace"`).
2. For the top 2-3 results that look most relevant, call `get_article(url)`
   to fetch the full article.
3. For every Bible reference mentioned in the user's question, call
   `resolve_reference` to get the canonical URL.
4. Synthesize the answer. **Every doctrinal claim MUST cite a verse or
   article URL returned by these tools.** Do not paraphrase from training
   data without a source.

## Boundaries

- If you cannot find verified sources, say so explicitly. Do not fall back
  to general knowledge.
- For a single verse, prefer `jw-verse-lookup` (lighter).
- For meeting prep specifically, prefer `jw-meeting-prep` (Phase 7).
