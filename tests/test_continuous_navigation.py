"""Testes da navegação da leitura contínua (item 5 do backlog UX)."""
from src.core.audio.continuous_navigation import find_next_readable_page


PAGES = {0: "Capítulo um.", 1: "", 2: "   ", 3: "Texto da página quatro.", 4: ""}


def _get(page: int) -> str:
    return PAGES.get(page, "")


def test_next_page_with_text():
    assert find_next_readable_page(_get, current=0, total=5) == 3  # pula 1 e 2


def test_none_at_end_of_book():
    assert find_next_readable_page(_get, current=3, total=5) is None  # só a 4 (vazia)


def test_none_when_current_is_last():
    assert find_next_readable_page(_get, current=4, total=5) is None


def test_max_skip_cap():
    empty = {p: "" for p in range(50)}
    empty[20] = "texto distante"
    assert find_next_readable_page(lambda p: empty[p], 0, 50, max_skip=10) is None
    assert find_next_readable_page(lambda p: empty[p], 0, 50, max_skip=30) == 20


def test_get_text_exception_treated_as_empty():
    def boom(page):
        if page == 1:
            raise RuntimeError("página corrompida")
        return "ok" if page == 2 else ""
    assert find_next_readable_page(boom, 0, 5) == 2
