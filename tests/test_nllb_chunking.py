"""Testes do fatiamento por sentenças do NLLBBackend (corrige repetição/truncamento).

Textos longos numa única chamada ao modelo (truncation=True, max_length=512)
faziam o NLLB degenerar em repetição. translate() agora fatia por sentenças
em lotes menores; estes testes cobrem os dois helpers puros e a orquestração
com _translate_one_batch mockado (sem carregar o modelo real).
"""
from unittest.mock import patch

from src.core.translation_backends.nllb_backend import NLLBBackend


# ── _split_sentences ──────────────────────────────────────────────────

def test_split_on_common_terminators():
    text = "Frase um. Frase dois! Frase tres? Frase quatro…"
    assert NLLBBackend._split_sentences(text) == [
        "Frase um.", "Frase dois!", "Frase tres?", "Frase quatro…",
    ]


def test_split_on_newlines():
    text = "Linha um\nLinha dois\n\nLinha tres"
    assert NLLBBackend._split_sentences(text) == ["Linha um", "Linha dois", "Linha tres"]


def test_split_empty_text():
    assert NLLBBackend._split_sentences("") == []
    assert NLLBBackend._split_sentences("   ") == []


def test_split_no_terminator_is_one_sentence():
    assert NLLBBackend._split_sentences("uma frase sem ponto final") == [
        "uma frase sem ponto final"
    ]


# ── _batch_sentences ──────────────────────────────────────────────────

def test_batch_packs_short_sentences_together():
    sentences = ["Curta um.", "Curta dois.", "Curta tres."]
    batches = NLLBBackend._batch_sentences(sentences, max_chars=1400)
    assert len(batches) == 1
    assert batches[0] == "Curta um. Curta dois. Curta tres."


def test_batch_splits_when_exceeding_budget():
    sentences = ["a" * 800 + ".", "b" * 800 + "."]
    batches = NLLBBackend._batch_sentences(sentences, max_chars=1000)
    assert len(batches) == 2
    assert batches[0] == "a" * 800 + "."
    assert batches[1] == "b" * 800 + "."


def test_batch_single_sentence_larger_than_budget_is_its_own_batch():
    huge = "x" * 2000 + "."
    batches = NLLBBackend._batch_sentences([huge], max_chars=1400)
    assert batches == [huge]


def test_batch_empty_list():
    assert NLLBBackend._batch_sentences([]) == []


# ── translate() orquestrando os lotes (modelo mockado) ────────────────

def test_translate_calls_one_batch_per_chunk_in_order(monkeypatch):
    backend = NLLBBackend()
    backend._is_loaded = True  # pula _load_model_lazy
    backend._device = "cpu"
    monkeypatch.setattr(backend, "_load_model_lazy", lambda: None)

    calls = []

    def fake_translate_one_batch(batch, src_nllb, tgt_nllb):
        calls.append(batch)
        return f"[T:{batch[:10]}]"

    with patch.object(backend, "_translate_one_batch", side_effect=fake_translate_one_batch):
        text = "Primeira frase aqui. " + ("x" * 1500) + ". Ultima frase aqui."
        result = backend.translate(text, src_lang="en", tgt_lang="pt")

    assert len(calls) >= 2  # o bloco gigante forçou mais de um lote
    assert result.startswith("[T:")
    # Ordem preservada: o resultado reflete a ordem dos lotes gerados
    assert result == " ".join(f"[T:{c[:10]}]" for c in calls)


def test_translate_empty_text_returns_empty_without_loading_model(monkeypatch):
    backend = NLLBBackend()
    called = []
    monkeypatch.setattr(backend, "_load_model_lazy", lambda: called.append(True))
    assert backend.translate("   ") == ""
    assert called == []  # não carrega o modelo à toa


def test_translate_single_short_sentence_one_batch_call(monkeypatch):
    backend = NLLBBackend()
    monkeypatch.setattr(backend, "_load_model_lazy", lambda: None)
    calls = []
    with patch.object(backend, "_translate_one_batch",
                      side_effect=lambda b, s, t: calls.append(b) or "traduzido"):
        result = backend.translate("Uma frase curta.", src_lang="en", tgt_lang="pt")
    assert len(calls) == 1
    assert result == "traduzido"
