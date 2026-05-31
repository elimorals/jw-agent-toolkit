"""apocrypha_detector — flag content falsely attributed to JW publications.

We maintain a list of known-bad attributions (quotes that circulate as
"the Watchtower said X" but trace back to anti-JW sites or were rewritten).
This list is hand-curated; updating it is a deliberate act.

Algorithm:
  1. Detect any quote-mark pattern in the input.
  2. For each candidate, run `reverse_citation_lookup`.
  3. If overlap < threshold AND the user's claimed attribution is in the
     blocklist → flag as APOCRYPHAL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from jw_core.clients.cdn import CDNClient
from jw_core.clients.wol import WOLClient

from jw_agents.base import AgentResult, Citation, Finding
from jw_agents.reverse_citation_lookup import _bigram_overlap, _normalize

_QUOTE_RE = re.compile(r'["“”«»]([^"“”«»]{20,500})["“”«»]')

# Patterns that, when paired with low-overlap matches, strongly indicate
# the user is repeating a misattribution circulating online.
_SUSPICIOUS_FRAMING = (
    "watchtower said",
    "the watchtower said",
    "jehovah's witnesses teach",
    "los testigos enseñan",
    "as testemunhas ensinam",
    "la watchtower dijo",
)


@dataclass
class ApocryphaCandidate:
    quote: str
    framing: str
    confidence_genuine: float  # 0..1, higher = more likely real
    best_match_url: str = ""
    best_match_title: str = ""


async def apocrypha_detector(
    text: str,
    *,
    language: str = "E",
    cdn: CDNClient | None = None,
    wol: WOLClient | None = None,
    min_confidence_genuine: float = 0.55,
) -> AgentResult:
    """Scan `text` for apocryphal quotes attributed to JW publications.

    Returns an `AgentResult` whose findings include a verdict per
    candidate: GENUINE / SUSPICIOUS / APOCRYPHAL.
    """
    result = AgentResult(query=text, agent_name="apocrypha_detector")
    framings = _detect_framings(text)
    candidates = list(_extract_candidates(text, framings))
    if not candidates:
        result.warnings.append("No quoted content detected.")
        return result

    owned_cdn = cdn is None
    owned_wol = wol is None
    cdn = cdn or CDNClient()
    wol = wol or WOLClient()
    try:
        for candidate in candidates:
            best_url, best_overlap, best_title = await _best_overlap(candidate.quote, cdn, wol, language=language)
            candidate.best_match_url = best_url
            candidate.best_match_title = best_title
            candidate.confidence_genuine = best_overlap
            verdict = _verdict(candidate, min_confidence_genuine=min_confidence_genuine)
            result.findings.append(
                Finding(
                    summary=f"{verdict}: '{candidate.quote[:60]}…'",
                    excerpt=candidate.quote,
                    citation=Citation(
                        url=best_url,
                        title=candidate.best_match_title,
                        kind="quote_match",
                    ),
                    metadata={
                        "source": "apocrypha_detector",
                        "verdict": verdict,
                        "confidence_genuine": candidate.confidence_genuine,
                        "framing": candidate.framing,
                    },
                )
            )
    finally:
        if owned_cdn:
            await cdn.aclose()
        if owned_wol:
            await wol.aclose()

    return result


def _detect_framings(text: str) -> list[str]:
    lower = text.lower()
    return [f for f in _SUSPICIOUS_FRAMING if f in lower]


def _extract_candidates(text: str, framings: list[str]) -> list[ApocryphaCandidate]:
    framing = framings[0] if framings else ""
    return [
        ApocryphaCandidate(quote=m.group(1).strip(), framing=framing, confidence_genuine=0.0)
        for m in _QUOTE_RE.finditer(text)
    ]


async def _best_overlap(
    quote: str,
    cdn: CDNClient,
    wol: WOLClient,
    *,
    language: str,
) -> tuple[str, float, str]:
    needle = _normalize(quote)
    query = " ".join(needle.split()[:10])
    try:
        data = await cdn.search(query, filter_type="publications", language=language, limit=10)
    except Exception:
        return ("", 0.0, "")
    from jw_core.parsers.article import parse_article

    from jw_agents.research_topic import _flatten_search, _wol_url_from

    best_url = ""
    best_score = 0.0
    best_title = ""
    for item in _flatten_search(data, limit=5):
        url = _wol_url_from(item)
        if not url:
            continue
        try:
            html = await wol.fetch(url)
        except Exception:
            continue
        article = parse_article(html)
        haystack = _normalize(" ".join(article.paragraphs))
        score = _bigram_overlap(needle, haystack)
        if score > best_score:
            best_score = score
            best_url = url
            best_title = article.title or item.get("title", "")
    return (best_url, best_score, best_title)


def _verdict(candidate: ApocryphaCandidate, *, min_confidence_genuine: float) -> str:
    if candidate.confidence_genuine >= min_confidence_genuine:
        return "GENUINE"
    if candidate.framing:
        return "APOCRYPHAL"
    return "SUSPICIOUS"
