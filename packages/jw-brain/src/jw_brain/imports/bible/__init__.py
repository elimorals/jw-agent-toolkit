"""Importador del knowledge graph bíblico desde fuentes JW puras
(Insight on the Scriptures + NWT/NWTsty + Topic Index).

NO usa LLMs en el path crítico: parsers procedurales sobre JWPUB ya descifrado.

Los re-exports de runtime (BibleLoader, parsers) se añaden conforme los
módulos se implementen en F58.3+. Los modelos Pydantic intermediarios ya
están expuestos.
"""

from jw_brain.imports.bible.models import (
    BibleKgPassage,
    BibleKgPeriod,
    BibleKgPerson,
    BibleKgPlace,
    InsightEntry,
)

__all__ = [
    "BibleKgPassage",
    "BibleKgPeriod",
    "BibleKgPerson",
    "BibleKgPlace",
    "InsightEntry",
]
