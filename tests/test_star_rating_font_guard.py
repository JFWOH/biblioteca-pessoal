"""Achado B0 — guard do único setPointSize COMPUTADO do projeto.

``StarRating._setup_ui`` fazia ``font.setPointSize(self._size // 2)``. Para
``size <= 1`` o valor vira 0/-1 e o Qt emite no console
``QFont::setPointSize: Point size <= 0``. O guard ``max(1, ...)`` evita o
warning sem mudar a renderização nos tamanhos normais (o único uso real hoje é
``size=18`` → pointSize 9).
"""
import pytest

from PyQt6.QtCore import qInstallMessageHandler

from src.gui.widgets.star_rating import StarRating


@pytest.mark.parametrize("size", [0, 1, 2, 18, 20])
def test_star_font_point_size_never_below_one(qtbot, size):
    w = StarRating(rating=3, size=size)
    qtbot.addWidget(w)
    assert w._stars, "esperado pelo menos uma estrela"
    for star in w._stars:
        assert star.font().pointSize() >= 1


def test_small_size_emits_no_point_size_warning(qtbot):
    msgs = []
    old = qInstallMessageHandler(lambda mode, ctx, m: msgs.append(m))
    try:
        w = StarRating(rating=2, size=1)  # size//2 == 0 sem o guard
        qtbot.addWidget(w)
    finally:
        qInstallMessageHandler(old)
    assert not any("oint size" in m for m in msgs), msgs
