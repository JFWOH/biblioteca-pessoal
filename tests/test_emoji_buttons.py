"""Onda 0.1 — bug visual: emoji embutido no texto do botão.

No Windows, ``QPushButton("📖 Ler")`` renderiza o emoji sobreposto ao rótulo.
A correção leva o emoji como ÍCONE (``setIcon(emoji_icon(...))``) e mantém o
``.text()`` do botão SEM emoji. Ver ``src/gui/styles.py::emoji_icon``.

Cobertura:
- ``BookDetails``: widget leve → instanciado e inspecionado ao vivo (pytest-qt).
- ``ReaderView``: NÃO pode ser importado depois de existir uma QApplication
  (puxa ``QtWebEngineWidgets``); a suíte já contorna isso com checagem estática
  do fonte (ver ``tests/test_reader_view_guards.py``). Seguimos o mesmo padrão.
"""
import re
from pathlib import Path

from PyQt6.QtWidgets import QPushButton

from src.gui.book_details import BookDetails

# Faixas Unicode de emoji/pictogramas. NÃO inclui setas (← ◀ ▶ = U+2190/25xx),
# operadores (− ⋯ = U+2212/22EF) nem box-drawing (│ = U+2502): glifos
# monocromáticos usados de propósito, que renderizam sem o bug.
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # pictogramas, emoticons, transporte, símbolos ext.
    "\U00002300-\U000023FF"   # técnicos (⏸ ⏹ ⌛ …)
    "\U00002600-\U000027BF"   # símbolos diversos + dingbats (⚙ ⛶ ✅ ❌ …)
    "\U00002B00-\U00002BFF"   # setas/símbolos (⬜ ⭐ …)
    "\U0000FE00-\U0000FE0F"   # seletores de variação (VS16 → apresentação emoji)
    "]"
)

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"

# Botões de ação do BookDetails que passam a carregar o emoji como ícone.
_BOOK_DETAILS_ICON_BTNS = (
    "_open_btn", "_dossier_btn", "_fav_btn", "_col_btn",
    "_meta_btn", "_remove_col_btn", "_del_btn",
)


def _has_emoji(text: str) -> bool:
    return bool(_EMOJI.search(text or ""))


# ── BookDetails (widget ao vivo) ───────────────────────────────────────

def test_book_details_buttons_have_no_emoji_in_text(qtbot):
    panel = BookDetails(db=None)
    qtbot.addWidget(panel)

    buttons = panel.findChildren(QPushButton)
    assert buttons, "esperava botões de ação no BookDetails"
    for btn in buttons:
        assert not _has_emoji(btn.text()), f"emoji no texto do botão: {btn.text()!r}"

    # Os botões de ação levam o emoji como ícone (não como texto).
    for attr in _BOOK_DETAILS_ICON_BTNS:
        assert not getattr(panel, attr).icon().isNull(), f"{attr} sem ícone-emoji"


def test_book_details_favorite_toggle_keeps_text_clean(qtbot):
    """``show_book`` troca o texto do botão favoritar — deve seguir limpo."""
    panel = BookDetails(db=None)
    qtbot.addWidget(panel)
    for is_fav in (1, 0):
        panel.show_book({"id": 1, "title": "T", "is_favorite": is_fav})
        assert not _has_emoji(panel._fav_btn.text())
        assert not panel._fav_btn.icon().isNull()


# ── ReaderView (checagem estática do fonte) ────────────────────────────

def test_reader_view_buttons_have_no_emoji_in_text():
    """Nenhum ``QPushButton``/``QToolButton`` criado com emoji no texto e
    nenhum ``setText("…emoji…")`` no arquivo inteiro. Emoji só via
    ``setIcon(emoji_icon("…"))`` — que esta checagem não inspeciona.
    """
    src = _READER_VIEW.read_text(encoding="utf-8")
    offenders = []
    for m in re.finditer(r'Q(?:Push|Tool)Button\(\s*(["\'])(.*?)\1', src):
        if _has_emoji(m.group(2)):
            offenders.append(f"construtor: {m.group(2)!r}")
    for m in re.finditer(r'\.setText\(\s*(["\'])(.*?)\1', src):
        if _has_emoji(m.group(2)):
            offenders.append(f"setText: {m.group(2)!r}")
    assert not offenders, "emoji no texto de botões do reader_view:\n" + "\n".join(offenders)
