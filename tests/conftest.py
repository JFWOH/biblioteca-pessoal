"""Fixtures globais da suíte.

Higiene de recursos nativos: o chromadb cacheia um ``System`` por path no
``SharedSystemClient`` — como os testes criam engines com ``tmp_path`` novo,
o cache só cresce (conexões sqlite + threads nativas), até estourar o limite
do runner no CI Linux com SIGABRT (exit 134) em posição estável por
configuração (~63% da suíte cheia; repro mínimo: proactive+rag_engine, 2026-07-16).
O finalizer abaixo limpa o cache após CADA teste, apenas quando o chromadb
já foi importado — testes que não usam Chroma não pagam nada.
"""
import sys

import pytest


@pytest.fixture(autouse=True)
def _clear_chroma_system_cache():
    yield
    client_mod = sys.modules.get("chromadb.api.client")
    if client_mod is not None:
        try:
            client_mod.SharedSystemClient.clear_system_cache()
        except Exception:
            pass
