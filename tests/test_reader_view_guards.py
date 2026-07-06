"""Guardas de regressão do ReaderView (checagens estáticas, sem importar Qt).

Não importa o módulo: o reader_view puxa QtWebEngineWidgets, que só pode ser
importado ANTES de existir um QApplication — em suíte cheia (qtbot já criou a
app) o import falharia. Lê o código-fonte direto do disco.
"""
import re
from pathlib import Path

_READER_VIEW = Path(__file__).resolve().parent.parent / "src" / "gui" / "reader_view.py"


def test_current_page_text_method_not_shadowed_by_attribute():
    """Regressão: um atributo self._current_page_text criado no __init__
    sombreava o MÉTODO homônimo e quebrava o menu de estudo com
    "TypeError: 'str' object is not callable" (reader_view._open_study_menu).
    """
    src = _READER_VIEW.read_text(encoding="utf-8")
    # Método deve existir…
    assert re.search(r"def _current_page_text\(self\)", src)
    # …e nenhum ATRIBUTO homônimo pode ser atribuído ([:=] pega "= x" e ": str = x";
    # [^=] exclui comparações "==").
    assert not re.search(r"self\._current_page_text\s*[:=][^=]", src), (
        "atributo self._current_page_text sombrearia o método homônimo "
        "(use outro nome, ex.: _last_page_text)"
    )
