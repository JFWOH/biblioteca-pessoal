import pytest
from pathlib import Path
import fitz
from src.core.ocr_service import OCRService

@pytest.fixture
def test_pdf_dir(tmp_path) -> Path:
    d = tmp_path / "pdfs"
    d.mkdir()
    return d

def create_digital_pdf(filepath: Path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Este é um PDF puramente digital com texto legível nativamente. " * 10)
    doc.save(str(filepath))
    doc.close()

def create_scanned_pdf(filepath: Path):
    from PIL import Image
    import io
    
    # Cria uma imagem branca com um texto ruidoso desenhado
    img = Image.new('RGB', (400, 400), color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    doc = fitz.open()
    page = doc.new_page()
    rect = fitz.Rect(0, 0, 400, 400)
    page.insert_image(rect, stream=img_bytes)
    # Zero texto inserido
    doc.save(str(filepath))
    doc.close()

def test_detect_digital_pdf(test_pdf_dir):
    service = OCRService()
    p = test_pdf_dir / "digital.pdf"
    create_digital_pdf(p)
    assert service.is_scanned_pdf(p) is False

def test_detect_scanned_pdf(test_pdf_dir):
    service = OCRService()
    p = test_pdf_dir / "scanned.pdf"
    create_scanned_pdf(p)
    assert service.is_scanned_pdf(p) is True

def test_ocr_unavailable_graceful_fail():
    service = OCRService()
    # Força indisponibilidade do motor OCR
    service._available = False

    text = service.extract_text_from_page("fake.pdf", 0)
    assert text is None


def test_ocr_extracts_from_image_pdf(test_pdf_dir):
    """Integração: o pipeline RapidOCR roda de ponta a ponta sobre uma página-imagem.

    (Regressão: antes o OCR dependia do binário Tesseract; agora é RapidOCR via pip.)
    """
    from PIL import Image, ImageDraw, ImageFont
    import io

    img = Image.new("RGB", (700, 220), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 64)
    except Exception:
        font = ImageFont.load_default()
    draw.text((25, 70), "BIBLIOTECA", fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=700, height=220)
    page.insert_image(fitz.Rect(0, 0, 700, 220), stream=buf.getvalue())
    p = test_pdf_dir / "img_text.pdf"
    doc.save(str(p))
    doc.close()

    service = OCRService()
    if not service.is_available():
        pytest.skip("RapidOCR indisponível neste ambiente")

    text = service.extract_text_from_page(p, 0)
    # O pipeline deve executar sem erro e retornar uma string (não None)
    assert text is not None
    assert isinstance(text, str)
