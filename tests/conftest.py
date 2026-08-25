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


def pytest_sessionfinish(session, exitstatus):
    """Blinda o ENCERRAMENTO contra o crash nativo residual (zona Qt).

    Documentado desde 2026-06-28 e caçado em 2026-07-16 (PR #14/#18): além do
    modo dominante do chromadb (resolvido acima), restava um flake nativo no
    GC de encerramento — o ``gc_collect_harder`` do plugin
    ``unraisableexception`` roda no ``pytest_unconfigure`` e varre objetos
    Qt/C++ já órfãos do teardown da QApplication, segfaultando no CI Linux
    (SIGSEGV/exit 139). O crescimento da suíte (1583→1865 na rodada ago/2026)
    tornou o flake frequente demais para o retry dos shards absorver (3×/3).

    ``gc.freeze()`` move todos os sobreviventes para a geração permanente —
    fora do alcance de QUALQUER coleta posterior. Neste ponto os testes já
    terminaram e o relatório já foi emitido; o processo está indo morrer, e
    liberar essa memória é trabalho (perigoso) que ninguém precisa.
    """
    import gc

    gc.collect()
    gc.freeze()
