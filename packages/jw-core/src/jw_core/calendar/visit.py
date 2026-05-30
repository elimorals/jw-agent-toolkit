"""Checklists for circuit overseer + elder visits.

These are LOCALIZED CHECKLISTS — not prose. The LLM presents them as
the publisher prepares for the visit.
"""

from __future__ import annotations


def circuit_overseer_checklist(language: str = "en") -> list[dict[str, str]]:
    items = {
        "en": [
            ("week_minus_4", "Confirm the visit dates with elders"),
            ("week_minus_3", "Review prior visit notes from your file"),
            ("week_minus_2", "Increase ministry hours where realistic"),
            ("week_minus_1", "Print invitations for the public talk"),
            ("week_of", "Arrive early for each meeting; greet visiting brother"),
            ("post_visit", "Apply the brother's specific suggestions in the next month"),
        ],
        "es": [
            ("week_minus_4", "Confirmar fechas con los ancianos"),
            ("week_minus_3", "Revisar las notas de la visita anterior"),
            ("week_minus_2", "Aumentar las horas de predicación cuando sea posible"),
            ("week_minus_1", "Imprimir invitaciones para el discurso público"),
            ("week_of", "Llegar temprano a cada reunión; saludar al hermano visitante"),
            ("post_visit", "Aplicar las sugerencias concretas durante el mes siguiente"),
        ],
        "pt": [
            ("week_minus_4", "Confirmar as datas com os anciãos"),
            ("week_minus_3", "Reler suas anotações da visita anterior"),
            ("week_minus_2", "Aumentar as horas no campo quando possível"),
            ("week_minus_1", "Imprimir convites para o discurso público"),
            ("week_of", "Chegar cedo às reuniões; cumprimentar o irmão visitante"),
            ("post_visit", "Aplicar as sugestões específicas no mês seguinte"),
        ],
    }
    pairs = items.get(language, items["en"])
    return [{"id": k, "task": v} for k, v in pairs]


def elder_visit_checklist(language: str = "en") -> list[dict[str, str]]:
    items = {
        "en": [
            ("hospitality", "Tidy main room; have a printed copy of the latest Watchtower"),
            ("agenda", "Write 2-3 questions you want spiritual help with"),
            ("listen", "Take notes during the visit; ask clarifying questions"),
            ("follow_up", "Schedule next step within 7 days"),
        ],
        "es": [
            ("hospitality", "Ordene la sala; tenga a mano la última Watchtower impresa"),
            ("agenda", "Anote 2-3 preguntas en las que quiere ayuda espiritual"),
            ("listen", "Tome notas durante la visita; pida aclaraciones"),
            ("follow_up", "Agende el próximo paso en 7 días"),
        ],
        "pt": [
            ("hospitality", "Organize a sala; tenha a última Sentinela impressa"),
            ("agenda", "Escreva 2-3 perguntas com as quais quer ajuda espiritual"),
            ("listen", "Faça anotações durante a visita; peça esclarecimentos"),
            ("follow_up", "Agende o próximo passo em 7 dias"),
        ],
    }
    pairs = items.get(language, items["en"])
    return [{"id": k, "task": v} for k, v in pairs]
