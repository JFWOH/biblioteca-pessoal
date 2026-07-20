"""Cache de tradução no fluxo traduzir-e-narrar (débito 3.5, rodada B1).

MainWindow não instancia na suíte (pesada) — harness com o método REAL
(unbound ``MainWindow._translate_and_narrate``) sobre um self falso mínimo e
um ``LibraryDB`` real em tmp_path (valida também a persistência e a limpeza
por ``delete_book``). O TranslationService é substituído por um fake síncrono
via monkeypatch (sem QThread/singleton — nada para drenar).
"""
from types import SimpleNamespace

import pytest

from src.core.database import LibraryDB, page_translation_fingerprint
from src.gui.main_window import MainWindow

EN_TEXT = "The quick brown fox jumps over the lazy dog. It was a bright day."
PT_TEXT = "A rápida raposa marrom salta sobre o cão preguiçoso num dia claro."


class _FakeStatusbar:
    def __init__(self):
        self.messages = []

    def showMessage(self, msg, ms=0):
        self.messages.append(msg)

    def clearMessage(self):
        pass


class _FakeReaderView:
    def __init__(self, book_id, page=4):
        self._book_id = book_id
        self._reader = SimpleNamespace(current_page=page, total_pages=99)
        self.narration_epoch = 0
        self.narrated = []  # (text, chain_continuous, language)

    def narrate_text(self, text, chain_continuous=False, language=None):
        self.narrated.append((text, chain_continuous, language))


class _FakeTranslationService:
    """Fake síncrono: registra chamadas e resolve na hora via on_success."""

    calls = 0
    result = "TRADUZIDO"

    @classmethod
    def get_instance(cls):
        return cls()

    def translate_async(self, text, src_lang, tgt_lang, on_success, on_error):
        type(self).calls += 1
        on_success(type(self).result)


@pytest.fixture
def db(tmp_path):
    return LibraryDB(tmp_path / "lib.db")


@pytest.fixture
def harness(db, monkeypatch):
    from src.gui import translation_service
    monkeypatch.setattr(
        translation_service, "TranslationService", _FakeTranslationService)
    _FakeTranslationService.calls = 0
    _FakeTranslationService.result = "TRADUZIDO"
    book_id = db.add_book(title="Livro", file_path="/x.pdf", file_format="pdf")
    self = SimpleNamespace(
        _db=db,
        _statusbar=_FakeStatusbar(),
        _reader_view=_FakeReaderView(book_id),
        _page_translation_pending=False,
    )
    return self, book_id


def _run(self, text=EN_TEXT, enable_chaining=True):
    MainWindow._translate_and_narrate(self, text, enable_chaining)


def test_miss_traduz_grava_e_narra(harness, db):
    self, book_id = harness
    _run(self)
    assert _FakeTranslationService.calls == 1
    assert self._reader_view.narrated == [("TRADUZIDO", True, "pt")]
    fp = page_translation_fingerprint(EN_TEXT)
    assert db.get_cached_page_translation(book_id, 4, "en", "pt", fp) == "TRADUZIDO"


def test_hit_narra_sem_chamar_traducao(harness, db):
    self, book_id = harness
    fp = page_translation_fingerprint(EN_TEXT)
    db.set_page_translation_cache(book_id, 4, "en", "pt", fp, "DO CACHE")
    _run(self)
    assert _FakeTranslationService.calls == 0  # NLLB não é chamado
    assert self._reader_view.narrated == [("DO CACHE", True, "pt")]
    assert any("cache" in m for m in self._statusbar.messages)


def test_fonte_alterado_invalida_e_retraduz(harness, db):
    self, book_id = harness
    db.set_page_translation_cache(
        book_id, 4, "en", "pt", "fingerprint-antiga", "VELHO")
    _run(self)  # texto atual tem fingerprint diferente → miss
    assert _FakeTranslationService.calls == 1
    assert self._reader_view.narrated == [("TRADUZIDO", True, "pt")]


def test_pagina_ja_em_pt_nao_toca_o_cache(harness, db):
    self, book_id = harness
    _run(self, text=PT_TEXT)
    assert _FakeTranslationService.calls == 0
    # narra o ORIGINAL em pt, sem consultar nem gravar cache
    assert self._reader_view.narrated == [(PT_TEXT, True, "pt")]
    fp = page_translation_fingerprint(PT_TEXT)
    assert db.get_cached_page_translation(book_id, 4, "en", "pt", fp) is None


def test_chaining_false_propaga_nos_dois_caminhos(harness, db):
    self, book_id = harness
    _run(self, enable_chaining=False)          # miss
    _run(self, enable_chaining=False)          # hit (gravado no miss acima)
    assert [c for (_t, c, _l) in self._reader_view.narrated] == [False, False]
    assert _FakeTranslationService.calls == 1  # 2ª passada veio do cache


def test_epoca_avancada_descarta_narracao_mas_grava_cache(harness, db):
    self, book_id = harness

    class _EpochBumpingService(_FakeTranslationService):
        def translate_async(self, text, src_lang, tgt_lang, on_success, on_error):
            type(self).calls += 1
            self_outer.narration_epoch += 1  # outra narração começou no meio-tempo
            on_success("TARDIA")

    self_outer = self._reader_view
    from src.gui import translation_service
    translation_service.TranslationService = _EpochBumpingService
    _run(self)
    assert self._reader_view.narrated == []  # narração descartada
    fp = page_translation_fingerprint(EN_TEXT)
    # ...mas a tradução foi gravada: a próxima visita vira HIT
    assert db.get_cached_page_translation(book_id, 4, "en", "pt", fp) == "TARDIA"


def test_delete_book_limpa_o_cache(harness, db):
    self, book_id = harness
    _run(self)
    db.delete_book(book_id)
    fp = page_translation_fingerprint(EN_TEXT)
    assert db.get_cached_page_translation(book_id, 4, "en", "pt", fp) is None
