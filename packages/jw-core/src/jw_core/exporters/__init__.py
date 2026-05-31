"""Convert AgentResult into printable study sheets and Anki decks.

Public API:
    from jw_core.exporters import StudySheet
    from jw_core.exporters.markdown import export_markdown
    from jw_core.exporters.pdf import export_pdf            # needs [pdf]
    from jw_core.exporters.docx import export_docx          # needs [docx]
    from jw_core.exporters.anki import export_apkg          # needs [anki]

Design: every exporter consumes a `StudySheet` (the single IR). The
`AgentResult → StudySheet` conversion lives in `ir.from_agent_result`.

Heavy dependencies (weasyprint, python-docx, genanki) are imported lazily
inside each exporter function, so importing this package never fails when
the extras are not installed.
"""

from jw_core.exporters.errors import ExportError, MissingDependencyError
from jw_core.exporters.ir import CitationIR, StudySection, StudySheet

__all__ = [
    "CitationIR",
    "ExportError",
    "MissingDependencyError",
    "StudySection",
    "StudySheet",
]
