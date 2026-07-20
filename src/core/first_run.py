"""Primeira execução do pacote portátil (rodada E2 do plano de empacotamento).

Lógica pura, sem Qt (ADR-006): importar o manual do usuário como primeiro
livro da biblioteca — a estante nunca abre vazia e o auto-index o torna
consultável pela IA ("como importo livros?" responde com página do manual).
O PDF é gerado pelo build (rodada E4) na raiz do pacote; no ambiente de
desenvolvimento ele normalmente não existe e nada acontece.
"""

import logging
from pathlib import Path

from src.utils.constants import PROJECT_ROOT

logger = logging.getLogger(__name__)

MANUAL_FILENAME = "Manual - Biblioteca Pessoal.pdf"
_FLAG_KEY = "app.manual_imported"


def manual_pdf_path() -> Path | None:
    """Caminho do PDF do manual (raiz do pacote ou docs/), ou None se ausente."""
    for candidate in (PROJECT_ROOT / MANUAL_FILENAME,
                      PROJECT_ROOT / "docs" / MANUAL_FILENAME):
        if candidate.exists():
            return candidate
    return None


def import_manual_if_first_run(library, config, manual_path=None) -> bool:
    """Importa o manual como livro na 1ª execução. True se importou AGORA.

    O flag ``app.manual_imported`` só é gravado após importar com sucesso.
    Uma vez importado, nunca reimporta — se o usuário remover o livro depois,
    a escolha é respeitada (o PDF continua na pasta do app). Falhas são
    logadas e não derrubam o startup (ADR-005).
    """
    if config.get(_FLAG_KEY, False):
        return False
    path = Path(manual_path) if manual_path is not None else manual_pdf_path()
    if path is None or not path.exists():
        return False
    try:
        book, _is_new = library.import_file(str(path))
    except Exception:
        logger.exception("Falha ao importar o manual do usuário (seguindo sem ele)")
        return False
    if book is None:
        return False
    config.set(_FLAG_KEY, True)  # set() já persiste no disco
    return True
