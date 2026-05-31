"""Low-level GBNF (GGML BNF) builders.

GBNF is the grammar format that llama.cpp consumes via
`--grammar-file` and that Ollama 0.5+ forwards under `options.grammar`.

We don't validate llama.cpp's own parser here — we just emit strings
that match its documented grammar. Validation happens at:
  - test time, via the regex-based mini-parser in tests, and
  - runtime, when the LLM provider rejects malformed grammars.
"""

from __future__ import annotations

from typing import Any

from jw_core.grammar.citation_grammar import citation_url_grammar
from jw_core.grammar.schemas import AgentResultModel, pydantic_to_gbnf


def escape_gbnf_string(s: str) -> str:
    """Escape a Python string for embedding in a GBNF string-literal."""

    out: list[str] = []
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        else:
            out.append(ch)
    return "".join(out)


def json_object_grammar(schema: dict[str, Any]) -> str:
    """Compile a tiny subset of JSON Schema (object with string/int/bool fields) to GBNF.

    Used as a generic helper. Production agents should prefer
    `pydantic_to_gbnf(AgentResultModel)`.
    """

    if schema.get("type") != "object":
        raise ValueError("json_object_grammar requires an object-shaped schema")

    props = schema.get("properties", {})
    if not props:
        return 'root ::= "{}"\n'

    fields = list(props.items())
    parts: list[str] = []
    for i, (name, sub) in enumerate(fields):
        ty = sub.get("type", "string")
        if ty == "string":
            val_rule = "string"
        elif ty == "integer":
            val_rule = "integer"
        elif ty == "number":
            val_rule = "number"
        elif ty == "boolean":
            val_rule = "boolean"
        else:
            raise ValueError(f"json_object_grammar: unsupported sub-type {ty!r}")
        sep = "" if i == len(fields) - 1 else ' "," ws'
        parts.append(f'ws "\\"{escape_gbnf_string(name)}\\"" ws ":" ws {val_rule}{sep}')

    rules = {
        "root": '"{" ' + " ".join(parts) + ' ws "}"',
        "ws": r"[ \t\n]*",
        "string": r"""'"' ( [^"\\] | "\\" ["\\bfnrt/] )* '"'""",
        "integer": r"""("-")? [0-9]+""",
        "number": r"""("-")? [0-9]+ ("." [0-9]+)?""",
        "boolean": r""" "true" | "false" """,
    }
    return "\n".join(f"{k} ::= {v}" for k, v in rules.items()) + "\n"


def bible_ref_grammar() -> str:
    """GBNF for the subset of Bible refs we accept across en/es/pt.

    Only the most common 66 books are covered. Unknown books raise no
    runtime error — they simply won't match.
    """

    books_en = [
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
        "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
        "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
        "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
        "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah", "Lamentations",
        "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
        "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
        "Zephaniah", "Haggai", "Zechariah", "Malachi",
        "Matthew", "Mark", "Luke", "John", "Acts",
        "Romans", "1 Corinthians", "2 Corinthians", "Galatians", "Ephesians",
        "Philippians", "Colossians", "1 Thessalonians", "2 Thessalonians", "1 Timothy",
        "2 Timothy", "Titus", "Philemon", "Hebrews", "James",
        "1 Peter", "2 Peter", "1 John", "2 John", "3 John",
        "Jude", "Revelation",
    ]  # fmt: skip
    books_es = [
        "Génesis", "Éxodo", "Levítico", "Números", "Deuteronomio",
        "Josué", "Jueces", "Rut", "1 Samuel", "2 Samuel",
        "1 Reyes", "2 Reyes", "1 Crónicas", "2 Crónicas", "Esdras",
        "Nehemías", "Ester", "Job", "Salmos", "Proverbios",
        "Eclesiastés", "Cantar de los Cantares", "Isaías", "Jeremías", "Lamentaciones",
        "Ezequiel", "Daniel", "Oseas", "Joel", "Amós",
        "Abdías", "Jonás", "Miqueas", "Nahúm", "Habacuc",
        "Sofonías", "Ageo", "Zacarías", "Malaquías",
        "Mateo", "Marcos", "Lucas", "Juan", "Hechos",
        "Romanos", "1 Corintios", "2 Corintios", "Gálatas", "Efesios",
        "Filipenses", "Colosenses", "1 Tesalonicenses", "2 Tesalonicenses", "1 Timoteo",
        "2 Timoteo", "Tito", "Filemón", "Hebreos", "Santiago",
        "1 Pedro", "2 Pedro", "1 Juan", "2 Juan", "3 Juan",
        "Judas", "Revelación",
    ]  # fmt: skip
    books_pt = [
        "Gênesis", "Êxodo", "Levítico", "Números", "Deuteronômio",
        "Josué", "Juízes", "Rute", "1 Samuel", "2 Samuel",
        "1 Reis", "2 Reis", "1 Crônicas", "2 Crônicas", "Esdras",
        "Neemias", "Ester", "Jó", "Salmos", "Provérbios",
        "Eclesiastes", "Cântico de Salomão", "Isaías", "Jeremias", "Lamentações",
        "Ezequiel", "Daniel", "Oseias", "Joel", "Amós",
        "Obadias", "Jonas", "Miqueias", "Naum", "Habacuque",
        "Sofonias", "Ageu", "Zacarias", "Malaquias",
        "Mateus", "Marcos", "Lucas", "João", "Atos",
        "Romanos", "1 Coríntios", "2 Coríntios", "Gálatas", "Efésios",
        "Filipenses", "Colossenses", "1 Tessalonicenses", "2 Tessalonicenses", "1 Timóteo",
        "2 Timóteo", "Tito", "Filêmon", "Hebreus", "Tiago",
        "1 Pedro", "2 Pedro", "1 João", "2 João", "3 João",
        "Judas", "Revelação",
    ]  # fmt: skip

    alts = sorted({b for b in (books_en + books_es + books_pt)})
    book_alts = " | ".join(f'"{escape_gbnf_string(b)}"' for b in alts)
    rules = {
        "root": ' "\\"" bible-ref "\\"" ',
        "bible-ref": ' book " " chapter (":" verse ("-" verse)?)?',
        "book": book_alts,
        "chapter": "[0-9]+",
        "verse": "[0-9]+",
    }
    return "\n".join(f"{k} ::= {v}" for k, v in rules.items()) + "\n"


def agent_result_grammar() -> str:
    """Convenience wrapper — compile the canonical AgentResultModel."""

    grammar = pydantic_to_gbnf(AgentResultModel)
    # The citation_url rule must be embedded for adapters that forward
    # the grammar string as-is.
    if "citation-url" not in grammar:
        grammar = grammar.rstrip() + "\n" + citation_url_grammar() + "\n"
    return grammar
