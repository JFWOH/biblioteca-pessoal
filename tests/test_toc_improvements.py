"""Testes do item 4 UX: limpeza do sumário + miniaturas de capítulos.

Onda P (ago/2026): as miniaturas deixaram de ser renderizadas na thread da GUI.
``load_toc`` só popula os itens; o ``ThumbnailWorker`` entrega as imagens depois.
"""
import re
from pathlib import Path

from PyQt6.QtCore import QBuffer
from PyQt6.QtGui import QImage

from src.readers.base_reader import TOCEntry
from src.readers.toc_utils import clean_toc
from src.gui.widgets.toc_widget import TOCWidget

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


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


# ── TOCWidget com miniaturas (assíncronas — Onda P) ──────────────────

def _fake_png() -> bytes:
    img = QImage(10, 14, QImage.Format.Format_RGB32)
    img.fill(0xFF3355AA)
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def test_load_toc_pede_miniaturas_so_dos_capitulos(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1", page=0), _e("Seção", page=1, level=1),
                _e("Cap 2", page=5)], with_thumbnails=True)
    assert w.pending_thumbnails() == [0, 5]  # só capítulos de nível 0


def test_load_toc_poe_placeholder_transparente(qtbot):
    """Onda P: o custo das miniaturas saiu de ``load_toc`` — o que fica é só o
    placeholder, que reserva a altura da linha para a miniatura real."""
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1", page=0), _e("Cap 2", page=4)], with_thumbnails=True)
    icone = w.topLevelItem(0).icon(0)
    assert not icone.isNull()
    imagem = icone.pixmap(44, 60).toImage()
    assert imagem.pixelColor(22, 30).alpha() == 0  # invisível de propósito


def test_set_thumbnail_aplica_no_item_correto(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1", page=0), _e("Seção", page=1, level=1),
                _e("Cap 2", page=5)], with_thumbnails=True)

    assert w.set_thumbnail(5, _fake_png()) is True
    # Página fora da lista (filha, ou livro já trocado) é descartada em silêncio.
    assert w.set_thumbnail(1, _fake_png()) is False
    assert w.set_thumbnail(99, _fake_png()) is False


def test_set_thumbnail_com_png_invalido_nao_quebra(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1", page=0)], with_thumbnails=True)
    assert w.set_thumbnail(0, b"nao sou um png") is False
    assert w.set_thumbnail(0, b"") is False
    assert w.topLevelItemCount() == 1


def test_load_toc_sem_miniaturas_e_texto_puro(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1")])
    assert w.pending_thumbnails() == []
    assert w.topLevelItem(0).icon(0).isNull()
    assert w.topLevelItem(0).text(0) == "Cap 1"


def test_teto_de_miniaturas_respeitado(qtbot):
    from src.gui.widgets.toc_widget import THUMB_MAX

    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e(f"Cap {i}", page=i) for i in range(THUMB_MAX + 15)],
               with_thumbnails=True)
    assert len(w.pending_thumbnails()) == THUMB_MAX
    assert w.topLevelItemCount() == THUMB_MAX + 15  # todas as entradas existem


def test_recarregar_toc_zera_a_fila_de_miniaturas(qtbot):
    w = TOCWidget()
    qtbot.addWidget(w)
    w.load_toc([_e("Cap 1", page=7)], with_thumbnails=True)
    w.load_toc([_e("Outro livro", page=3)], with_thumbnails=True)
    assert w.pending_thumbnails() == [3]
    assert w.set_thumbnail(7, _fake_png()) is False  # entrega atrasada, ignorada


# ── Ligação no ReaderView ────────────────────────────────────────────
# Checagens ESTÁTICAS: reader_view.py não pode ser importado depois de existir
# uma QApplication (puxa QtWebEngine) — mesmo padrão de
# tests/test_reader_view_guards.py e test_reader_navigation.py.

def _reader_view_src() -> str:
    return _READER_VIEW.read_text(encoding="utf-8")


def test_open_book_nao_renderiza_miniatura_na_thread_da_gui():
    src = _reader_view_src()
    assert "thumb_provider" not in src, (
        "open_book voltou a renderizar miniaturas em série na thread da GUI")
    assert "with_thumbnails=renderiza_miniatura" in src
    assert "self._start_thumbnail_worker(filepath)" in src


def test_worker_de_miniaturas_e_encerrado_na_troca_e_no_fechamento():
    src = _reader_view_src()
    # start sempre para o anterior antes de criar o novo (troca de livro)…
    inicio = re.search(r"def _start_thumbnail_worker\(self.*?\n    def ",
                       src, re.DOTALL)
    assert inicio and "self._stop_thumbnail_worker()" in inicio.group(0)
    # …e close_reader (chamado pelo closeEvent da janela) também encerra.
    fechamento = re.search(r"def close_reader\(self\):.*?\n    def ", src, re.DOTALL)
    assert fechamento and "self._stop_thumbnail_worker()" in fechamento.group(0)


def test_entrega_atrasada_de_worker_aposentado_e_descartada():
    """Desconectar não cancela sinais JÁ postados na fila da GUI — por isso o
    slot confere ``sender()`` antes de aplicar a miniatura."""
    src = _reader_view_src()
    slot = re.search(r"def _on_thumbnail_ready\(self.*?\n    def ", src, re.DOTALL)
    assert slot and "self.sender() is not self._thumbnail_worker" in slot.group(0)
