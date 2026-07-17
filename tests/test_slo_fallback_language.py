"""Rodada 3 de ajustes de TTS — Tarefa B: o fallback por violação do SLO de
TTFB no meio da narração só troca de motor se o reserva puder falar o idioma.

Furos fechados (ver prompt do executor):
  (1) ``_resolve_voice`` (pós-rodada 2) devolvia ``None`` quando o reserva não
      tinha voz no idioma → o Piper lia PT com o modelo default EN ("anglicado").
  (2) o re-início pós-fallback abortava a narração no meio quando a checagem
      honesta de idioma era atingida.

Correção: ``TTSRouter._mid_stream_fallback`` decide a troca ANTES de trocar —
só devolve um reserva quando ele tem voz no idioma efetivo (ou o idioma não é
explícito). Caso contrário devolve ``(None, None)`` e quem chama CONTINUA com o
provider atual (lento porém com áudio correto).

Testes unitários e rápidos (TTS mockado, offline): exercitam diretamente a
decisão do helper e checam estaticamente que ambos os caminhos do SLO (streaming
e não-streaming) passam por ele.
"""
import inspect
from typing import Optional

from src.core.tts.base_tts_provider import BaseTTSProvider, SynthesisResult, VoiceInfo
from src.core.tts.tts_router import TTSRouter
from src.core.tts.voice_profile import VoiceProfile, NarrationRole


class _BilingualProvider(BaseTTSProvider):
    """Provider falso com vozes PT e EN (síntese instantânea)."""

    def __init__(self, name="Kokoro", tier="B"):
        self._name = name
        self._tier = tier

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> str:
        return self._tier

    def synthesize(self, text, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
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


class _EnglishOnlyProvider(_BilingualProvider):
    """Reserva que só tem voz EN (caso real: Piper só com o modelo en)."""

    def available_voices(self):
        return [VoiceInfo("en_US-lessac-medium", "Lessac", "en-US", "female", "", ["serene"])]


def _router(current, fallback):
    router = TTSRouter()
    router.register_provider(current)
    router.register_provider(fallback)
    return router


# ── Decisão do fallback mid-stream (idioma explícito) ──────────────────

def test_no_switch_when_fallback_lacks_target_language():
    """Reserva sem voz PT + idioma PT explícito → NÃO troca (mantém o atual)."""
    kokoro = _BilingualProvider("Kokoro", "B")
    piper = _EnglishOnlyProvider("Piper", "C")
    router = _router(kokoro, piper)

    fb, voice = router._mid_stream_fallback(kokoro, "pt-BR", "serene",
                                            language_explicit=True)
    assert fb is None
    assert voice is None


def test_switch_with_correct_voice_when_fallback_has_language():
    """Reserva COM voz PT + idioma PT explícito → troca com a voz PT (não None)."""
    kokoro = _BilingualProvider("Kokoro", "B")
    piper = _BilingualProvider("Piper", "C")
    router = _router(kokoro, piper)

    fb, voice = router._mid_stream_fallback(kokoro, "pt-BR", "serene",
                                            language_explicit=True)
    assert fb is piper
    assert voice == "pf_dora"  # voz PT resolvida — nunca None tendo voz no idioma


def test_switch_resolves_english_voice_for_english_page():
    kokoro = _BilingualProvider("Kokoro", "B")
    piper = _BilingualProvider("Piper", "C")
    router = _router(kokoro, piper)

    fb, voice = router._mid_stream_fallback(kokoro, "en-US", "serene",
                                            language_explicit=True)
    assert fb is piper
    assert voice == "af_heart"


# ── Sem idioma explícito: comportamento antigo preservado ──────────────

def test_switch_when_language_not_explicit_even_without_language_voice():
    """Sem override de idioma, a decisão de idioma não barra a troca (o motor
    de reserva usa sua voz interna)."""
    kokoro = _BilingualProvider("Kokoro", "B")
    piper = _EnglishOnlyProvider("Piper", "C")
    router = _router(kokoro, piper)

    fb, voice = router._mid_stream_fallback(kokoro, "pt-BR", "serene",
                                            language_explicit=False)
    assert fb is piper  # troca ocorre (comportamento antigo)
    assert voice is None  # sem voz PT → provider usa a interna


# ── Sem reserva registrado ─────────────────────────────────────────────

def test_no_fallback_registered_returns_none():
    kokoro = _BilingualProvider("Kokoro", "B")
    router = TTSRouter()
    router.register_provider(kokoro)  # só o atual

    fb, voice = router._mid_stream_fallback(kokoro, "pt-BR", "serene",
                                            language_explicit=True)
    assert fb is None
    assert voice is None


# ── Fiação estática: ambos os caminhos do SLO usam o helper ────────────

def test_both_slo_paths_use_mid_stream_fallback():
    """Streaming e não-streaming devem passar pela decisão de idioma (o antigo
    _get_fallback_provider + _resolve_voice inline foi substituído)."""
    src = inspect.getsource(TTSRouter.speak)
    assert src.count("_mid_stream_fallback(") >= 2


# ── Débito da rodada 3 corrigido: resume pós-SLO no provider já trocado ─
#
# Antes: sob violação de SLO, o mecanismo levantava um TTSProviderError genérico
# capturado por um handler que RECOMPUTAVA _get_fallback_provider sobre o provider
# JÁ TROCADO por _mid_stream_fallback. Com Kokoro+Piper, isso não achava nada
# abaixo do Piper e dava break, PARANDO a reprodução justamente quando o reserva
# tinha a voz e a troca deveria funcionar. Agora a troca por SLO usa um sinal
# próprio (_SLOFallbackSwap) e o chunk é RE-sintetizado no provider já trocado.


class _RecordingBilingual(_BilingualProvider):
    """_BilingualProvider que registra cada síntese como (voice_id, texto)."""

    def __init__(self, name="Kokoro", tier="B"):
        super().__init__(name, tier)
        self.calls: list[tuple] = []
        self.is_ready = True  # evita o caminho de warmup do Kokoro no router

    def synthesize(self, text, voice_id=None, rate=1.0, volume=1.0):
        self.calls.append((voice_id, text))
        return super().synthesize(text, voice_id, rate, volume)


class _RecordingEnglishOnly(_EnglishOnlyProvider):
    """Reserva que só tem voz EN e registra as chamadas de síntese."""

    def __init__(self, name="Piper", tier="C"):
        super().__init__(name, tier)
        self.calls: list[tuple] = []
        self.is_ready = True

    def synthesize(self, text, voice_id=None, rate=1.0, volume=1.0):
        self.calls.append((voice_id, text))
        return super().synthesize(text, voice_id, rate, volume)


def _speak_router(kokoro, piper):
    router = TTSRouter()
    router.register_provider(kokoro)
    router.register_provider(piper)
    router.set_book_profile(VoiceProfile(
        role=NarrationRole.BOOK_NARRATOR, preferred_provider="kokoro",
        language="pt-BR", style="serene"))
    # SLO negativo: qualquer TTFB estoura no 1º chunk, sem sleeps reais.
    router._TTFB_SLO_SECONDS = -1.0
    return router


def test_slo_swap_resumes_on_fallback_that_has_voice():
    """SLO estoura + reserva TEM a voz PT → a reprodução CONTINUA no Piper (não
    para): o chunk corrente é RE-sintetizado no provider já trocado."""
    kokoro = _RecordingBilingual("Kokoro", "B")
    piper = _RecordingBilingual("Piper", "C")
    router = _speak_router(kokoro, piper)

    router.speak("Ele disse que não era para todos.", language="pt-BR")

    assert piper.calls, "Piper deveria ter retomado a síntese após o SLO"
    assert all(v == "pf_dora" for v, _ in piper.calls)  # voz PT correta


def test_slo_no_swap_keeps_current_when_fallback_lacks_language():
    """SLO estoura + reserva SEM voz no idioma explícito → continua no Kokoro
    (comportamento da rodada 3 preservado; nada de áudio 'anglicado')."""
    kokoro = _RecordingBilingual("Kokoro", "B")
    piper = _RecordingEnglishOnly("Piper", "C")
    router = _speak_router(kokoro, piper)

    router.speak("Ele disse que não era para todos.", language="pt-BR")

    assert piper.calls == []  # não trocou
    assert kokoro.calls and all(v == "pf_dora" for v, _ in kokoro.calls)
