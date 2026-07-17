"""Testes da pré-síntese TTS da próxima página (tarefa 3.6).

Cobre: a decisão pura de "qual é o próximo texto", o cache puro de áudio, o
worker de síntese (com router falso — TTS mockado, sem áudio real), o modo
"prepared" do AudioWorker (player falso) e a fiação estática no reader_view
(que não é importável na suíte por causa do QtWebEngine).
"""
from pathlib import Path
from types import SimpleNamespace

from src.core.audio.continuous_navigation import next_readable_page_with_text
from src.core.audio.continuous_player import PreSynthesisCache


# ── Decisão pura: próxima página + texto ───────────────────────────────

PAGES = {0: "Cap. um.", 1: "", 2: "  ", 3: "Página quatro.", 4: ""}


def _get(page):
    return PAGES.get(page, "")


def test_next_page_with_text_returns_page_and_text():
    assert next_readable_page_with_text(_get, current=0, total=5) == (3, "Página quatro.")


def test_next_page_with_text_none_at_end():
    assert next_readable_page_with_text(_get, current=3, total=5) is None


def test_next_page_with_text_respects_max_skip():
    empty = {p: "" for p in range(50)}
    empty[20] = "longe"
    assert next_readable_page_with_text(lambda p: empty[p], 0, 50, max_skip=10) is None
    assert next_readable_page_with_text(lambda p: empty[p], 0, 50, max_skip=30) == (20, "longe")


def test_next_page_with_text_exception_is_empty():
    def boom(p):
        if p == 1:
            raise RuntimeError("corrompida")
        return "ok" if p == 2 else ""
    assert next_readable_page_with_text(boom, 0, 5) == (2, "ok")


# ── Cache puro de áudio pré-sintetizado ────────────────────────────────

def test_cache_store_and_take():
    c = PreSynthesisCache()
    key = (1, 5, "voz")
    segs = [{"audio_data": b"x", "sample_rate": 24000, "channels": 1, "dtype": "int16"}]
    assert c.pending_key is None
    c.store(key, segs)
    assert c.has(key)
    assert c.pending_key == key
    assert c.take(key) == segs
    assert c.pending_key is None  # take remove
    assert c.take(key) is None    # já foi


def test_cache_key_mismatch_returns_none():
    c = PreSynthesisCache()
    c.store((1, 5, "voz"), [{"audio_data": b"x"}])
    assert c.take((1, 6, "voz")) is None  # página diferente
    assert c.has((1, 5, "voz"))           # o original continua


def test_cache_invalidate():
    c = PreSynthesisCache()
    c.store((1, 5, "voz"), [{"audio_data": b"x"}])
    c.invalidate()
    assert c.pending_key is None
    assert c.take((1, 5, "voz")) is None


# ── Worker de pré-síntese (router falso, TTS mockado) ─────────────────

def _fake_router(provider_name="kokoro"):
    profile = SimpleNamespace(
        language="pt", style="neutral", voice_id="", rate=1.0, volume=1.0,
        preferred_provider=provider_name)
    provider = SimpleNamespace(
        name=provider_name,
        channels=1,
        dtype="int16",
        latency_profile=lambda: "low",
        synthesize=lambda chunk, voice_id=None, rate=1.0, volume=1.0: SimpleNamespace(
            success=True, audio_data=b"\x00\x01\x02", sample_rate=24000),
    )
    return SimpleNamespace(
        get_book_profile=lambda: profile,
        get_assistant_profile=lambda: profile,
        _get_provider_for_profile=lambda p: provider,
        _resolve_voice=lambda p, lang, style: "pt-voice",
    )


def test_presynth_worker_synthesizes_segments(qtbot):
    from src.gui.workers.audio_worker import PreSynthesisWorker
    w = PreSynthesisWorker(
        text="Olá mundo. Isto é um teste de síntese.",
        key=(1, 2, "voz"), cache=PreSynthesisCache(), router=_fake_router())
    segs = w._synthesize()
    assert segs and all("audio_data" in s and "sample_rate" in s for s in segs)
    assert segs[0]["channels"] == 1 and segs[0]["dtype"] == "int16"


def test_presynth_worker_run_stores_and_emits(qtbot):
    from src.gui.workers.audio_worker import PreSynthesisWorker
    cache = PreSynthesisCache()
    key = (1, 2, "voz")
    w = PreSynthesisWorker(text="Texto qualquer.", key=key, cache=cache,
                           router=_fake_router())
    ready = []
    w.ready.connect(ready.append)
    w.run()
    assert cache.has(key)
    assert ready == [key]


def test_presynth_worker_skips_pyttsx3(qtbot):
    from src.gui.workers.audio_worker import PreSynthesisWorker
    w = PreSynthesisWorker(text="Texto.", key=(1, 2, "voz"),
                           cache=PreSynthesisCache(), router=_fake_router("pyttsx3"))
    assert w._synthesize() == []  # pyttsx3 não gera audio_data


def test_presynth_worker_no_router_is_noop(qtbot):
    from src.gui.workers.audio_worker import PreSynthesisWorker
    w = PreSynthesisWorker(text="Texto.", key=(1, 2, "voz"),
                           cache=PreSynthesisCache(), router=None)
    assert w._synthesize() == []


def test_presynth_worker_cancel_before_store(qtbot):
    from src.gui.workers.audio_worker import PreSynthesisWorker
    cache = PreSynthesisCache()
    w = PreSynthesisWorker(text="Texto.", key=(1, 2, "voz"), cache=cache,
                           router=_fake_router())
    w.cancel()
    w.run()
    assert cache.pending_key is None  # cancelado → não guarda


# ── AudioWorker em modo "prepared" (player falso, sem áudio real) ──────

class _FakePlayer:
    def __init__(self, *a, **k):
        self.enqueued = []
        self.stopped = False
        self.paused = False
        self.resumed = False
        self.waited = False

    def start(self):
        pass

    def enqueue(self, audio, sample_rate, channels=1, dtype="float32"):
        self.enqueued.append((audio, sample_rate, channels, dtype))

    def wait_until_done(self):
        self.waited = True

    def stop(self):
        self.stopped = True

    def pause(self):
        self.paused = True

    def resume(self):
        self.resumed = True


def test_audioworker_prepared_plays_cached_segments(qtbot, monkeypatch):
    import src.core.audio.continuous_player as cp
    from src.gui.workers.audio_worker import AudioWorker

    fake = _FakePlayer()
    monkeypatch.setattr(cp, "ContinuousAudioPlayer", lambda *a, **k: fake)

    segs = [
        {"audio_data": b"a", "sample_rate": 24000, "channels": 1, "dtype": "int16"},
        {"audio_data": b"b", "sample_rate": 24000, "channels": 1, "dtype": "int16"},
    ]
    w = AudioWorker("", prepared=segs)
    finished = []
    w.playback_finished.connect(finished.append)
    w.run()  # entra no ramo prepared, sem re-sintetizar
    assert len(fake.enqueued) == 2
    assert finished == [2]
    assert fake.waited and fake.stopped


def test_audioworker_prepared_pause_resume_stop_delegate(qtbot):
    from src.gui.workers.audio_worker import AudioWorker
    w = AudioWorker("", prepared=[{"audio_data": b"a", "sample_rate": 24000}])
    fake = _FakePlayer()
    w._prepared_player = fake
    w.pause()
    w.resume()
    w.stop()
    assert fake.paused and fake.resumed and fake.stopped


# ── Fiação no reader_view.py (checagem estática) ──────────────────────

_READER_VIEW = (Path(__file__).resolve().parent.parent
                / "src" / "gui" / "reader_view.py").read_text(encoding="utf-8")


def test_reader_initializes_presynth_cache():
    assert "self._presynth_cache = PreSynthesisCache()" in _READER_VIEW


def test_reader_kicks_presynth_on_audio_start():
    assert "self._maybe_presynthesize_next()" in _READER_VIEW


def test_reader_continue_consumes_cache_before_go_to_page():
    body = _READER_VIEW.split("def _continue_narration")[1].split("\n    def ")[0]
    take_idx = body.index("self._presynth_cache.take(")
    go_idx = body.index("self._go_to_page(next_page)")
    assert take_idx < go_idx  # pega o áudio ANTES de invalidar
    assert "self._play_prepared(prepared)" in body
    assert "next_readable_page_with_text" in body


def test_reader_invalidates_on_manual_nav_and_stop():
    for method in ("_go_next", "_go_prev", "_stop_audio_if_running"):
        body = _READER_VIEW.split(f"def {method}")[1].split("\n    def ")[0]
        assert "self._invalidate_presynth()" in body, method


def test_audio_worker_has_prepared_mode_and_presynth_worker():
    src = (Path(__file__).resolve().parent.parent
           / "src" / "gui" / "workers" / "audio_worker.py").read_text(encoding="utf-8")
    assert "def _run_prepared" in src
    assert "class PreSynthesisWorker" in src
    assert "prepared: list | None = None" in src


# ── Item C: zoom/tipografia re-renderizam SEM parar o áudio ───────────

def test_go_to_page_can_preserve_audio_on_same_page_rerender():
    body = _READER_VIEW.split("def _go_to_page")[1].split("\n    def ")[0]
    assert "preserve_audio" in body
    # o stop só acontece quando NÃO se pede para preservar (navegação real)
    assert "if not preserve_audio:" in body
    assert "self._stop_audio_if_running()" in body


def test_zoom_rerender_preserves_audio():
    for method in ("_zoom_in", "_zoom_out"):
        body = _READER_VIEW.split(f"def {method}")[1].split("\n    def ")[0]
        assert "preserve_audio=True" in body, method


def test_typography_rerender_preserves_audio():
    body = _READER_VIEW.split("def _apply_reader_typography")[1].split("\n    def ")[0]
    assert "preserve_audio=True" in body


# ── Item E: feedback imediato na narração traduzida ───────────────────

def test_translated_narration_shows_immediate_feedback():
    assert "_begin_translation_feedback" in _READER_VIEW
    toggle = _READER_VIEW.split("def _toggle_audio")[1].split("\n    def ")[0]
    assert "_begin_translation_feedback()" in toggle
    read_tr = _READER_VIEW.split("def _on_read_translated_page")[1].split("\n    def ")[0]
    assert "_begin_translation_feedback()" in read_tr


def test_audio_start_clears_translation_feedback():
    started = _READER_VIEW.split("def _on_audio_started")[1].split("\n    def ")[0]
    assert "self._translating_for_audio = False" in started
