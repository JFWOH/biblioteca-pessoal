import os

import pytest
from PyQt6.QtCore import QCoreApplication, QEvent
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import QLabel

from src.gui.widgets.book_card import BookCard

@pytest.fixture
def app(qtbot):
    # qtbot fixture comes from pytest-qt
    return qtbot

def test_book_card_init_normal(qtbot):
    data = {"id": 1, "title": "Normal Book", "file_path": __file__}  # Usa o próprio teste como arquivo existente
    card = BookCard(data)
    qtbot.addWidget(card)
    
    assert card.is_broken is False
    assert card.is_selected is False
    assert card.book_data == data

def test_book_card_init_broken(qtbot):
    data = {"id": 2, "title": "Ghost Book", "file_path": "/caminho/falso/que/nao/existe.epub"}
    card = BookCard(data)
    qtbot.addWidget(card)
    
    assert card.is_broken is True
    # toolTip is set
    assert "⚠️" in card.toolTip()

def test_book_card_selection(qtbot):
    data = {"id": 1, "title": "Normal Book", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)

    with qtbot.waitSignal(card.selected_changed, timeout=1000) as blocker:
        card.set_selected(True)

    assert blocker.args == [1, True]
    assert card.is_selected is True

    card.set_selected(False)
    assert card.is_selected is False


# ── update_book (reciclagem in-place, rodada 4 perf/gui + auditoria) ────────

def _flush_deferred():
    """Consome os deleteLater pendentes (fora de um event loop rodando,
    processEvents sozinho não entrega DeferredDelete — mesmo racional do
    _flush em tools/profile_transitions.py)."""
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _make_cover(path, color):
    pm = QPixmap(8, 8)
    pm.fill(QColor(color))
    pm.save(str(path), "PNG")


def test_update_book_equal_dict_resets_selection(qtbot):
    """Auditoria B1: dict igual + card selecionado NÃO pode deixar seleção
    fantasma (a view já limpou _selected_ids antes de reciclar)."""
    data = {"id": 1, "title": "Livro", "file_path": __file__}
    card = BookCard(data)
    qtbot.addWidget(card)
    card.set_selected(True)

    card.update_book(dict(data))  # conteúdo idêntico → curto-circuito

    assert card.is_selected is False


def test_update_book_equal_dict_rechecks_broken(qtbot, tmp_path):
    """Auditoria B2: mesmo com dict igual, o DISCO pode ter mudado — o broken
    é re-checado e, se divergiu, o card é reconstruído (na main cada refresh
    re-checava; um arquivo deletado não pode ficar 'saudável' para sempre)."""
    f = tmp_path / "livro.pdf"
    f.write_bytes(b"x")
    data = {"id": 1, "title": "Livro", "file_path": str(f)}
    card = BookCard(data)
    qtbot.addWidget(card)
    assert card.is_broken is False

    f.unlink()                     # arquivo some do disco entre refreshes
    card.update_book(dict(data))   # dict IGUAL

    assert card.is_broken is True
    assert "⚠️" in card.toolTip()


def test_update_book_reuses_cover_when_unchanged(qtbot, tmp_path):
    """A capa (load+scale de QPixmap, a parte cara) é reaproveitada quando
    path e mtime não mudaram — mesmo com o resto do card reconstruído."""
    cover = tmp_path / "cover.png"
    _make_cover(cover, "#ff0000")
    data = {"id": 1, "title": "Um", "file_path": __file__,
            "cover_path": str(cover)}
    card = BookCard(data)
    qtbot.addWidget(card)
    label_before = card._cover_label

    card.update_book({**data, "title": "Outro"})  # rebuild, capa intacta

    assert card._cover_label is label_before


def test_update_book_reloads_cover_when_mtime_changes(qtbot, tmp_path):
    """Auditoria B3: capas são sobrescritas no MESMO caminho
    (covers/cover_{id}.jpg) — o mtime na chave força a recarga do pixmap."""
    cover = tmp_path / "cover.png"
    _make_cover(cover, "#ff0000")
    data = {"id": 1, "title": "Um", "file_path": __file__,
            "cover_path": str(cover)}
    card = BookCard(data)
    qtbot.addWidget(card)
    label_before = card._cover_label

    _make_cover(cover, "#00ff00")  # capa nova, mesmo caminho
    st = cover.stat()
    # mtime explícito (+1ms): não depende da resolução do relógio/filesystem.
    os.utime(cover, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    card.update_book({**data, "title": "Outro"})

    assert card._cover_label is not label_before


def test_update_book_renders_new_title_and_author(qtbot):
    """O card reciclado tem título/autor RENDERIZADOS (QLabels) atualizados —
    não basta o dict interno mudar (uma regressão em _build_contents passaria
    despercebida se o teste só olhasse book_data)."""
    card = BookCard({"id": 1, "title": "Título Antigo", "author": "Autor Antigo",
                     "file_path": __file__})
    qtbot.addWidget(card)

    card.update_book({"id": 2, "title": "Título Novo", "author": "Autor Novo",
                      "file_path": __file__})
    _flush_deferred()  # destrói de fato os QLabels antigos (deleteLater)

    texts = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert "Título Novo" in texts
    assert "Autor Novo" in texts
    assert "Título Antigo" not in texts
    assert "Autor Antigo" not in texts
