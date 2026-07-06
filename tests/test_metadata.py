"""Testes do módulo de metadados."""



from src.core.metadata import BookMetadata, extract_metadata


class TestBookMetadata:
    def test_default_values(self):
        meta = BookMetadata()
        assert meta.title == ""
        assert meta.author == ""
        assert meta.language == ""
        assert meta.page_count == 0
        assert meta.cover_data is None

    def test_to_dict(self):
        meta = BookMetadata(title="Test", author="Author")
        d = meta.to_dict()
        assert d["title"] == "Test"
        assert d["author"] == "Author"
        assert isinstance(d, dict)
        # cover_data é removido, e campos vazios são filtrados
        assert "cover_data" not in d
        assert "isbn" not in d  # vazio → filtrado


class TestExtractMetadata:
    def test_txt_metadata(self, tmp_path):
        txt = tmp_path / "hello.txt"
        txt.write_text("Conteúdo do arquivo de texto.", encoding="utf-8")
        meta = extract_metadata(txt)
        assert meta.title == "hello"  # nome do arquivo sem extensão
        # TXT usa extrator genérico que não conta páginas
        assert isinstance(meta.page_count, int)

    def test_md_metadata(self, tmp_path):
        md = tmp_path / "notes.md"
        md.write_text("# Título\n\nConteúdo markdown", encoding="utf-8")
        meta = extract_metadata(md)
        assert meta.title == "notes"

    def test_nonexistent_file(self, tmp_path):
        meta = extract_metadata(tmp_path / "nope.pdf")
        assert meta.title == "nope"  # fallback

    def test_unknown_format(self, tmp_path):
        f = tmp_path / "data.xyz"
        f.write_bytes(b"binary data")
        meta = extract_metadata(f)
        assert meta.title == "data"
