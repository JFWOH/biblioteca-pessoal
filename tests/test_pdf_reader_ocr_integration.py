import pytest
from unittest.mock import patch, MagicMock

from src.core.rag_engine import RAGEngine
from src.core.database import LibraryDB

@pytest.fixture
def mock_db_with_scanned_pdf(tmp_path):
    db_path = tmp_path / "test_library.db"
    db = LibraryDB(db_path)
    
    # Adiciona um livro fake que simula um PDF escaneado
    book_id = db.add_book(
        title="Documento Escaneado",
        file_path=str(tmp_path / "fake_scanned.pdf"),
        file_format="pdf",
        description="Teste de OCR"
    )
    
    yield db_path, book_id
    db.conn.close()

def test_extract_book_text_with_ocr_fallback(mock_db_with_scanned_pdf):
    db_path, book_id = mock_db_with_scanned_pdf
    
    # Instancia o RAGEngine
    engine = RAGEngine(db_path=db_path)
    
    # Mock do Reader para simular que o get_page_text retorna vazio (escaneado)
    mock_reader = MagicMock()
    mock_reader.total_pages = 2
    mock_reader.get_page_text.return_value = ""  # Sem texto nativo
    
    # Mock do OCRService
    mock_ocr_service = MagicMock()
    mock_ocr_service.is_scanned_pdf.return_value = True
    mock_ocr_service.is_available.return_value = True
    
    # Para a página 0 e 1, o OCR encontra texto
    def mock_extract(p, i):
        return f"Texto detectado via OCR na página {i}"
        
    mock_ocr_service.extract_text_from_page.side_effect = mock_extract

    # Precisamos mockar create_reader e OCRService dentro do _extract_book_text
    with patch("src.readers.reader_factory.create_reader", return_value=mock_reader), \
         patch("src.core.ocr_service.OCRService", return_value=mock_ocr_service), \
         patch("pathlib.Path.exists", return_value=True):
         
        from src.core.document_indexer_service import DocumentIndexerService
        db = LibraryDB(db_path)
        indexer = DocumentIndexerService(db, engine)
        book_meta, chunks = indexer._extract_book_text(book_id)
        
        # Verifica se os chunks foram gerados a partir do OCR
        # 1 chunk pro metadata (título + descrição)
        # 2 chunks pro conteúdo OCR (um por página)
        
        assert len(chunks) == 3
        
        ocr_chunk_0 = [c for c in chunks if c["page_number"] == 0 and c["chunk_type"] == "content"][0]
        ocr_chunk_1 = [c for c in chunks if c["page_number"] == 1 and c["chunk_type"] == "content"][0]
        
        assert ocr_chunk_0["text"] == "Texto detectado via OCR na página 0"
        assert ocr_chunk_1["text"] == "Texto detectado via OCR na página 1"
        
        # Verifica se foi persistido no banco
        db = LibraryDB(db_path)
        ocr_page_0 = db.get_ocr_page(book_id, 0)
        ocr_page_1 = db.get_ocr_page(book_id, 1)
        
        assert ocr_page_0["content"] == "Texto detectado via OCR na página 0"
        assert ocr_page_1["content"] == "Texto detectado via OCR na página 1"
        
        db.conn.close()

def test_extract_book_text_ocr_cache_hit(mock_db_with_scanned_pdf):
    db_path, book_id = mock_db_with_scanned_pdf
    
    # Insere cache antecipado no banco
    db = LibraryDB(db_path)
    db.save_ocr_page(book_id, 0, "Texto OCR no Cache")
    db.conn.close()
    
    engine = RAGEngine(db_path=db_path)
    
    mock_reader = MagicMock()
    mock_reader.total_pages = 1
    mock_reader.get_page_text.return_value = ""  # Sem texto nativo
    
    mock_ocr_service = MagicMock()
    mock_ocr_service.is_scanned_pdf.return_value = True
    mock_ocr_service.is_available.return_value = True
    
    with patch("src.readers.reader_factory.create_reader", return_value=mock_reader), \
         patch("src.core.ocr_service.OCRService", return_value=mock_ocr_service), \
         patch("pathlib.Path.exists", return_value=True):
         
        from src.core.document_indexer_service import DocumentIndexerService
        db_indexer = LibraryDB(db_path)
        indexer = DocumentIndexerService(db_indexer, engine)
        book_meta, chunks = indexer._extract_book_text(book_id)
        
        # Como estava em cache, extract_text_from_page nunca deve ser chamado
        mock_ocr_service.extract_text_from_page.assert_not_called()
        
        ocr_chunk_0 = [c for c in chunks if c["page_number"] == 0 and c["chunk_type"] == "content"][0]
        assert ocr_chunk_0["text"] == "Texto OCR no Cache"
