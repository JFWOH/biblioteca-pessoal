"""Cache de tradução no fluxo traduzir-e-narrar (débito 3.5, rodada B1).

MainWindow não instancia na suíte (pesada) — harness com o método REAL
(unbound ``MainWindow._translate_and_narrate``) sobre um self falso mínimo e
um ``LibraryDB`` real em diretório temporário (valida também a persistência e
a limpeza por ``delete_book``). O TranslationService é substituído por um fake
síncrono (sem QThread/singleton — nada para drenar).

ESTE MÓDULO NÃO IMPORTA ``src.gui.main_window`` EM PROCESSO. Ele puxa
``QtWebEngineWidgets`` (via ReaderView) e o GC do QtWebEngine sem event loop
dá Segmentation fault no teardown do pytest no Linux — foi a causa das quedas
do shard ``test_[t-z]``. Os 7 cenários rodam num subprocesso fresco que importa
o módulo ANTES de criar o QApplication e devolve um JSON assertável (mesmo
padrão de ``test_reader_tts_fallback_visivel.py`` e
``test_ux_background_sem_dialogos.py``). ``test_modulo_nao_puxa_webengine``
trava a regressão.
"""
import ast
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

EN_TEXT = "The quick brown fox jumps over the lazy dog. It was a bright day."
PT_TEXT = "A rápida raposa marrom salta sobre o cão preguiçoso num dia claro."


def _rodar(driver: str, *args, timeout: int = 600):
    return subprocess.run(
        [sys.executable, "-c", driver, str(_ROOT), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONIOENCODING="utf-8"),
        timeout=timeout,
    )


# ── Guarda de higiene: este módulo não pode puxar QtWebEngine ──────────────

_GUARDA_DRIVER = textwrap.dedent(
    """
    import importlib.util, json, sys
    sys.path.insert(0, sys.argv[1])
    spec = importlib.util.spec_from_file_location("_mod_sob_guarda", sys.argv[2])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    suspeitos = sorted(m for m in sys.modules if "WebEngine" in m
                       or m in ("src.gui.main_window", "src.gui.reader_view"))
    print("@@JSON@@" + json.dumps(suspeitos))
    """
)


def test_modulo_nao_puxa_webengine():
    """Importar ESTE módulo não pode carregar QtWebEngine.

    Em subprocesso, e não com ``sys.modules`` em processo: outros módulos do
    mesmo shard podem ter carregado o WebEngine antes, e a asserção em processo
    mediria a ordem do shard em vez da higiene deste arquivo.
    """
    proc = _rodar(_GUARDA_DRIVER, str(Path(__file__).resolve()), timeout=300)
    assert "@@JSON@@" in (proc.stdout or ""), (
        f"guarda não rodou (rc={proc.returncode}):\n{proc.stderr[-1500:]}")
    carregados = json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())
    assert carregados == [], (
        "este módulo voltou a puxar QtWebEngine em processo "
        f"(segfault no teardown do pytest no Linux): {carregados}")


def test_fonte_deste_teste_nao_importa_main_window_no_topo():
    """Feedback rápido da mesma invariante, sem pagar um subprocesso."""
    arvore = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    modulos = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            modulos.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            modulos.add(no.module)
    proibidos = sorted(m for m in modulos if "QtWebEngine" in m or m in (
        "src.gui.main_window", "src.gui.reader_view"))
    assert proibidos == [], f"import pesado reintroduzido: {proibidos}"


# ── Cenários reais (subprocesso: import ANTES do QApplication) ─────────────

_DRIVER = textwrap.dedent(
    '''
    import json, sys, tempfile
    from pathlib import Path
    from types import SimpleNamespace
    sys.path.insert(0, sys.argv[1])

    EN_TEXT = sys.argv[2]
    PT_TEXT = sys.argv[3]

    # ANTES do QApplication (main_window -> reader_view -> QtWebEngineWidgets).
    from src.gui.main_window import MainWindow
    from src.core.database import LibraryDB, page_translation_fingerprint
    from src.gui import translation_service

    out = {}

    class _FakeStatusbar:
        def __init__(self): self.messages = []
        def showMessage(self, msg, ms=0): self.messages.append(msg)
        def clearMessage(self): pass

    class _FakeReaderView:
        def __init__(self, book_id, page=4):
            self._book_id = book_id
            self._reader = SimpleNamespace(current_page=page, total_pages=99)
            self.narration_epoch = 0
            self.narrated = []          # (text, chain_continuous, language)
        def narrate_text(self, text, chain_continuous=False, language=None):
            self.narrated.append([text, chain_continuous, language])

    class _FakeTranslationService:
        """Fake síncrono: registra chamadas e resolve na hora via on_success."""
        calls = 0
        result = "TRADUZIDO"
        @classmethod
        def get_instance(cls): return cls()
        def translate_async(self, text, src_lang, tgt_lang, on_success, on_error):
            type(self).calls += 1
            on_success(type(self).result)

    def harness():
        """DB real novo + self falso mínimo, com o fake de tradução religado."""
        translation_service.TranslationService = _FakeTranslationService
        _FakeTranslationService.calls = 0
        _FakeTranslationService.result = "TRADUZIDO"
        db = LibraryDB(Path(tempfile.mkdtemp()) / "lib.db")
        book_id = db.add_book(title="Livro", file_path="/x.pdf", file_format="pdf")
        eu = SimpleNamespace(
            _db=db,
            _statusbar=_FakeStatusbar(),
            _reader_view=_FakeReaderView(book_id),
            _page_translation_pending=False,
        )
        return eu, db, book_id

    def run(eu, text=None, enable_chaining=True):
        MainWindow._translate_and_narrate(eu, text or EN_TEXT, enable_chaining)

    def cache(db, book_id, texto):
        return db.get_cached_page_translation(
            book_id, 4, "en", "pt", page_translation_fingerprint(texto))

    # 1) miss: traduz, grava e narra
    eu, db, bid = harness()
    run(eu)
    out["miss"] = {"calls": _FakeTranslationService.calls,
                   "narrated": list(eu._reader_view.narrated),
                   "cache": cache(db, bid, EN_TEXT)}

    # 2) hit: narra sem chamar a tradução
    eu, db, bid = harness()
    db.set_page_translation_cache(
        bid, 4, "en", "pt", page_translation_fingerprint(EN_TEXT), "DO CACHE")
    run(eu)
    out["hit"] = {"calls": _FakeTranslationService.calls,
                  "narrated": list(eu._reader_view.narrated),
                  "mensagens": list(eu._statusbar.messages)}

    # 3) fonte alterado (fingerprint diferente) invalida e retraduz
    eu, db, bid = harness()
    db.set_page_translation_cache(bid, 4, "en", "pt", "fingerprint-antiga", "VELHO")
    run(eu)
    out["fingerprint_velha"] = {"calls": _FakeTranslationService.calls,
                                "narrated": list(eu._reader_view.narrated)}

    # 4) página já em pt: não consulta nem grava cache
    eu, db, bid = harness()
    run(eu, text=PT_TEXT)
    out["ja_em_pt"] = {"calls": _FakeTranslationService.calls,
                       "narrated": list(eu._reader_view.narrated),
                       "cache": cache(db, bid, PT_TEXT)}

    # 5) chaining=False propaga nos DOIS caminhos (miss e hit)
    eu, db, bid = harness()
    run(eu, enable_chaining=False)      # miss
    run(eu, enable_chaining=False)      # hit (gravado no miss acima)
    out["chaining_false"] = {
        "calls": _FakeTranslationService.calls,
        "chains": [c for (_t, c, _l) in eu._reader_view.narrated],
    }

    # 6) época avançada no meio-tempo: descarta a narração, MAS grava o cache
    eu, db, bid = harness()
    leitor = eu._reader_view
    class _EpochBumpingService(_FakeTranslationService):
        def translate_async(self, text, src_lang, tgt_lang, on_success, on_error):
            type(self).calls += 1
            leitor.narration_epoch += 1   # outra narração começou no meio-tempo
            on_success("TARDIA")
    translation_service.TranslationService = _EpochBumpingService
    run(eu)
    out["epoca_avancada"] = {"narrated": list(eu._reader_view.narrated),
                             "cache": cache(db, bid, EN_TEXT)}

    # 7) delete_book limpa o cache
    eu, db, bid = harness()
    run(eu)
    db.delete_book(bid)
    out["apos_delete"] = {"cache": cache(db, bid, EN_TEXT)}

    print("@@JSON@@" + json.dumps(out, ensure_ascii=True))
    '''
)


@pytest.fixture(scope="module")
def r():
    """Roda o driver UMA vez e devolve o JSON com todos os cenários."""
    proc = _rodar(_DRIVER, EN_TEXT, PT_TEXT)
    if "@@JSON@@" not in (proc.stdout or ""):
        pytest.skip(
            f"driver do _translate_and_narrate não rodou (rc={proc.returncode}): "
            f"{proc.stderr[-800:]}")
    return json.loads(proc.stdout.split("@@JSON@@", 1)[1].strip())


def test_miss_traduz_grava_e_narra(r):
    caso = r["miss"]
    assert caso["calls"] == 1
    assert caso["narrated"] == [["TRADUZIDO", True, "pt"]]
    assert caso["cache"] == "TRADUZIDO"


def test_hit_narra_sem_chamar_traducao(r):
    caso = r["hit"]
    assert caso["calls"] == 0            # NLLB não é chamado
    assert caso["narrated"] == [["DO CACHE", True, "pt"]]
    assert any("cache" in m for m in caso["mensagens"])


def test_fonte_alterado_invalida_e_retraduz(r):
    caso = r["fingerprint_velha"]
    assert caso["calls"] == 1
    assert caso["narrated"] == [["TRADUZIDO", True, "pt"]]


def test_pagina_ja_em_pt_nao_toca_o_cache(r):
    caso = r["ja_em_pt"]
    assert caso["calls"] == 0
    # narra o ORIGINAL em pt, sem consultar nem gravar cache
    assert caso["narrated"] == [[PT_TEXT, True, "pt"]]
    assert caso["cache"] is None


def test_chaining_false_propaga_nos_dois_caminhos(r):
    caso = r["chaining_false"]
    assert caso["chains"] == [False, False]
    assert caso["calls"] == 1            # 2ª passada veio do cache


def test_epoca_avancada_descarta_narracao_mas_grava_cache(r):
    caso = r["epoca_avancada"]
    assert caso["narrated"] == []        # narração descartada
    # ...mas a tradução foi gravada: a próxima visita vira HIT
    assert caso["cache"] == "TARDIA"


def test_delete_book_limpa_o_cache(r):
    assert r["apos_delete"]["cache"] is None
