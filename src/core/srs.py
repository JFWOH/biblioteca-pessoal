"""Repetição espaçada (SM-2 simplificado) para os flashcards — lógica pura.

Sem GUI / sem dependências externas (ADR-006). Recebe o estado de um card e uma
nota de revisão e devolve o novo estado + a próxima data de revisão.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

GRADES = ("again", "hard", "good", "easy")
GRADE_LABELS = {"again": "Errei", "hard": "Difícil", "good": "Bom", "easy": "Fácil"}

MIN_EASE = 1.3
DEFAULT_EASE = 2.5


@dataclass
class CardState:
    interval_days: int = 0
    ease: float = DEFAULT_EASE
    reps: int = 0
    lapses: int = 0


def review(state: CardState, grade: str, today: date | None = None) -> tuple[CardState, date]:
    """Aplica uma nota de revisão; devolve (novo estado, próxima data de revisão)."""
    if grade not in GRADES:
        raise ValueError(f"grade inválida: {grade}")
    today = today or date.today()

    interval = state.interval_days
    ease = state.ease
    reps = state.reps
    lapses = state.lapses

    if grade == "again":
        reps = 0
        lapses += 1
        ease = max(MIN_EASE, ease - 0.20)
        interval = 0  # revisar de novo hoje
    elif grade == "hard":
        ease = max(MIN_EASE, ease - 0.15)
        interval = max(1, round((interval or 1) * 1.2))
        reps += 1
    elif grade == "good":
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    else:  # easy
        ease = ease + 0.15
        interval = 4 if reps == 0 else max(1, round(interval * ease * 1.3))
        reps += 1

    new_state = CardState(
        interval_days=interval,
        ease=round(ease, 3),
        reps=reps,
        lapses=lapses,
    )
    return new_state, today + timedelta(days=interval)


def interval_label(days: int) -> str:
    """Rótulo curto para o intervalo (usado nos botões de nota)."""
    if days <= 0:
        return "hoje"
    if days == 1:
        return "1 dia"
    if days < 30:
        return f"{days} dias"
    months = round(days / 30)
    return "1 mês" if months == 1 else f"{months} meses"


def preview_intervals(state: CardState, today: date | None = None) -> dict[str, str]:
    """Pré-visualiza o próximo intervalo para cada nota possível (hint nos botões)."""
    return {g: interval_label(review(state, g, today)[0].interval_days) for g in GRADES}
