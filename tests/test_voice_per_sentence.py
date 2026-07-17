"""Tarefa A (item 6) — o TTSRouter troca a voz por SENTENÇA em texto misto.

Providers falsos (TTS mockado, offline): registram cada chamada de síntese como
``(voice_id, texto)``. Fixamos:
  * texto misto PT/EN SEM idioma explícito → cada run é sintetizado com a voz do
    seu idioma (PT→voz PT, EN→voz EN) e enfileirado no mesmo player;
  * texto de idioma único → caminho atual inalterado (uma voz só);
  * idioma EXPLÍCITO (fluxo traduzido) → single-language intocado (uma voz só),
    mesmo com sentenças de outro idioma no meio;
  * degradação graciosa: provider sem voz no idioma do run herda a voz anterior;
  * a pré-síntese (PreSynthesisWorker) espelha a mesma segmentação/vozes.
"""
from typing import Optional

from src.core.tts.base_tts_provider import BaseTTSProvider, SynthesisResult, VoiceInfo
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.tts_router import TTSRouter


PT_EN_MIXED = (
    "Ele disse que não era para todos. "
    "The book is on the table and it is good. "
    "Então ela foi embora daqui."
)
PT_ONLY = "Ele disse que não era para todos os alunos da turma inteira."


class _RecordingBilingual(BaseTTSProvider):
    """Provider falso com vozes PT e EN que registra (voice_id, texto)."""

    def __init__(self, name="Kokoro", tier="B"):
        self._name = name
        self._tier = tier
        self.calls: list[tuple] = []
        self.is_ready = True  # evita o caminho de warmup do Kokoro no router

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> str:
        return self._tier

    def synthesize(self, text, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        self.calls.append((voice_id, text))
        return SynthesisResult(audio_data=b"\x00" * 8, sample_rate=24000,
                               provider_name=self._name)

    def speak_blocking(self, text, voice_id=None, rate=1.0, volume=1.0) -> None:
        pass

    def stop(self) -> None:
        pass

    def available_voices(self):
        return [
            VoiceInfo("pf_dora", "Dora", "pt-BR", "female", "", ["serene"]),
            VoiceInfo("af_heart", "Heart", "en-US", "female", "", ["serene"]),
        ]


class _RecordingMono(_RecordingBilingual):
    """Reserva/provider que só tem voz EN (sem voz PT)."""

    def available_voices(self):
        return [VoiceInfo("en_only", "Lessac", "en-US", "female", "", ["serene"])]


def _router(provider):
    router = TTSRouter()
    router.register_provider(provider)
    router.set_book_profile(VoiceProfile(
        role=NarrationRole.BOOK_NARRATOR, preferred_provider=provider.name.lower(),
        language="pt-BR", style="serene"))
    return router


# ── Multi-run: voz por sentença ────────────────────────────────────────

def test_mixed_text_uses_per_sentence_voices():
    prov = _RecordingBilingual("Kokoro", "B")
    router = _router(prov)
    router.speak(PT_EN_MIXED)  # sem idioma explícito → dispara a segmentação

    voices_used = [v for v, _ in prov.calls]
    assert "pf_dora" in voices_used  # sentenças PT → voz PT
    assert "af_heart" in voices_used  # sentença EN → voz EN
    # A sentença inglesa foi lida com a voz inglesa (e não com a PT).
    en_calls = [t for v, t in prov.calls if v == "af_heart"]
    assert any("book" in t.lower() for t in en_calls)


def test_single_language_uses_one_voice():
    prov = _RecordingBilingual("Kokoro", "B")
    router = _router(prov)
    router.speak(PT_ONLY)  # PT puro → 1 run → caminho atual inalterado
    assert {v for v, _ in prov.calls} == {"pf_dora"}


def test_explicit_language_stays_single_voice():
    """Fluxo traduzido: idioma fixado → single-language, mesmo com trecho EN."""
    prov = _RecordingBilingual("Kokoro", "B")
    router = _router(prov)
    router.speak(PT_EN_MIXED, language="pt-BR")
    assert {v for v, _ in prov.calls} == {"pf_dora"}  # tudo na voz PT


def test_graceful_fallback_when_run_language_lacks_voice():
    """Provider sem voz PT: o run PT herda a voz disponível (não aborta)."""
    prov = _RecordingMono("Kokoro", "B")
    router = _router(prov)
    router.speak(PT_EN_MIXED)  # multi-run, mas só há voz EN
    # Todos os 3 runs foram sintetizados, sem abortar. O run EN usa a voz EN; os
    # runs PT herdam a voz anterior/perfil (None = voz interna do motor) já que
    # não há voz PT — degradação graciosa (ADR-005), nunca um erro.
    assert len(prov.calls) >= 3
    assert "en_only" in {v for v, _ in prov.calls}


# ── Pré-síntese espelha a segmentação/vozes ────────────────────────────

def test_presynthesis_mirrors_per_sentence_voices(qtbot):
    from src.core.audio.continuous_player import PreSynthesisCache
    from src.gui.workers.audio_worker import PreSynthesisWorker

    prov = _RecordingBilingual("Kokoro", "B")
    router = _router(prov)
    worker = PreSynthesisWorker(
        text=PT_EN_MIXED, key=(1, 2, "voz"), cache=PreSynthesisCache(),
        router=router, language=None)
    segments = worker._synthesize()

    assert segments  # sintetizou algo
    voices_used = {v for v, _ in prov.calls}
    assert voices_used == {"pf_dora", "af_heart"}  # mesmas vozes por run
