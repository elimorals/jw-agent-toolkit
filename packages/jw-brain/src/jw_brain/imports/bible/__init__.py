"""Importador del knowledge graph bíblico desde fuentes JW puras
(Insight on the Scriptures + NWT/NWTsty + Topic Index).

NO usa LLMs en el path crítico: parsers procedurales sobre JWPUB ya descifrado.

Los re-exports concretos (BibleLoader, models, ...) se exponen conforme
los módulos se implementen en F58.2+. Mientras tanto el package es importable
como skeleton para que tests y futuros submódulos puedan habitarlo.
"""
