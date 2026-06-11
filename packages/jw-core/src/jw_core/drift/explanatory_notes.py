"""Standard 'luz creciente' notes attached to every drift report (Fase 72)."""

from __future__ import annotations

EXPLANATORY_NOTE_ES = """
Los Testigos de Jehová consideran que la comprensión doctrinal se
refina con el tiempo, en armonía con Proverbios 4:18: "Pero la senda
de los justos es como la luz brillante que va aumentando hasta que el
día queda firmemente establecido". Los cambios reportados aquí
reflejan ese refinamiento, no contradicciones. Cada cita enlaza a
wol.jw.org para verificación directa.
""".strip()

EXPLANATORY_NOTE_EN = """
Jehovah's Witnesses understand that doctrinal understanding is
refined over time, in harmony with Proverbs 4:18: "But the path of
the righteous is like the bright morning light that grows brighter
and brighter until full daylight." The changes reported here reflect
that refinement, not contradictions. Each citation links to
wol.jw.org for direct verification.
""".strip()

EXPLANATORY_NOTE_PT = """
As Testemunhas de Jeová entendem que a compreensão doutrinal é
refinada com o tempo, em harmonia com Provérbios 4:18: "Mas a vereda
dos justos é como a luz brilhante da manhã, que brilha cada vez mais
clara até ficar pleno dia." As mudanças aqui reportadas refletem esse
refinamento, não contradições. Cada citação liga-se a wol.jw.org para
verificação direta.
""".strip()


def get_explanatory_note(language: str) -> str:
    """Return the explanatory note for the language, falling back to en."""

    return {
        "es": EXPLANATORY_NOTE_ES,
        "en": EXPLANATORY_NOTE_EN,
        "pt": EXPLANATORY_NOTE_PT,
    }.get(language, EXPLANATORY_NOTE_EN)
