"""Regressão: livros grandes estouravam o teto de batch do Chroma.

Erro real (2026-07-06, book_id=58, 'Box Coleção Ditadura'):
"Batch size 9820 exceeds maximum batch size 5461" — depois de gerar TODOS os
9820 embeddings, o upsert único descartava o trabalho inteiro. O salvamento
agora é em lotes sob o limite do cliente.
"""
from src.core.document_indexer_service import upsert_in_batches, _resolve_max_batch


class FakeCollection:
    """Imita o Chroma: rejeita lotes acima do limite, registra chamadas."""

    def __init__(self, max_batch: int = 5461, expose_client_limit: bool = False):
        self.max_batch = max_batch
        self.calls: list[int] = []
        self.received_ids: list[str] = []
        if expose_client_limit:
            class _Client:
                def __init__(self, limit):
                    self._limit = limit

                def get_max_batch_size(self):
                    return self._limit

            self._client = _Client(max_batch)

    def upsert(self, ids, embeddings, documents, metadatas):
        if len(ids) > self.max_batch:
            raise ValueError(
                f"Batch size {len(ids)} exceeds maximum batch size {self.max_batch}")
        assert len(ids) == len(embeddings) == len(documents) == len(metadatas)
        self.calls.append(len(ids))
        self.received_ids.extend(ids)


def _payload(n: int):
    ids = [f"c{i}" for i in range(n)]
    return ids, [[0.1] * 4] * n, [f"doc {i}" for i in range(n)], [{"i": i} for i in range(n)]


def test_case_real_9820_chunks_does_not_exceed_limit():
    col = FakeCollection(max_batch=5461)
    ids, emb, docs, metas = _payload(9820)
    sent = upsert_in_batches(col, ids, emb, docs, metas)
    assert sent == 9820
    assert all(size <= 5461 for size in col.calls)
    assert col.received_ids == ids  # todos, na ordem, sem perda


def test_small_book_single_call():
    col = FakeCollection()
    ids, emb, docs, metas = _payload(120)
    assert upsert_in_batches(col, ids, emb, docs, metas) == 120
    assert col.calls == [120]


def test_uses_client_limit_when_exposed():
    col = FakeCollection(max_batch=1000, expose_client_limit=True)
    ids, emb, docs, metas = _payload(2500)
    sent = upsert_in_batches(col, ids, emb, docs, metas)
    assert sent == 2500
    assert all(size <= 1000 for size in col.calls)
    assert len(col.calls) == 3


def test_fallback_limit_when_client_silent():
    """Sem get_max_batch_size no cliente → teto conservador de 4000."""
    col = FakeCollection(max_batch=5461)  # sem expose_client_limit
    assert _resolve_max_batch(col) == 4000
    ids, emb, docs, metas = _payload(9000)
    upsert_in_batches(col, ids, emb, docs, metas)
    assert all(size <= 4000 for size in col.calls)


def test_cancel_between_batches_stops_early():
    col = FakeCollection(max_batch=5461)
    ids, emb, docs, metas = _payload(9000)
    cancel_after_first = iter([False, True])
    sent = upsert_in_batches(col, ids, emb, docs, metas,
                             should_cancel=lambda: next(cancel_after_first),
                             batch_size=4000)
    assert sent == 4000          # só o primeiro lote
    assert len(col.calls) == 1   # parou cooperativamente


def test_empty_ids_is_noop():
    col = FakeCollection()
    assert upsert_in_batches(col, [], [], [], []) == 0
    assert col.calls == []


def test_progress_callback_reports_cumulative():
    col = FakeCollection()
    ids, emb, docs, metas = _payload(9000)
    progress = []
    upsert_in_batches(col, ids, emb, docs, metas, batch_size=4000,
                      progress_cb=lambda done, total: progress.append((done, total)))
    assert progress == [(4000, 9000), (8000, 9000), (9000, 9000)]
