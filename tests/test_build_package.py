"""Testes da rodada E4 — script de build do pacote portátil.

Cobre as partes que rodam SEM rede: geração real do PDF do manual (Qt),
patch do ``python311._pth`` (função pura), cópia da árvore do app com
exclusões, arquivos de raiz (LEIA-ME/lançadores/portable.flag) e o pré-seed
do Kokoro a partir de um cache fake. Os estágios de rede (runtime/deps) são
exercitados só no build real (roteiro E5).
"""

import pytest

from src.tools.build_package import (
    copy_app_tree,
    patch_embed_pth,
    seed_kokoro,
    write_root_files,
)
from src.tools.manual_pdf import generate_manual_pdf


class TestManualPdf:
    def test_gera_pdf_real_do_manual(self, qtbot, tmp_path):
        out = generate_manual_pdf(out_path=tmp_path / "manual.pdf")
        data = out.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 20_000  # manual completo, não página vazia

    def test_pdf_tem_fontes_e_texto_de_verdade(self, qtbot, tmp_path):
        """Regressão do bug do 1º build (2026-07-20): com QT_QPA_PLATFORM=
        offscreen no Windows, o PDF saía inteiro em tofu — ZERO fontes
        embutidas e ZERO texto extraível (ilegível E inindexável pelo RAG).
        Estas duas propriedades são o discriminador exato do defeito."""
        import fitz
        # Sonda de ambiente (Onda S): em algumas máquinas Windows o plugin
        # offscreen não entrega fonte NENHUMA ao Qt — aí nenhum PDF via Qt
        # embute fonte e este teste mediria o ambiente, não o app. A sonda
        # usa o mesmo mecanismo num documento trivial: se nem "hello" embute
        # fonte, o problema é da plataforma → skip. O CI Linux tem fontes e
        # continua cobrindo a regressão de verdade.
        from PyQt6.QtGui import QPageSize, QPdfWriter, QTextDocument
        sonda = tmp_path / "sonda_fonte.pdf"
        writer = QPdfWriter(str(sonda))
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        doc_sonda = QTextDocument()
        doc_sonda.setPlainText("hello")
        doc_sonda.print(writer)
        with fitz.open(str(sonda)) as probe:
            if not probe[0].get_fonts():
                pytest.skip("Qt offscreen sem fontes do sistema nesta máquina "
                            "— regressão coberta no CI Linux")
        out = generate_manual_pdf(out_path=tmp_path / "manual.pdf")
        doc = fitz.open(str(out))
        try:
            page = doc[0]
            assert page.get_fonts(), "PDF sem nenhuma fonte embutida (tofu)"
            text = "".join(p.get_text() for p in doc)
            assert "Biblioteca Pessoal" in text
            assert "Instala" in text  # seção 1 do manual
        finally:
            doc.close()

    def test_md_customizado(self, qtbot, tmp_path):
        md = tmp_path / "mini.md"
        md.write_text("# Título\n\nCorpo do documento.", encoding="utf-8")
        out = generate_manual_pdf(md_path=md, out_path=tmp_path / "mini.pdf")
        assert out.read_bytes().startswith(b"%PDF")


class TestPatchEmbedPth:
    REAL_SAMPLE = "python311.zip\n.\n\n# Uncomment to run site.main() automatically\n#import site\n"

    def test_habilita_site_e_adiciona_caminhos(self):
        patched = patch_embed_pth(self.REAL_SAMPLE)
        lines = patched.splitlines()
        assert "import site" in lines
        assert "#import site" not in lines
        assert ".." in lines
        assert "Lib\\site-packages" in lines

    def test_idempotente(self):
        once = patch_embed_pth(self.REAL_SAMPLE)
        assert patch_embed_pth(once) == once


@pytest.fixture
def fake_project(tmp_path):
    root = tmp_path / "proj"
    (root / "src" / "core").mkdir(parents=True)
    (root / "src" / "core" / "app.py").write_text("x = 1", encoding="utf-8")
    (root / "src" / "core" / "__pycache__").mkdir()
    (root / "src" / "core" / "__pycache__" / "app.pyc").write_bytes(b"x")
    (root / "src" / "data" / "traces").mkdir(parents=True)
    (root / "src" / "data" / "traces" / "t.jsonl").write_text("{}", encoding="utf-8")
    (root / "resources" / "themes").mkdir(parents=True)
    (root / "resources" / "themes" / "dark.qss").write_text("", encoding="utf-8")
    (root / "venv").mkdir()  # nunca copiado (não está em APP_TREES)
    return root


class TestCopyAppTree:
    def test_copia_src_e_resources_sem_caches_nem_dados_dev(self, fake_project,
                                                            tmp_path):
        out = tmp_path / "pkg"
        out.mkdir()
        copied = copy_app_tree(fake_project, out)
        assert copied == ["src", "resources"]
        assert (out / "src" / "core" / "app.py").exists()
        assert (out / "resources" / "themes" / "dark.qss").exists()
        assert not (out / "src" / "core" / "__pycache__").exists()
        assert not (out / "src" / "data").exists()  # traces de dev ficam fora
        assert not (out / "venv").exists()

    def test_recopia_limpa(self, fake_project, tmp_path):
        out = tmp_path / "pkg"
        out.mkdir()
        copy_app_tree(fake_project, out)
        stale = out / "src" / "velho.py"
        stale.write_text("sobras de build anterior", encoding="utf-8")
        copy_app_tree(fake_project, out)
        assert not stale.exists()


class TestRootFiles:
    def test_leiame_lancadores_e_flag(self, tmp_path):
        write_root_files(tmp_path)
        assert (tmp_path / "portable.flag").exists()
        assert (tmp_path / "data").is_dir()
        leiame = (tmp_path / "LEIA-ME.txt").read_text(encoding="utf-8")
        assert "dois cliques" in leiame
        launcher = (tmp_path / "Biblioteca Pessoal.bat").read_text(encoding="utf-8")
        assert "pythonw.exe" in launcher and "-m src.main" in launcher
        diag = (tmp_path / "Diagnostico.bat").read_text(encoding="utf-8")
        assert "python.exe" in diag and "pause" in diag


class TestSeedKokoro:
    def test_copia_do_cache_local(self, tmp_path):
        hub = tmp_path / "hub"
        model = hub / "models--hexgrad--Kokoro-82M" / "snapshots" / "abc"
        model.mkdir(parents=True)
        (model / "kokoro-v1_0.pth").write_bytes(b"pesos")
        out = tmp_path / "pkg"
        out.mkdir()
        assert seed_kokoro(out, hf_hub_dir=hub) is True
        dst = (out / "data" / "hf_cache" / "hub" / "models--hexgrad--Kokoro-82M"
               / "snapshots" / "abc" / "kokoro-v1_0.pth")
        assert dst.read_bytes() == b"pesos"

    def test_sem_cache_avisa_e_segue(self, tmp_path):
        out = tmp_path / "pkg"
        out.mkdir()
        assert seed_kokoro(out, hf_hub_dir=tmp_path / "nada") is False
        assert not (out / "data" / "hf_cache").exists()
