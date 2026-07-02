"""Guardas de regressão do ReaderView (checagens estáticas, sem instanciar Qt).

Instanciar o ReaderView em teste exige QtWebEngine; estas guardas pegam a
classe de bug no nível do código-fonte.
"""
import inspect
import re


def test_current_page_text_method_not_shadowed_by_attribute():
    """Regressão: um atributo self._current_page_text criado no __init__
    sombreava o MÉTODO homônimo e quebrava o menu de estudo com
    "TypeError: 'str' object is not callable" (reader_view._open_study_menu).
    """
    from src.gui import reader_view

    src = inspect.getsource(reader_view)
    # Método deve existir…
    assert re.search(r"def _current_page_text\(self\)", src)
    # …e nenhum ATRIBUTO homônimo pode ser atribuído ([:=] pega "= x" e ": str = x";
    # [^=] exclui comparações "==").
    assert not re.search(r"self\._current_page_text\s*[:=][^=]", src), (
        "atributo self._current_page_text sombrearia o método homônimo "
        "(use outro nome, ex.: _last_page_text)"
    )
