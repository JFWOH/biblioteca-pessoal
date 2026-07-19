"""Profiling reprodutível das transições de tela da Biblioteca Pessoal.

Contexto (rodada de ajustes pós-teste, F3): o usuário relatou que "o app ficou
mais lento nas transições de tela" após o programa de melhorias jul/2026. Este
script isola e MEDE as três hipóteses do orquestrador, para corrigir só o que a
medição confirmar:

  1. QSS DUPLICADO — ``MainWindow._apply_theme`` aplica a folha (~3.900 linhas)
     na ``QApplication`` E na própria janela (``self.setStyleSheet``). Todo card
     descendente resolve estilo contra AS DUAS folhas em cada polish. Mede-se o
     custo de (a) só a folha da QApplication vs (b) folha também na janela-mãe.
  2. RECONSTRUÇÃO DA GRADE — ``LibraryView._refresh_grid`` destrói e recria TODOS
     os cards a cada carga de seção. Mede-se o custo por reconstrução completa.
  3. CONSULTAS POR TRANSIÇÃO — get_progress_map / get_in_progress_books /
     get_statistics (+ streak/weekly). Mede-se contra um DB sintético.

NÃO faz parte da suíte de testes (tempo não entra no pytest). Rodar com o venv:

    venv\\Scripts\\python.exe tools\\profile_transitions.py [n_livros] [n_cargas]

Saída: números de cada medição em stdout. Use antes/depois de uma correção,
na MESMA máquina, para comparar.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter

# Plataforma offscreen ANTES de qualquer import de PyQt6 (headless/reprodutível).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Nunca tentar baixar assets de IA neste script (não tocamos RAG/TTS aqui).
os.environ.setdefault("HF_HUB_OFFLINE", "1")

# Console Windows pode ser cp1252 — a saída usa Δ/acentos, força UTF-8.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - ambientes sem reconfigure
    pass

# Raiz do projeto no sys.path (para importar ``src`` rodando de qualquer cwd).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMainWindow  # noqa: E402
from PyQt6.QtGui import QPixmap, QColor  # noqa: E402

from src.gui.library_view import LibraryView  # noqa: E402
from src.gui.styles import get_theme  # noqa: E402


# ── Dados sintéticos ────────────────────────────────────────────────────────

_COLORS = [
    "#6366f1", "#ef4444", "#10b981", "#f59e0b",
    "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16",
]


def _make_dummy_covers(n: int, out_dir: Path) -> list[str]:
    """Gera ``n`` PNGs sólidos pequenos (capas dummy) e devolve os caminhos.

    Exercita o caminho real de carregamento/escala de capa no BookCard, sem
    depender de arquivos do usuário.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for i in range(n):
        pm = QPixmap(160, 220)
        pm.fill(QColor(_COLORS[i % len(_COLORS)]))
        p = out_dir / f"cover_{i}.png"
        pm.save(str(p), "PNG")
        paths.append(str(p))
    return paths


def _make_books(n: int, cover_paths: list[str]) -> list[dict]:
    """Lista de ``n`` dicts de livro, ~2/3 com capa e ~1/3 com progresso."""
    fmts = ["PDF", "EPUB", "MOBI", "TXT", "DOCX"]
    books: list[dict] = []
    for i in range(n):
        books.append({
            "id": i + 1,
            "title": f"Livro de Teste Número {i + 1} com Título Razoavelmente Longo",
            "author": f"Autor {i % 12}",
            "file_path": str(_ROOT / "tools" / f"__nao_existe_{i}.pdf"),
            "file_format": fmts[i % len(fmts)],
            "cover_path": cover_paths[i % len(cover_paths)] if i % 3 != 0 else "",
            "is_favorite": 1 if i % 7 == 0 else 0,
            "percentage": (i * 137) % 100 if i % 2 == 0 else 0,
        })
    return books


# ── Medição 1+2: construção/reconstrução da grade (com/sem folha na janela) ──

def _flush(app: QApplication) -> None:
    """Processa eventos INCLUINDO a deleção adiada (deleteLater).

    Fora de um event loop rodando, ``processEvents()`` sozinho NÃO consome os
    eventos ``DeferredDelete`` — os cards destruídos por ``_clear_grid``
    acumulariam entre as recargas e contaminariam a medição (custo crescente).
    ``sendPostedEvents(None, DeferredDelete)`` reproduz o retorno ao event
    loop do app real, onde os cards são de fato destruídos a cada transição.
    """
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()


def _make_window(app: QApplication, qss: str, window_sheet: bool):
    win = QMainWindow()
    win.resize(1280, 800)
    if window_sheet:
        win.setStyleSheet(qss)
    view = LibraryView()
    win.setCentralWidget(view)
    win.show()
    _flush(app)
    return win, view


def measure_grid_pair(app: QApplication, books: list[dict], loads: int) -> dict:
    """Mede a grade em DOIS cenários de folha, intercalados, em DOIS caminhos.

    Cenários de folha (hipótese 1):
      (A) só a folha da QApplication (correção proposta) vs (B) folha na
      QApplication E na janela-mãe (estado da Onda 0.2). As cargas são
      intercaladas A,B,A,B,… para que deriva da máquina (térmica, processos
      de fundo) afete os dois cenários por igual.

    Caminhos de recarga (hipótese 2):
      - ``rebuild``: o progress_map alterna a cada carga (dados MUDARAM) —
        força ``_clear_grid`` + recriação de todos os BookCards, como uma
        troca de seção com dados novos. Comparável ao baseline pré-correção,
        onde TODA recarga era assim.
      - ``same``: recarrega o MESMO estado (dados idênticos) — o caminho de
        "voltar à biblioteca sem nada ter mudado". Após a correção do atalho
        em ``load_books``, este caminho não reconstrói os cards.
      - ``resort`` (rodada A4): MESMOS livros, ORDEM alternada (invertida) a
        cada carga, progress_map CONSTANTE — reordenação/filtro. Com o
        casamento por ``book_id`` (A4) o card do mesmo livro é reutilizado e as
        capas NÃO recarregam do disco; antes (reciclagem por POSIÇÃO, PR #43) a
        reordenação trocava o livro de cada posição e recarregava todas as
        capas (~custo do rebuild).
    """
    qss = get_theme("dark")
    app.setStyleSheet(qss)

    win_a, view_a = _make_window(app, qss, window_sheet=False)
    win_b, view_b = _make_window(app, qss, window_sheet=True)

    progress_1 = {b["id"]: b["percentage"] for b in books if b["percentage"]}
    # Variante com percentuais deslocados: qualquer diferença de valor força
    # a reconstrução completa (o atalho compara os dicts por valor).
    progress_2 = {k: (v % 99) + 1 for k, v in progress_1.items()}

    # Warmup (não cronometrado): 1ª carga paga custos únicos de fonte/layout.
    view_a.load_books(books, progress_map=progress_1)
    view_b.load_books(books, progress_map=progress_1)
    _flush(app)

    samples = {
        "a_rebuild": [], "b_rebuild": [], "a_same": [], "b_same": [],
        "a_resort": [], "b_resort": [],
    }
    for i in range(loads):
        pm = progress_2 if i % 2 == 0 else progress_1  # alterna → rebuild

        for key, view in (("a_rebuild", view_a), ("b_rebuild", view_b)):
            t0 = perf_counter()
            view.load_books(books, progress_map=pm)
            _flush(app)
            samples[key].append((perf_counter() - t0) * 1000.0)

        for key, view in (("a_same", view_a), ("b_same", view_b)):
            t0 = perf_counter()
            view.load_books(books, progress_map=pm)  # mesmo estado → atalho
            _flush(app)
            samples[key].append((perf_counter() - t0) * 1000.0)

    # ── Cenário RESORT (rodada A4) ──────────────────────────────────────────
    # Mesmos livros, ORDEM alternada (invertida) a cada recarga, progress_map
    # CONSTANTE. Re-baseline na ordem direta antes de cronometrar para isolar
    # o custo da reordenação pura (mesmos dados, só a ordem muda).
    books_rev = list(reversed(books))
    view_a.load_books(books, progress_map=progress_1)
    view_b.load_books(books, progress_map=progress_1)
    _flush(app)
    for i in range(loads):
        ordered = books_rev if i % 2 == 0 else books  # alterna a ordem
        for key, view in (("a_resort", view_a), ("b_resort", view_b)):
            t0 = perf_counter()
            view.load_books(ordered, progress_map=progress_1)
            _flush(app)
            samples[key].append((perf_counter() - t0) * 1000.0)

    win_a.close()
    win_b.close()
    _flush(app)

    def _stats(vals: list[float]) -> dict:
        return {
            "mean_ms": statistics.mean(vals),
            "median_ms": statistics.median(vals),
            "min_ms": min(vals),
            "max_ms": max(vals),
        }

    return {k: _stats(v) for k, v in samples.items()}


# ── Medição 3: consultas por transição (DB sintético real) ──────────────────

def measure_queries(n_books: int, iters: int = 200) -> dict:
    """Mede as consultas disparadas a cada transição contra um DB sintético."""
    from src.core.database import LibraryDB

    tmp = Path(tempfile.mkdtemp(prefix="profile_lib_")) / "lib.db"
    db = LibraryDB(tmp)
    for i in range(n_books):
        bid = db.add_book(
            title=f"Livro {i}", author=f"Autor {i % 12}",
            file_path=str(tmp.parent / f"b{i}.pdf"), file_format="pdf",
        )
        # ~40% com progresso (metade concluídos, metade em andamento).
        if i % 5 < 2:
            total = 300
            cur = total if i % 2 == 0 else (i * 7) % total + 1
            db.update_reading_progress(bid, cur, total, time_spent=600)

    def _bench(fn) -> float:
        # aquece
        fn()
        samples = []
        for _ in range(iters):
            t0 = perf_counter()
            fn()
            samples.append((perf_counter() - t0) * 1000.0)
        return statistics.median(samples)

    results = {
        "get_progress_map": _bench(db.get_progress_map),
        "get_in_progress_books": _bench(db.get_in_progress_books),
        "get_statistics": _bench(db.get_statistics),
        "get_reading_streak": _bench(db.get_reading_streak),
        "get_weekly_reading_minutes": _bench(db.get_weekly_reading_minutes),
    }
    # Soma "por transição de seção" (o que _load_library dispara em "all").
    results["_sum_load_library_all_ms"] = (
        results["get_progress_map"]
        + results["get_in_progress_books"]
        + results["get_statistics"]
    )
    return results


def main() -> None:
    n_books = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    loads = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory(prefix="profile_covers_") as tmp:
        covers = _make_dummy_covers(8, Path(tmp))
        books = _make_books(n_books, covers)

        print("=" * 68)
        print(f"PROFILE transições — {n_books} livros, {loads} recargas cronometradas")
        print(f"QSS: {len(get_theme('dark').splitlines())} linhas | platform={os.environ['QT_QPA_PLATFORM']}")
        print("=" * 68)

        # Medição 1+2 — (A) só folha da QApplication (correção proposta) vs
        # (B) folha também na janela-mãe (estado da Onda 0.2), intercaladas,
        # nos dois caminhos: rebuild forçado e recarga de estado idêntico.
        r = measure_grid_pair(app, books, loads=loads)

        def _fmt(s: dict) -> str:
            return (f"{s['mean_ms']:.1f} / {s['median_ms']:.1f} "
                    f"({s['min_ms']:.1f}-{s['max_ms']:.1f}) ms")

        print("\n[GRADE] media / mediana / (min-max) ms por recarga")
        print("  rebuild forçado (dados mudaram a cada carga):")
        print(f"    (A) só folha da QApplication : {_fmt(r['a_rebuild'])}")
        print(f"    (B) folha app + janela-mãe   : {_fmt(r['b_rebuild'])}")
        delta = r["b_rebuild"]["median_ms"] - r["a_rebuild"]["median_ms"]
        base = r["b_rebuild"]["median_ms"]
        pct = (delta / base * 100.0) if base else 0.0
        print(f"    Δ folha dupla (B-A, mediana) : {delta:+.1f} ms  ({pct:+.1f}% de B)")
        print("  recarga idêntica (voltar à biblioteca sem mudança de dados):")
        print(f"    (A) só folha da QApplication : {_fmt(r['a_same'])}")
        print(f"    (B) folha app + janela-mãe   : {_fmt(r['b_same'])}")
        print("  resort (mesmos livros, ordem invertida — reordenação/filtro):")
        print(f"    (A) só folha da QApplication : {_fmt(r['a_resort'])}")
        print(f"    (B) folha app + janela-mãe   : {_fmt(r['b_resort'])}")

    print("\n[CONSULTAS] por transição (mediana ms, DB sintético)")
    q = measure_queries(n_books)
    for k, v in q.items():
        if not k.startswith("_"):
            print(f"  {k:<28}: {v:.3f} ms")
    print(f"  {'soma _load_library(all)':<28}: {q['_sum_load_library_all_ms']:.3f} ms")


if __name__ == "__main__":
    main()
