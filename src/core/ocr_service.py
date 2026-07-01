"""Serviço local de OCR usando RapidOCR (onnxruntime) e PyMuPDF.

RapidOCR roda 100% via pip (sem binário de sistema), com modelos ONNX embarcados
no pacote — adequado para texto em alfabeto latino (PT/EN/ES). Roda em CPU.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(self, config_path: str | Path = "data/config.json"):
        self.config_path = Path(config_path)
        self._available: Optional[bool] = None
        self._engine = None  # RapidOCR (lazy)

    def _get_engine(self):
        """Constrói (uma vez) e retorna o motor RapidOCR, ou None se indisponível."""
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR()
            return self._engine
        except Exception as e:
            logger.warning("RapidOCR indisponível: %s", e)
            return None

    def is_available(self) -> bool:
        """Verifica se o motor de OCR (RapidOCR) pode ser carregado (sem binário externo)."""
        if self._available is not None:
            return self._available
        self._available = self._get_engine() is not None
        return self._available

    def is_scanned_pdf(self, filepath: str | Path, sample_pages: int = 3) -> bool:
        """Detecta heurística se um PDF é provável 'scanned' (muita imagem, pouco texto)."""
        import fitz
        try:
            doc = fitz.open(str(filepath))
        except Exception:
            return False
            
        total_pages = doc.page_count
        pages_to_check = min(total_pages, sample_pages)
        if pages_to_check == 0:
            doc.close()
            return False
            
        empty_text_pages = 0
        pages_with_images = 0
        
        for i in range(pages_to_check):
            page = doc[i]
            text = page.get_text().strip()
            if len(text) < 50:  # Pouquíssimo texto ou texto sujo
                empty_text_pages += 1
            
            image_list = page.get_images()
            if image_list:
                pages_with_images += 1
                
        doc.close()
        
        # Se a maioria das páginas testadas não tem texto mas tem imagens, é provável escaneado
        return empty_text_pages >= (pages_to_check / 2) and pages_with_images > 0

    def extract_text_from_page(self, filepath: str | Path, page_number: int) -> Optional[str]:
        """Extrai texto de uma página de PDF via OCR (rasterização + RapidOCR)."""
        if not self.is_available():
            return None

        engine = self._get_engine()
        if engine is None:
            return None

        import fitz

        try:
            doc = fitz.open(str(filepath))
            if page_number >= doc.page_count:
                doc.close()
                return None

            page = doc[page_number]
            # Zoom = 2 para ~144 DPI, bom equilíbrio para OCR de texto legível
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            png_bytes = pix.tobytes("png")
            doc.close()

            # RapidOCR aceita bytes PNG; result = lista de [box, texto, confiança]
            result, _ = engine(png_bytes)
            if not result:
                return ""
            text = "\n".join(line[1] for line in result)
            return text.strip()

        except Exception as e:
            logger.error("Erro durante OCR na página %d do PDF %s: %s", page_number, filepath, e)
            return None
