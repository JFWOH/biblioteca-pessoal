"""Serviço local de OCR utilizando PyTesseract e PyMuPDF."""

import logging
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class OCRService:
    def __init__(self, config_path: str | Path = "data/config.json"):
        self.config_path = Path(config_path)
        self._tesseract_available = None
        self._supported_langs = self._load_ocr_language()
        
    def _load_ocr_language(self) -> str:
        """Carrega o idioma de OCR do config.json, com fallback para 'por+eng'."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return config.get("ocr_language", "por+eng")
        except Exception as e:
            logger.warning("Falha ao ler config.json para OCR: %s", e)
        return "por+eng"
        
    def is_available(self) -> bool:
        """Verifica se o tesseract está instalado e disponível no PATH."""
        if self._tesseract_available is not None:
            return self._tesseract_available
            
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except (ImportError, Exception) as e:
            logger.warning("Tesseract OCR não disponível ou não encontrado no PATH: %s", e)
            self._tesseract_available = False
            
        return self._tesseract_available

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
        """Extrai texto de uma página de PDF usando OCR via rasterização (pixmap)."""
        if not self.is_available():
            return None
            
        import fitz
        import pytesseract
        from PIL import Image
        
        try:
            doc = fitz.open(str(filepath))
            if page_number >= doc.page_count:
                return None
                
            page = doc[page_number]
            # Zoom = 2 para 144 DPI, bom equilíbrio para OCR de texto legível
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Converte Pixmap para objeto PIL Image
            if pix.n - pix.alpha < 4:      # RGB ou Grayscale
                mode = "RGB" if pix.n == 3 else "L"
            else:
                mode = "CMYK"
            
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            
            # Tenta com as linguagens do config
            try:
                text = pytesseract.image_to_string(img, lang=self._supported_langs)
            except pytesseract.TesseractError as e:
                # Fallback para 'por' caso 'por+eng' falhe por falta de pack
                if "por+eng" in self._supported_langs and "Failed loading language" in str(e):
                    logger.warning("Idioma OCR '%s' indisponível, tentando fallback para 'por'.", self._supported_langs)
                    text = pytesseract.image_to_string(img, lang="por")
                else:
                    raise e
                    
            doc.close()
            return text.strip()
            
        except Exception as e:
            logger.error("Erro durante OCR na página %d do PDF %s: %s", page_number, filepath, e)
            return None
