"""Genera un PDF de 1-2 páginas con texto sintético + 1 tabla mini
para tests del marker loader.

Para regenerar:
    cd packages/jw-rag/tests/fixtures/pdf
    uv run --with reportlab python build_sample_pdf.py

Requiere reportlab (dep dev). El PDF resultante simula el layout de
una página de Atalaya histórica (encabezado + tabla simple) pero el
contenido es Lorem-ipsum-style para evitar issues de copyright en tests.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).parent
OUTPUT = HERE / "atalaya_sample.pdf"

LOREM_HEADER = "Sample Article Heading (synthetic, not JW content)"
LOREM_P1 = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate."
)
LOREM_P2 = (
    "At vero eos et accusamus et iusto odio dignissimos ducimus qui blanditiis "
    "praesentiunt voluptatum deleniti atque corrupti quos dolores et quas "
    "molestias excepturi sint occaecati cupiditate non provident."
)


def main() -> None:
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=LETTER, title="Sample fixture")
    styles = getSampleStyleSheet()
    story = [
        Paragraph(LOREM_HEADER, styles["Heading1"]),
        Spacer(1, 12),
        Paragraph(LOREM_P1, styles["BodyText"]),
        Spacer(1, 12),
        Paragraph(LOREM_P2, styles["BodyText"]),
        Spacer(1, 18),
        Paragraph("Table 1 — example", styles["Heading3"]),
    ]
    table_data = [
        ["Year", "Event", "Reference"],
        ["1914", "World War I begins", "Lorem 1:1"],
        ["1919", "Treaty signed", "Lorem 1:2"],
        ["1925", "Sample event", "Lorem 1:3"],
    ]
    t = Table(table_data, colWidths=[60, 250, 100])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.append(t)
    doc.build(story)
    print(f"Wrote {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
