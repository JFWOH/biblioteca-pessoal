"""Degradação graciosa com arquivos de livro danificados/incompletos (ADR-005).

Contrato (Onda S, rodada ago/2026): ``open()`` de um reader NUNCA deixa vazar
exceção crua da biblioteca de parsing — ou abre, ou levanta ``BookOpenError``
com mensagem PT-BR pronta para a GUI. Os arquivos ruins são gerados aqui
mesmo (tmp_path), a partir de originais minúsculos válidos — nada binário
commitado no repo.
"""
import zipfile

import pytest

from src.readers.base_reader import BookOpenError
from src.readers.epub_reader import EPUBReader
from src.readers.pdf_reader import PDFReader


# ── Geradores de arquivos ─────────────────────────────────────────────────

def _pdf_valido(tmp_path):
    import fitz

    path = tmp_path / "ok.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "página de teste")
    doc.save(str(path))
    doc.close()
    return path


def _epub_valido(tmp_path):
    from ebooklib import epub

    path = tmp_path / "ok.epub"
    book = epub.EpubBook()
    book.set_identifier("robustez-teste")
    book.set_title("Livro de Teste")
    book.set_language("pt")
    cap = epub.EpubHtml(title="Capítulo 1", file_name="cap1.xhtml", lang="pt")
    cap.content = "<html><body><h1>Capítulo 1</h1><p>Texto.</p></body></html>"
    book.add_item(cap)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", cap]
    epub.write_epub(str(path), book)
    return path


def _truncado(path, fracao=0.5):
    """Corta o arquivo no meio — simula download/cópia interrompida."""
    data = path.read_bytes()
    quebrado = path.with_name(f"truncado_{path.name}")
    quebrado.write_bytes(data[: max(16, int(len(data) * fracao))])
    return quebrado


# ── Contrato: falha CLARA, nunca exceção crua ─────────────────────────────

def _open_e_gracioso(reader) -> bool:
    """True se abriu; False se falhou do jeito combinado (BookOpenError PT-BR)."""
    try:
        reader.open()
    except BookOpenError as exc:
        assert "danificado ou ilegível" in str(exc)
        assert reader._filepath.name in str(exc)
        return False
    return True


def test_pdf_truncado_abre_ou_falha_claro(tmp_path):
    """O MuPDF tem modo de REPARO: PDF truncado pode abrir mesmo assim.

    Os dois desfechos são degradação graciosa válida — o proibido é exceção
    crua. Quando abre, tem de se comportar como documento de verdade.
    """
    quebrado = _truncado(_pdf_valido(tmp_path))
    reader = PDFReader(quebrado)
    if _open_e_gracioso(reader):
        assert reader.total_pages >= 0
        reader.close()


def test_pdf_com_conteudo_de_texto_falha_claro(tmp_path):
    falso = tmp_path / "falso.pdf"
    falso.write_text("isto não é um PDF, é um txt de chapéu", encoding="utf-8")
    with pytest.raises(BookOpenError):
        PDFReader(falso).open()


def test_pdf_vazio_falha_claro(tmp_path):
    vazio = tmp_path / "vazio.pdf"
    vazio.write_bytes(b"")
    with pytest.raises(BookOpenError):
        PDFReader(vazio).open()


def test_epub_truncado_falha_claro(tmp_path):
    quebrado = _truncado(_epub_valido(tmp_path))
    with pytest.raises(BookOpenError, match="danificado ou ilegível"):
        EPUBReader(quebrado).open()


def test_epub_vazio_falha_claro(tmp_path):
    vazio = tmp_path / "vazio.epub"
    vazio.write_bytes(b"")
    with pytest.raises(BookOpenError):
        EPUBReader(vazio).open()


def test_epub_sem_mimetype_abre_ou_falha_claro(tmp_path):
    """ebooklib é leniente com mimetype ausente — os DOIS desfechos valem.

    O contrato não exige rejeitar (o arquivo pode ser legível); exige apenas
    que o desfecho seja controlado: abrir de verdade OU BookOpenError.
    """
    original = _epub_valido(tmp_path)
    sem_mime = tmp_path / "sem_mimetype.epub"
    with zipfile.ZipFile(original) as zin, zipfile.ZipFile(sem_mime, "w") as zout:
        for info in zin.infolist():
            if info.filename == "mimetype":
                continue
            zout.writestr(info, zin.read(info.filename))
    reader = EPUBReader(sem_mime)
    if _open_e_gracioso(reader):
        assert reader.total_pages >= 1


def test_arquivos_validos_continuam_abrindo(tmp_path):
    """Controle: a blindagem não pode ter quebrado o caminho feliz."""
    pdf = PDFReader(_pdf_valido(tmp_path))
    assert _open_e_gracioso(pdf)
    assert pdf.total_pages == 1
    pdf.close()

    epub_reader = EPUBReader(_epub_valido(tmp_path))
    assert _open_e_gracioso(epub_reader)
    assert epub_reader.total_pages >= 1
    epub_reader.close()
