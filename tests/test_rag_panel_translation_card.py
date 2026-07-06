"""Testes do cartão de tradução no painel do assistente (substitui QMessageBox)."""
from src.gui.widgets.rag_panel import RAGPanel


def test_show_translation_card_contains_header_and_text(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.show_translation_card("Seleção (42 caracteres)", "Hello world", "Olá mundo")
    text = panel._response_area.toPlainText()
    assert "Tradução" in text
    assert "Seleção (42 caracteres)" in text
    assert "Olá mundo" in text


def test_show_translation_card_shows_character_count_of_original(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    original = "x" * 250
    panel.show_translation_card("Página 3 inteira", original, "traduzido")
    text = panel._response_area.toPlainText()
    assert "250 caracteres" in text


def test_show_translation_card_escapes_html(qtbot):
    """Texto do modelo/usuário nunca deve virar HTML cru (injeção de markup)."""
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.show_translation_card("Seleção", "<b>x</b>", "<script>alert(1)</script>")
    text = panel._response_area.toPlainText()
    assert "<script>" not in panel._response_area.toHtml()  # não plain-text, HTML cru
    assert "alert(1)" in text  # o conteúdo textual aparece, só não como tag ativa


def test_show_translation_card_appends_without_clearing_previous_content(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel._response_area.setPlainText("resposta anterior do assistente")
    panel.show_translation_card("Seleção", "original", "traduzido")
    text = panel._response_area.toPlainText()
    assert "resposta anterior do assistente" in text
    assert "traduzido" in text


def test_show_translation_card_uses_theme_colors(qtbot):
    panel = RAGPanel()
    qtbot.addWidget(panel)
    panel.set_theme("light")
    colors_light = panel._translation_card_colors()
    panel.set_theme("dark")
    colors_dark = panel._translation_card_colors()
    assert colors_light != colors_dark
