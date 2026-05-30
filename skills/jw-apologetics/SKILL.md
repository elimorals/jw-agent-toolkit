---
name: jw-apologetics
description: Answer doctrinal questions with verified citations from jw.org. Use when the user asks "¿qué dice la Biblia / Watch Tower sobre X?", "¿qué creemos sobre Y?", "respóndele a este argumento", or any topic that touches on JW doctrine (Trinity, soul, last days, blood, holidays, etc.).
---

# JW apologetics (verified citations)

Call the MCP tool `apologetics(question, language="E", topic_top_k=1, web_top_k=3, use_rag=True)`.

Source priority of the findings returned (use this for ranking in your
synthesis):

1. **`topic_index`** — Watch Tower Publications Index subject. The most
   authoritative source. If a finding has `metadata.source == "topic_index"`
   or `"topic_index_entry"`, surface its citation first.
2. **`question_refs`** — Bible references the user named.
3. **`verse_text`** — actual verse text fetched from wol.jw.org.
4. **`study_note`** — nwtsty commentary mapped to the verse.
5. **`cdn_search`** — articles found via search.
6. **`rag`** — local corpus (if anything is indexed).

## How to compose the answer

1. **Open with the JW position** — usually derived from a `topic_subject`
   or `topic_subheading` finding. Quote `excerpt` if non-empty.
2. **Back it with scripture** — pull from `question_refs` / `verse_text` /
   `study_note` findings. Quote the verse text verbatim and cite the
   `citation.url`.
3. **Cite jw.org articles** — for each `cdn_search` finding, name the
   article title (`citation.title`) and link `citation.url`.
4. **Never paraphrase doctrine from training data** without a backing
   citation. If no citation exists, say so explicitly.

## Boundaries

- For prep of a specific Watchtower Study, use `jw-meeting-prep`.
- For a single verse, use `jw-verse-lookup`.
- This skill is for **defending and explaining** JW positions using
  authoritative sources. It is not for personal opinion synthesis.

## Example

User: "¿Qué dice la Biblia sobre la Trinidad?"
→ Call `apologetics("¿Qué dice la Biblia sobre la Trinidad?", language="S")`.
→ The Trinity subject (185 subheadings, 563 citations) returns first.
→ Open with the JW position, quote 1Ti 2:5 / Juan 17:3 from the findings,
   cite ti (Should You Believe in the Trinity?) and recent w articles.
