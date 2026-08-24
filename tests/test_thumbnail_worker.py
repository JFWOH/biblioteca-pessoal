"""ThumbnailWorker: entrega das miniaturas fora da thread da GUI (Onda P).

Testes GUI do repo rodam offscreen; o ``qtbot`` do pytest-qt cuida do
``QApplication``. Todo worker criado aqui é esperado (``wait``) antes do fim do
teste — QThread destruído com a thread do SO viva é a receita do SIGABRT do
PR #32.
"""

import os
import threading
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.core.thumbnail_cache import ThumbnailCache  # noqa: E402
from src.gui.workers.thumbnail_worker import ThumbnailWorker  # noqa: E402


PNG = b"\x89PNG\r\n\x1a\n" + b"miniatura"


@pytest.fixture
def livro(tmp_path):
    p = tmp_path / "livro.pdf"
    p.write_bytes(b"%PDF-1.7\n" + b"z" * 300)
    return p


@pytest.fixture
def cache(tmp_path):
    return ThumbnailCache(cache_dir=tmp_path / "thumbs")


def _roda(qtbot, worker, timeout=10000):
    """Inicia o worker, coleta as entregas e espera o fim de verdade."""
    recebidas = []
    worker.thumbnail_ready.connect(lambda page, png: recebidas.append((page, png)))
    with qtbot.waitSignal(worker.finished, timeout=timeout):
        worker.start()
    worker.wait(timeout)
    return recebidas


# ── Entrega ───────────────────────────────────────────────────────────

def test_entrega_uma_miniatura_por_pagina(qtbot, livro, cache):
    pedidos = []

    def provider(page, width):
        pedidos.append((page, width))
        return PNG + bytes([page])

    worker = ThumbnailWorker(livro, [0, 4, 9], width=110,
                             cache=cache, provider=provider)
    recebidas = _roda(qtbot, worker)

    assert [p for p, _ in recebidas] == [0, 4, 9]  # ordem do sumário preservada
    assert pedidos == [(0, 110), (4, 110), (9, 110)]
    assert recebidas[1][1] == PNG + bytes([4])


def test_paginas_repetidas_sao_renderizadas_uma_vez(qtbot, livro, cache):
    chamadas = []

    def provider(page, width):
        chamadas.append(page)
        return PNG

    worker = ThumbnailWorker(livro, [3, 3, 7, 3], cache=cache, provider=provider)
    recebidas = _roda(qtbot, worker)

    assert chamadas == [3, 7]
    assert [p for p, _ in recebidas] == [3, 7]


def test_provider_que_falha_ou_devolve_none_e_pulado(qtbot, livro, cache):
    def provider(page, width):
        if page == 0:
            raise RuntimeError("render falhou")
        if page == 1:
            return None
        return PNG

    worker = ThumbnailWorker(livro, [0, 1, 2], cache=cache, provider=provider)
    recebidas = _roda(qtbot, worker)

    assert [p for p, _ in recebidas] == [2]  # ADR-005: falha vira ausência


def test_finished_batch_conta_as_entregues(qtbot, livro, cache):
    lote = []
    worker = ThumbnailWorker(livro, [0, 1], cache=cache,
                             provider=lambda page, width: PNG)
    worker.finished_batch.connect(lote.append)
    _roda(qtbot, worker)
    assert lote == [2]


# ── Cache ─────────────────────────────────────────────────────────────

def test_grava_no_cache_e_reabre_sem_renderizar(qtbot, livro, cache):
    chamadas = []

    def provider(page, width):
        chamadas.append(page)
        return PNG + bytes([page])

    primeira = ThumbnailWorker(livro, [0, 5], cache=cache, provider=provider)
    assert len(_roda(qtbot, primeira)) == 2
    assert chamadas == [0, 5]

    # Segunda abertura do MESMO livro: tudo vem do disco.
    segunda = ThumbnailWorker(livro, [0, 5], cache=cache, provider=provider)
    recebidas = _roda(qtbot, segunda)

    assert chamadas == [0, 5]  # provider não foi chamado de novo
    assert [png for _, png in recebidas] == [PNG + bytes([0]), PNG + bytes([5])]


def test_arquivo_alterado_invalida_o_cache(qtbot, livro, cache):
    chamadas = []

    def provider(page, width):
        chamadas.append(page)
        return PNG

    _roda(qtbot, ThumbnailWorker(livro, [0], cache=cache, provider=provider))
    time.sleep(0.01)
    livro.write_bytes(b"%PDF-1.7\n" + b"OUTRA EDICAO" * 40)
    _roda(qtbot, ThumbnailWorker(livro, [0], cache=cache, provider=provider))

    assert chamadas == [0, 0]  # renderizou de novo


# ── Cancelamento ──────────────────────────────────────────────────────

def test_cancel_interrompe_no_meio_do_lote(qtbot, livro, cache):
    entrou = threading.Event()
    liberar = threading.Event()
    chamadas = []

    def provider(page, width):
        chamadas.append(page)
        entrou.set()
        liberar.wait(5)  # segura o worker na 1ª página até o cancel chegar
        return PNG

    worker = ThumbnailWorker(livro, list(range(30)), cache=cache,
                             provider=provider)
    recebidas = []
    worker.thumbnail_ready.connect(lambda p, png: recebidas.append(p))
    worker.start()
    assert entrou.wait(5)

    worker.cancel()
    liberar.set()
    assert worker.wait(10000)

    assert worker.cancelled is True
    assert len(chamadas) < 30           # não percorreu o lote inteiro
    assert recebidas == []              # nada é emitido depois do cancel


def test_cancel_antes_de_iniciar_nao_renderiza_nada(qtbot, livro, cache):
    chamadas = []
    worker = ThumbnailWorker(livro, [0, 1, 2], cache=cache,
                             provider=lambda p, w: chamadas.append(p) or PNG)
    worker.cancel()
    with qtbot.waitSignal(worker.finished, timeout=10000):
        worker.start()
    worker.wait(10000)
    assert chamadas == []


# ── Caminho real (PyMuPDF), sem provider injetado ─────────────────────

def test_abre_o_proprio_leitor_quando_nao_ha_provider(qtbot, tmp_path, cache):
    fitz = pytest.importorskip("fitz")

    pdf = tmp_path / "real.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=300, height=400)
    doc.save(str(pdf))
    doc.close()

    worker = ThumbnailWorker(pdf, [0, 2], width=110, cache=cache)
    recebidas = _roda(qtbot, worker)

    assert [p for p, _ in recebidas] == [0, 2]
    assert all(png.startswith(b"\x89PNG") for _, png in recebidas)
    assert cache.get(pdf, 0, 110) is not None  # gravou no cache


def test_arquivo_inexistente_nao_derruba_o_worker(qtbot, tmp_path, cache):
    worker = ThumbnailWorker(tmp_path / "sumiu.pdf", [0, 1], cache=cache)
    assert _roda(qtbot, worker) == []
