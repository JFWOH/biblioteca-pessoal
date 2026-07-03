"""Navegação da leitura contínua (item 5 do backlog UX).

Lógica pura (ADR-006): decide qual é a próxima página narrável quando a
narração de uma página termina no modo contínuo. Pula páginas sem texto
(capas, imagens, divisórias) até um limite, para não varrer o livro inteiro
atrás de texto.
"""


def find_next_readable_page(get_text, current: int, total: int,
                            max_skip: int = 10) -> int | None:
    """Próxima página (0-based, após ``current``) com texto narrável.

    Args:
        get_text: callable(page) -> str (texto da página; pode lançar).
        current: página atual 0-based.
        total: total de páginas do livro.
        max_skip: máximo de páginas vazias puladas em sequência.

    Returns:
        Índice da próxima página com texto, ou None (fim do livro /
        só páginas vazias adiante dentro do limite).
    """
    page = current + 1
    skipped = 0
    while page < total and skipped <= max_skip:
        try:
            text = (get_text(page) or "").strip()
        except Exception:
            text = ""
        if text:
            return page
        page += 1
        skipped += 1
    return None
