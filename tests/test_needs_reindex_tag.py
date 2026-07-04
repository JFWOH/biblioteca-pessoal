"""Regressão: needs_reindex não pode tratar 'bge-m3:latest' vs 'bge-m3' como
modelos diferentes (aliases da MESMA dimensão).

O bug real: _get_embedding resolve a tag exata (':latest') e ela vai para a
metadata da collection; a config traz o nome cru; needs_reindex comparava as
strings antes de qualquer embedding → busca vetorial bloqueada para sempre,
pedindo reindex a cada reinício do app (com 24k chunks perfeitamente válidos).
"""
from src.core.rag_engine import RAGEngine


class FakeCollection:
    def __init__(self, embed_model: str, n: int = 100):
        self.metadata = {"embed_model": embed_model, "hnsw:space": "cosine"}
        self._n = n

    def count(self):
        return self._n


def _engine(configured: str, stored: str, n: int = 100) -> RAGEngine:
    eng = RAGEngine.__new__(RAGEngine)  # sem __init__: nada de Chroma/Ollama real
    eng._embed_model = configured
    eng._collection = FakeCollection(stored, n)
    return eng


def test_model_base_strips_tag():
    assert RAGEngine._model_base("bge-m3:latest") == "bge-m3"
    assert RAGEngine._model_base("bge-m3") == "bge-m3"
    assert RAGEngine._model_base("  BGE-M3:Q4  ") == "bge-m3"
    assert RAGEngine._model_base(None) == ""


def test_same_model_different_tag_does_not_need_reindex():
    """O caso do bug: metadata ':latest' vs config crua → NÃO reindexar."""
    assert _engine("bge-m3", "bge-m3:latest").needs_reindex() is False
    assert _engine("bge-m3:latest", "bge-m3").needs_reindex() is False


def test_actually_different_model_needs_reindex():
    assert _engine("bge-m3", "nomic-embed-text:latest").needs_reindex() is True
    assert _engine("nomic-embed-text", "bge-m3:latest").needs_reindex() is True


def test_empty_collection_never_needs_reindex():
    assert _engine("bge-m3", "nomic-embed-text", n=0).needs_reindex() is False


def test_no_collection_never_needs_reindex():
    eng = RAGEngine.__new__(RAGEngine)
    eng._embed_model = "bge-m3"
    eng._collection = None
    assert eng.needs_reindex() is False
