"""O load do NLLB deve liberar a rede (HF_HUB_OFFLINE=0) e restaurar depois.

Garante que o modo offline forçado pelo Kokoro não bloqueie o download do
modelo de tradução na primeira vez.
"""
import os
from unittest.mock import patch

import pytest

from src.core.translation_backends.nllb_backend import NLLBBackend


def test_load_uses_online_then_restores(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    backend = NLLBBackend()
    captured = {}

    def fake_from_pretrained(*args, **kwargs):
        captured["during"] = os.environ.get("HF_HUB_OFFLINE")
        raise RuntimeError("boom")  # força o caminho de erro para checar o finally

    with patch("transformers.AutoTokenizer.from_pretrained", side_effect=fake_from_pretrained):
        with pytest.raises(RuntimeError):
            backend._load_model_lazy()

    assert captured["during"] == "0"                 # durante o load: online
    assert os.environ.get("HF_HUB_OFFLINE") == "1"   # restaurou o valor anterior


def test_load_removes_var_when_absent_before(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    backend = NLLBBackend()

    def fake_from_pretrained(*args, **kwargs):
        raise RuntimeError("boom")

    with patch("transformers.AutoTokenizer.from_pretrained", side_effect=fake_from_pretrained):
        with pytest.raises(RuntimeError):
            backend._load_model_lazy()

    assert os.environ.get("HF_HUB_OFFLINE") is None  # não vaza '0'
