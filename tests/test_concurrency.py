import pytest
import threading
import time
from pathlib import Path

from src.core.database import LibraryDB


def test_database_concurrency(tmp_path: Path):
    """
    Testa o cenário P0 de colisão: inserções massivas por uma thread (simulando Indexador)
    e interações esporádicas de outra (simulando UI e anotações), garantindo que
    o banco não seja corrompido e não ocorra 'database disk image is malformed'
    devido a concorrência no SQLite.
    """
    db_path = tmp_path / "test_concurrency.db"
    
    # Prepara uma base comum que será compartilhada (o objeto LibraryDB pode ser passado)
    db = LibraryDB(db_path)
    
    # Cria um livro inicial
    book_id = db.add_book(title="Test Concurrency", file_path="test/path.pdf", file_format="pdf")
    
    exception_caught = None
    
    # 1. Thread que simula o Indexador (Background Worker)
    # Faz inserções constantes
    def background_indexer():
        nonlocal exception_caught
        try:
            # O Indexador recebe o mesmo objeto `db`, mas o `threading.local` dará
            # a ele sua própria conexão persistente, e as escritas sincronizarão via Lock.
            for i in range(100):
                db.save_ocr_page(book_id, i, f"OCR Text {i}")
                time.sleep(0.001)  # simula trabalho rápido
        except Exception as e:
            exception_caught = e
            
    # 2. Thread que simula a UI salvando uma anotação (Main Thread interaction)
    def ui_thread():
        nonlocal exception_caught
        try:
            for i in range(20):
                db.add_annotation(book_id, page_number=i, content=f"Anotação {i}")
                time.sleep(0.005) # simula demoras entre anotações
        except Exception as e:
            exception_caught = e

    t_bg = threading.Thread(target=background_indexer)
    t_ui = threading.Thread(target=ui_thread)
    
    t_bg.start()
    t_ui.start()
    
    t_bg.join()
    t_ui.join()
    
    assert exception_caught is None, f"Ocorreu exceção concorrente: {exception_caught}"
    
    # 3. Validações Pós-Concorrência
    # Verifica se os registros foram de fato criados
    ocr_pages = db.get_all_ocr_pages(book_id)
    annotations = db.get_annotations(book_id)
    
    assert len(ocr_pages) == 100
    assert len(annotations) == 20
    
    # 4. Verifica integridade do banco (O mais importante)
    # Acessamos a conexão bruta para rodar pragma integrity_check
    result = db.conn.execute("PRAGMA integrity_check;").fetchone()
    assert result[0].lower() == "ok", f"O banco de dados foi corrompido! Integrity: {result[0]}"

    db.close()
