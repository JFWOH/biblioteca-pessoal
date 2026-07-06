"""Testes do item 4 UX: limpeza do sumário + miniaturas de capítulos."""
from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QImage

from src.readers.base_reader import TOCEntry
from src.readers.toc_utils import clean_toc
from src.gui.widgets.toc_widget import TOCWidget


def _e(title, page=0, level=0):
    return TOCEntry(title=title, page=page, level=level)


# ── clean_toc (puro) ─────────────────────────────────────────────────

def test_clean_toc_drops_orphan_numbers():
    toc = [_e("INTRODUÇÃO inovação"), _e("CAPÍTULO 1 nada dura"), _e("1"),
           _e("2"), _e("- 3 -"), _e("7.")]
    cleaned = clean_toc(toc)
    assert [e.title for e in cleaned] == ["INTRODUÇÃO inovação", "CAPÍTULO 1 nada dura"]


def test_clean_toc_drops_empty_titles():
    assert clean_toc([_e(""), _e("   "), _e("Válido")])[0].title == "Válido"
    assert len(clean_toc([_e(""), _e("   "), _e("Válido")])) == 1


def test_clean_toc_keeps_titles_with_numbers():
    toc = [_e("Capítulo 1"), _e("1. Introdução"), _e("IV. A lógica"),
           _e("Seção 2.3", level=1)]
    assert len(clean_toc(toc)) == 4


def test_clean_toc_empty_input():
    assert clean_toc([]) == []


# ── TOCWidget com miniaturas ─────────────────────────────────────────

def _fake_png() -> bytes:
    img = QImage(10, 14, QImage.Format.Format_RGB32)
    img.fill(0xFF3355AA)
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def test_load_toc_sets_thumbnails_on_chapters(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    png = _fake_png()
    calls = []

    def provider(page, width):
        calls.append(page)
        return png

    w.load_toc([_e("Cap 1", page=0), _e("Seção", page=1, level=1),
                _e("Cap 2", page=5)], thumb_provider=provider)
    assert calls == [0, 5]  # só capítulos de nível 0
    assert not w.topLevelItem(0).icon(0).isNull()
    assert not w.topLevelItem(1).icon(0).isNull()
    # A seção (filha) não recebe miniatura
    assert w.topLevelItem(0).child(0).icon(0).isNull()


def test_load_toc_without_provider_is_text_only(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1")])
    assert w.topLevelItem(0).icon(0).isNull()
    assert w.topLevelItem(0).text(0) == "Cap 1"


def test_load_toc_provider_none_or_error_is_graceful(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)

    def broken(page, width):
        if page == 0:
            raise RuntimeError("render falhou")
        return None

    w.load_toc([_e("Cap 1", page=0), _e("Cap 2", page=1)], thumb_provider=broken)
    assert w.topLevelItemCount() == 2  # nada quebra; segue texto-só
    assert w.topLevelItem(0).icon(0).isNull()
    assert w.topLevelItem(1).icon(0).isNull()
