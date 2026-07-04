"""Testes da qualidade da tradução: limpeza de PDF + revisão pelo agente."""
import io
import json

from src.core.translation_backends.text_cleanup import clean_source_text
from src.core.translation_backends import translation_reviser
from src.core.translation_backends.translation_reviser import revise_translation


# ── clean_source_text ─────────────────────────────────────────────────

def test_clean_joins_spaced_caps_heading():
    """'C H A P T E R 1' (título com letras espaçadas) vira palavra única."""
    assert clean_source_text("C H A P T E R 1 Introduction") == "CHAPTER 1 Introduction"


def test_clean_joins_drop_cap_at_start():
    """Capitular 'W ELCOME' no início do texto (caso real do bug relatado)."""
    text = "W ELCOME to the world of Python! You might have heard."
    assert clean_source_text(text).startswith("WELCOME to the world")


def test_clean_does_not_join_mid_text_single_letters():
    """'I HAVE' no meio do texto NÃO pode virar 'IHAVE' (capitular é só no início)."""
    text = "He said that I HAVE to go now."
    assert "I HAVE" in clean_source_text(text)


def test_clean_fixes_hyphenated_line_breaks():
    assert clean_source_text("artificial intelli-\ngence is here") == \
        "artificial intelligence is here"


def test_clean_collapses_repeated_spaces_keeps_newlines():
    out = clean_source_text("too   many    spaces\nsecond line")
    assert "too many spaces" in out
    assert "\n" in out


def test_clean_empty():
    assert clean_source_text("") == ""
    assert clean_source_text(None or "") == ""


def test_clean_plain_text_unchanged():
    text = "Python is a high-level language. It was created by Guido van Rossum."
    assert clean_source_text(text) == text


# ── revise_translation (Ollama mockado) ───────────────────────────────

class _FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(content: str):
    body = json.dumps({"message": {"content": content}}).encode()
    return lambda req, timeout=0: _FakeResp(body)


def test_revise_success(monkeypatch):
    revised_text = "Bem-vindo ao mundo do Python! Você pode já ter ouvido falar."
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(revised_text))
    out = revise_translation("Welcome to the world of Python!",
                             "Wcome ao mundo do Python voce pode ter ouvido",
                             model="fake:1b")
    assert out == revised_text


def test_revise_too_short_response_returns_none(monkeypatch):
    """Resposta suspeita de truncamento → None (chamador mantém o rascunho)."""
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen("ok"))
    draft = "uma tradução relativamente longa que não pode ser substituída por nada curto"
    assert revise_translation("some long original text here", draft, model="fake:1b") is None


def test_revise_network_failure_returns_none(monkeypatch):
    def _boom(req, timeout=0):
        raise OSError("ollama fora")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert revise_translation("original", "rascunho da tradução", model="fake:1b") is None


def test_revise_no_model_available_returns_none(monkeypatch):
    monkeypatch.setattr(translation_reviser, "revise_translation".__class__.__name__, None,
                        raising=False)  # no-op; resolução real mockada abaixo
    monkeypatch.setattr("src.core.graph.concept_extractor.resolve_llm_model",
                        lambda url: None)
    assert revise_translation("original", "rascunho", model=None) is None


def test_revise_empty_inputs_return_none():
    assert revise_translation("", "rascunho", model="fake:1b") is None
    assert revise_translation("original", "", model="fake:1b") is None


# ── TranslationWorker aplica a revisão (sem modelo real) ──────────────

class _FakeBackend:
    def translate(self, text, src, tgt):
        return "rascunho do nllb com falhas mas razoavelmente longo"


def test_worker_uses_revised_translation(qtbot, monkeypatch):
    from src.gui.translation_service import TranslationWorker

    monkeypatch.setattr(
        "src.core.translation_backends.translation_reviser.revise_translation",
        lambda original, draft, **kw: "tradução revisada pelo agente principal")
    worker = TranslationWorker(_FakeBackend(), "original text", "en", "pt", revise=True)
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert results == ["tradução revisada pelo agente principal"]


def test_worker_falls_back_to_draft_when_revision_unavailable(qtbot, monkeypatch):
    from src.gui.translation_service import TranslationWorker

    monkeypatch.setattr(
        "src.core.translation_backends.translation_reviser.revise_translation",
        lambda original, draft, **kw: None)
    worker = TranslationWorker(_FakeBackend(), "original text", "en", "pt", revise=True)
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert results == ["rascunho do nllb com falhas mas razoavelmente longo"]


def test_worker_revision_disabled_skips_reviser(qtbot, monkeypatch):
    from src.gui.translation_service import TranslationWorker

    def _fail(*a, **kw):
        raise AssertionError("revisão não deveria ser chamada com revise=False")

    monkeypatch.setattr(
        "src.core.translation_backends.translation_reviser.revise_translation", _fail)
    worker = TranslationWorker(_FakeBackend(), "original text", "en", "pt", revise=False)
    results = []
    worker.finished.connect(results.append)
    worker.run()
    assert results == ["rascunho do nllb com falhas mas razoavelmente longo"]
