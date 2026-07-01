"""Testes da repetição espaçada (SM-2 simplificado)."""
from datetime import date

import pytest

from src.core.srs import (
    CardState, review, GRADES, interval_label, preview_intervals,
    DEFAULT_EASE, MIN_EASE,
)


def test_grades_constant():
    assert GRADES == ("again", "hard", "good", "easy")


def test_good_progression():
    s = CardState()  # novo
    s1, due1 = review(s, "good", date(2026, 1, 1))
    assert s1.interval_days == 1 and s1.reps == 1
    assert due1 == date(2026, 1, 2)
    s2, _ = review(s1, "good", date(2026, 1, 1))
    assert s2.interval_days == 6 and s2.reps == 2
    s3, _ = review(s2, "good", date(2026, 1, 1))
    assert s3.interval_days == 15  # round(6 * 2.5)


def test_again_resets_and_lowers_ease():
    s = CardState(interval_days=10, ease=2.5, reps=3, lapses=0)
    s1, due = review(s, "again", date(2026, 1, 1))
    assert s1.reps == 0
    assert s1.lapses == 1
    assert s1.interval_days == 0
    assert due == date(2026, 1, 1)  # revisar hoje
    assert s1.ease == 2.3


def test_ease_has_floor():
    s = CardState(ease=1.35)
    s1, _ = review(s, "again")
    assert s1.ease == MIN_EASE


def test_easy_new_card():
    s = CardState()
    s1, _ = review(s, "easy", date(2026, 1, 1))
    assert s1.interval_days == 4
    assert s1.ease == round(DEFAULT_EASE + 0.15, 3)


def test_invalid_grade_raises():
    with pytest.raises(ValueError):
        review(CardState(), "nope")


def test_interval_label():
    assert interval_label(0) == "hoje"
    assert interval_label(1) == "1 dia"
    assert interval_label(6) == "6 dias"
    assert interval_label(30) == "1 mês"
    assert interval_label(60) == "2 meses"


def test_preview_has_all_grades():
    p = preview_intervals(CardState())
    assert set(p.keys()) == set(GRADES)
