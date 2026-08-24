"""Mede a abertura de um PDF pesado pelo caminho de código REAL do app.

Onda P — rodada UX ago/2026. Duas partes:

``gen``      gera um PDF sintético pesado (o baseline de julho usou um livro de
             248,3MB/777 páginas que não está versionado; este comando recria um
             equivalente reproduzível no scratchpad).
``measure``  cronometra a abertura em dois modos (``--modo``, padrão ``ambos``):

  ``bruto``  o caminho ANTIGO, mantido para comparação: renderiza as até 40
             miniaturas EM SÉRIE, como ``toc_widget.load_toc`` fazia antes da
             Onda P (open + 40×``render_thumbnail(page,110)`` + ``get_page(0)``).

  ``novo``   o caminho REAL de hoje, com ``TOCWidget`` + ``ThumbnailWorker``:
               (a) ``load_toc_ms`` — o que ``load_toc`` custa NA THREAD DA GUI
                   (mais ``open``/``get_toc``/``get_page(0)``, somados em
                   ``thread_gui_ms``: o congelamento que o usuário sente)
               (b) ``frio_miniaturas_async_ms`` — do ``start()`` do worker até
                   as 40 miniaturas estarem aplicadas nos itens, cache VAZIO
               (c) ``quente_miniaturas_async_ms`` — o mesmo com o cache quente
                   (reabrir o livro não renderiza nada)

O modo ``novo`` instancia uma ``QApplication`` offscreen (precisa de widget e
event loop de verdade); o modo ``bruto`` não usa Qt para nada — mas o script
inteiro roda com ``QT_QPA_PLATFORM=offscreen``.

Baseline jul/2026 (livro real, 248,3MB/777pág):
    open 92,9ms + miniaturas 1600,7ms (88%) + página 1 114,9ms = 1819ms

Uso:
    venv\\Scripts\\python.exe tools/perf/measure_pdf_open.py gen
    venv\\Scripts\\python.exe tools/perf/measure_pdf_open.py measure --pdf <caminho>
    venv\\Scripts\\python.exe tools/perf/measure_pdf_open.py measure --pdf <c> --modo novo
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.perf._common import emit, fmt  # noqa: E402

# Espelham THUMB_MAX/THUMB_WIDTH de src/gui/widgets/toc_widget.py — usados só
# pelo modo "bruto" (o modo "novo" importa as constantes de verdade).
THUMB_MAX = 40
THUMB_WIDTH = 110

SCRATCHPAD_PADRAO = (
    r"C:\Users\jefer\AppData\Local\Temp\claude"
    r"\G--PROGRAMAS-PYTHON-Biblioteca-pessoal"
    r"\d33b2b3e-1f3e-4ece-bdb6-f340511dd94f\scratchpad\perf"
)


# --------------------------------------------------------------------------- #
# gen
# --------------------------------------------------------------------------- #
def _amostras_base(largura: int, altura: int) -> bytes:
    """Fundo suave (gradiente) na resolução de um escaneamento A4.

    Resolução alta é o que torna a decodificação da miniatura cara — é o custo
    que se quer medir. O gradiente comprime bem, então o arquivo não explode; o
    peso em disco é dosado depois pela mancha de ruído (ver ``_jpeg_pagina``).
    """
    linha = bytes(
        (255 - (x * 60) // largura) if c == 0
        else (250 - (x * 70) // largura) if c == 1
        else (240 - (x * 80) // largura)
        for x in range(largura)
        for c in range(3)
    )
    buf = bytearray()
    tabela = bytes(range(256))
    for y in range(altura):
        if y % 16 == 0:
            desloc = (y * 45) // max(altura, 1)
            tabela = bytes(max(0, v - desloc) for v in range(256))
        buf += linha.translate(tabela)
    return bytes(buf)


def _jpeg_pagina(base: bytes, largura: int, altura: int, semente: int,
                 qualidade: int, bytes_ruido: int) -> bytes:
    """JPEG de uma página: fundo suave + mancha de ruído.

    A mancha tem duas funções: dosar o tamanho do arquivo (ruído comprime mal) e
    tornar cada stream único — streams idênticos seriam deduplicados pelo
    PyMuPDF num único xref, e o PDF não chegaria ao tamanho alvo.
    """
    import fitz

    rng = random.Random(semente)
    buf = bytearray(base)
    if bytes_ruido > 0:
        limite = max(1, len(buf) - bytes_ruido)
        deslocamento = rng.randrange(0, limite)
        buf[deslocamento:deslocamento + bytes_ruido] = rng.randbytes(bytes_ruido)
    pix = fitz.Pixmap(fitz.csRGB, largura, altura, bytes(buf), False)
    return pix.tobytes("jpeg", jpg_quality=qualidade)


def _calibra_ruido(base: bytes, largura: int, altura: int, qualidade: int,
                   bytes_alvo: int) -> int:
    """Quantos bytes de ruído por página para o arquivo bater o tamanho alvo.

    O tamanho do JPEG cresce ~linearmente com a área de ruído, então duas sondas
    (sem ruído e com uma mancha de referência) bastam para interpolar.
    """
    sonda = min(len(base) // 4, 1_500_000)
    sem_ruido = len(_jpeg_pagina(base, largura, altura, 0, qualidade, 0))
    com_ruido = len(_jpeg_pagina(base, largura, altura, 1, qualidade, sonda))
    if bytes_alvo <= sem_ruido or com_ruido <= sem_ruido:
        return 0
    por_byte = (com_ruido - sem_ruido) / sonda
    estimado = int((bytes_alvo - sem_ruido) / max(por_byte, 1e-9))
    return max(0, min(len(base) - 1, estimado))


def comando_gen(args: argparse.Namespace) -> int:
    import fitz

    destino = Path(args.saida)
    destino.parent.mkdir(parents=True, exist_ok=True)

    if destino.exists() and not args.forcar:
        tamanho_mb = destino.stat().st_size / (1024 * 1024)
        with fitz.open(str(destino)) as doc:
            paginas, entradas = doc.page_count, len(doc.get_toc())
        emit("status", "ja_existia")
        emit("pdf", destino)
        emit("tamanho_mb", fmt(tamanho_mb))
        emit("paginas", paginas)
        emit("entradas_toc", entradas)
        return 0

    bytes_alvo = int(args.alvo_mb * 1024 * 1024 / args.paginas)
    largura, altura = args.largura, args.altura
    base = _amostras_base(largura, altura)
    bytes_ruido = _calibra_ruido(base, largura, altura, args.qualidade, bytes_alvo)
    print(f"# imagem por página: {largura}x{altura} q{args.qualidade} "
          f"(~{bytes_alvo // 1024}KB/pág, ruído {bytes_ruido // 1024}KB)", flush=True)

    t0 = time.perf_counter()
    doc = fitz.open()
    for n in range(args.paginas):
        page = doc.new_page(width=595, height=842)  # A4
        page.insert_text(
            (56, 64),
            f"Capítulo sintético — página {n + 1} de {args.paginas}",
            fontsize=14,
        )
        corpo = "\n".join(
            f"Linha {i + 1} — texto de enchimento para dar peso à extração de "
            f"conteúdo e ao layout da página {n + 1}."
            for i in range(24)
        )
        page.insert_textbox(fitz.Rect(56, 92, 539, 380), corpo, fontsize=9)
        page.insert_image(
            fitz.Rect(56, 400, 539, 800),
            stream=_jpeg_pagina(base, largura, altura, n, args.qualidade, bytes_ruido),
        )
        if (n + 1) % 100 == 0:
            print(f"# {n + 1}/{args.paginas} páginas", flush=True)

    # Sumário: capítulos em nível 1 (viram level 0 em TOCEntry, os únicos que
    # ganham miniatura) + subseções em nível 2.
    toc = []
    passo = max(1, args.paginas // args.capitulos)
    for c in range(args.capitulos):
        pagina = min(args.paginas, c * passo + 1)
        toc.append([1, f"Capítulo {c + 1}", pagina])
        if c % 3 == 0:
            toc.append([2, f"Capítulo {c + 1} — seção A", min(args.paginas, pagina + 2)])
    doc.set_toc(toc)

    doc.save(str(destino), deflate=False, garbage=0)
    doc.close()
    gerado_s = time.perf_counter() - t0

    tamanho_mb = destino.stat().st_size / (1024 * 1024)
    emit("status", "gerado")
    emit("pdf", destino)
    emit("tamanho_mb", fmt(tamanho_mb))
    emit("paginas", args.paginas)
    emit("entradas_toc", len(toc))
    emit("entradas_toc_nivel0", sum(1 for e in toc if e[0] == 1))
    emit("geracao_s", fmt(gerado_s))
    return 0


# --------------------------------------------------------------------------- #
# measure
# --------------------------------------------------------------------------- #
def _mede_rodada(caminho: str, rotulo: str) -> dict[str, float | int]:
    """Uma rodada do caminho ANTIGO: open + 40 miniaturas em série + página 1."""
    from src.readers.pdf_reader import PDFReader

    reader = PDFReader(caminho)

    t0 = time.perf_counter()
    reader.open()
    open_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    entradas = reader.get_toc()
    toc_ms = (time.perf_counter() - t0) * 1000.0

    # Réplica do laço que vivia em src/gui/widgets/toc_widget.py:84-94 até a
    # Onda P (removido de lá; preservado aqui como termo de comparação). A única
    # diferença é que aqui não há QPixmap: o widget só contava a miniatura
    # quando ``pixmap.loadFromData(png)`` dava certo; aqui conta quando o PNG
    # existe.
    t0 = time.perf_counter()
    miniaturas = 0
    for entrada in entradas:
        if entrada.level == 0 and miniaturas < THUMB_MAX:
            try:
                png = reader.render_thumbnail(entrada.page, THUMB_WIDTH)
            except Exception:
                png = None
            if png:
                miniaturas += 1
    miniaturas_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    reader.get_page(0)
    pagina1_ms = (time.perf_counter() - t0) * 1000.0

    reader.close()

    total_ms = open_ms + miniaturas_ms + pagina1_ms
    return {
        "rotulo": rotulo,
        "open_ms": open_ms,
        "toc_ms": toc_ms,
        "miniaturas_ms": miniaturas_ms,
        "miniaturas_renderizadas": miniaturas,
        "pagina1_ms": pagina1_ms,
        "total_ms": total_ms,
        "entradas_toc": len(entradas),
        "entradas_toc_nivel0": sum(1 for e in entradas if e.level == 0),
    }


# --------------------------------------------------------------------------- #
# measure — modo "novo" (TOCWidget + ThumbnailWorker, o caminho real de hoje)
# --------------------------------------------------------------------------- #
def _mede_novo(caminho: str, cache_dir: Path) -> dict[str, float | int]:
    """Uma abertura pelo caminho da Onda P, com QApplication offscreen.

    Reproduz ``ReaderView.open_book``: abre o leitor, limpa o TOC, popula o
    ``TOCWidget`` (sem renderizar nada), dispara o ``ThumbnailWorker`` e vai
    renderizar a primeira página — tudo isso na thread da GUI — e só então roda
    o event loop até as miniaturas terminarem de chegar.
    """
    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtWidgets import QApplication

    from src.core.thumbnail_cache import ThumbnailCache
    from src.gui.widgets.toc_widget import TOCWidget, THUMB_WIDTH
    from src.gui.workers.thumbnail_worker import ThumbnailWorker
    from src.readers.pdf_reader import PDFReader
    from src.readers.toc_utils import clean_toc

    app = QApplication.instance() or QApplication([])  # noqa: F841 (mantém viva)

    reader = PDFReader(caminho)

    t0 = time.perf_counter()
    reader.open()
    open_ms = (time.perf_counter() - t0) * 1000.0

    t0 = time.perf_counter()
    entradas = clean_toc(reader.get_toc())
    toc_ms = (time.perf_counter() - t0) * 1000.0

    widget = TOCWidget()

    # (a) O que a thread da GUI paga pelo sumário. Antes: o laço de 40 renders.
    t0 = time.perf_counter()
    widget.load_toc(entradas, with_thumbnails=True)
    load_toc_ms = (time.perf_counter() - t0) * 1000.0

    paginas = widget.pending_thumbnails()
    cache = ThumbnailCache(cache_dir=cache_dir)
    worker = ThumbnailWorker(caminho, paginas, width=THUMB_WIDTH, cache=cache)

    aplicadas: list[int] = []

    def _aplica(page: int, png: bytes) -> None:
        # Caminho REAL: o PNG vira QPixmap na thread da GUI, item a item.
        if widget.set_thumbnail(page, png):
            aplicadas.append(page)

    loop = QEventLoop()
    worker.thumbnail_ready.connect(_aplica)
    worker.finished_batch.connect(lambda _n: loop.quit())

    # (b)/(c) Relógio do assíncrono: do start ao último item aplicado.
    t_async = time.perf_counter()
    worker.start()

    t0 = time.perf_counter()
    reader.get_page(0)  # a GUI segue trabalhando enquanto o worker renderiza
    pagina1_ms = (time.perf_counter() - t0) * 1000.0

    QTimer.singleShot(120_000, loop.quit)  # rede de segurança
    loop.exec()
    miniaturas_async_ms = (time.perf_counter() - t_async) * 1000.0

    worker.cancel()
    worker.wait(5000)
    reader.close()
    widget.deleteLater()

    thread_gui_ms = open_ms + toc_ms + load_toc_ms + pagina1_ms
    return {
        "open_ms": open_ms,
        "toc_ms": toc_ms,
        "load_toc_ms": load_toc_ms,
        "pagina1_ms": pagina1_ms,
        "thread_gui_ms": thread_gui_ms,
        "miniaturas_async_ms": miniaturas_async_ms,
        "miniaturas_aplicadas": len(aplicadas),
        "miniaturas_pedidas": len(paginas),
        "entradas_toc": len(entradas),
    }


def _emite_novo(rotulo: str, r: dict) -> None:
    emit(f"{rotulo}_open_ms", fmt(r["open_ms"]))
    emit(f"{rotulo}_toc_ms", fmt(r["toc_ms"]))
    emit(f"{rotulo}_load_toc_ms", fmt(r["load_toc_ms"]))
    emit(f"{rotulo}_pagina1_ms", fmt(r["pagina1_ms"]))
    emit(f"{rotulo}_thread_gui_ms", fmt(r["thread_gui_ms"]))
    emit(f"{rotulo}_miniaturas_async_ms", fmt(r["miniaturas_async_ms"]))
    emit(f"{rotulo}_miniaturas_aplicadas", r["miniaturas_aplicadas"])
    emit(f"{rotulo}_miniaturas_pedidas", r["miniaturas_pedidas"])


def comando_measure(args: argparse.Namespace) -> int:
    import shutil

    caminho = Path(args.pdf)
    if not caminho.exists():
        print(f"erro: PDF não encontrado: {caminho}", file=sys.stderr)
        return 2

    emit("medicao", "pdf_open")
    emit("modo", args.modo)
    emit("pdf", caminho)
    emit("tamanho_mb", fmt(caminho.stat().st_size / (1024 * 1024)))
    emit("thumb_max", THUMB_MAX)
    emit("thumb_width", THUMB_WIDTH)

    if args.modo in ("bruto", "ambos"):
        for i in range(args.rodadas):
            rotulo = "bruto_frio" if i == 0 else (
                "bruto_quente" if i == 1 else f"bruto_r{i + 1}")
            r = _mede_rodada(str(caminho), rotulo)
            print("---")
            emit("rodada", rotulo)
            emit(f"{rotulo}_open_ms", fmt(r["open_ms"]))
            emit(f"{rotulo}_toc_ms", fmt(r["toc_ms"]))
            emit(f"{rotulo}_miniaturas_ms", fmt(r["miniaturas_ms"]))
            emit(f"{rotulo}_miniaturas_renderizadas", r["miniaturas_renderizadas"])
            emit(f"{rotulo}_pagina1_ms", fmt(r["pagina1_ms"]))
            emit(f"{rotulo}_total_ms", fmt(r["total_ms"]))
            pct = 100.0 * r["miniaturas_ms"] / max(r["total_ms"], 1e-9)
            emit(f"{rotulo}_miniaturas_pct_do_total", fmt(pct))
            if i == 0:
                emit("entradas_toc", r["entradas_toc"])
                emit("entradas_toc_nivel0", r["entradas_toc_nivel0"])

    if args.modo in ("novo", "ambos"):
        cache_dir = Path(args.cache_dir)
        if not args.manter_cache:
            shutil.rmtree(cache_dir, ignore_errors=True)  # (b) exige cache frio

        print("---")
        emit("rodada", "novo_frio")
        emit("cache_dir", cache_dir)
        frio = _mede_novo(str(caminho), cache_dir)
        _emite_novo("novo_frio", frio)

        print("---")
        emit("rodada", "novo_quente")  # (c) reabertura: tudo do cache em disco
        quente = _mede_novo(str(caminho), cache_dir)
        _emite_novo("novo_quente", quente)

        print("---")
        ganho = frio["miniaturas_async_ms"] / max(quente["miniaturas_async_ms"], 1e-9)
        emit("cache_ganho_x", fmt(ganho))
        emit("arquivos_no_cache", len(list(cache_dir.glob("*.png")))
             if cache_dir.exists() else 0)

    print("---")
    emit("baseline_jul_open_ms", "92.9")
    emit("baseline_jul_miniaturas_ms", "1600.7")
    emit("baseline_jul_pagina1_ms", "114.9")
    emit("baseline_jul_total_ms", "1819")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="comando", required=True)

    g = sub.add_parser("gen", help="gera o PDF sintético pesado")
    g.add_argument("--saida", default=str(Path(SCRATCHPAD_PADRAO) / "livro_pesado.pdf"))
    g.add_argument("--paginas", type=int, default=780)
    g.add_argument("--capitulos", type=int, default=60,
                   help="entradas de nível 1 no sumário. Padrão: 60")
    g.add_argument("--alvo-mb", type=float, default=110.0,
                   help="tamanho alvo do arquivo, em MB. Padrão: 110")
    g.add_argument("--largura", type=int, default=2067,
                   help="largura do JPEG por página (A4 a 250dpi). Padrão: 2067")
    g.add_argument("--altura", type=int, default=2924,
                   help="altura do JPEG por página (A4 a 250dpi). Padrão: 2924")
    g.add_argument("--qualidade", type=int, default=70, help="qualidade JPEG")
    g.add_argument("--forcar", action="store_true", help="regera mesmo se já existir")
    g.set_defaults(func=comando_gen)

    m = sub.add_parser("measure", help="mede a abertura do PDF")
    m.add_argument("--pdf", required=True)
    m.add_argument("--modo", choices=("novo", "bruto", "ambos"), default="ambos",
                   help="'novo' = TOCWidget+ThumbnailWorker (caminho atual); "
                        "'bruto' = 40 renders em série (caminho pré-Onda P, "
                        "termo de comparação). Padrão: ambos")
    m.add_argument("--rodadas", type=int, default=2,
                   help="rodadas do modo bruto no MESMO processo: 1ª fria, "
                        "2ª quente. Padrão: 2")
    m.add_argument("--cache-dir",
                   default=str(Path(SCRATCHPAD_PADRAO) / "cache_thumbs"),
                   help="cache de miniaturas usado pelo modo novo (fora de "
                        "data/, para não sujar o cache real do app)")
    m.add_argument("--manter-cache", action="store_true",
                   help="não apaga o cache antes da rodada fria")
    m.set_defaults(func=comando_measure)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
