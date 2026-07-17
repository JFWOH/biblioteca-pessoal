"""Item B: a narração deve usar o idioma do TEXTO para escolher a voz.

O bug: com uma voz PT-BR CONFIGURADA no perfil, uma página em inglês era lida
com a voz portuguesa (o ``voice_id`` fixo do perfil ignorava o idioma detectado).
Aqui garantimos que:
  * o AudioWorker detecta o idioma do texto (caminho do botão "Ouvir");
  * o TTSRouter resolve uma voz para o idioma do TEXTO mesmo quando há uma voz
    configurada, e a preserva quando o idioma bate.
"""
from typing import Optional

from src.core.tts.base_tts_provider import BaseTTSProvider, SynthesisResult, VoiceInfo
from src.core.tts.tts_router import TTSRouter
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.language_detect import detect_language


class _VoicedProvider(BaseTTSProvider):
    """Provider falso com vozes PT e EN (síntese instantânea, sem áudio real)."""

    def __init__(self, name="Piper", tier="C"):
        self._name = name
        self._tier = tier
        self.last_voice_id = "unset"

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> str:
        return self._tier

    def synthesize(self, text, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        self.last_voice_id = voice_id
        return SynthesisResult(audio_data=b"x" + b"\x00" * 44, sample_rate=24000,
                               provider_name=self._name)

    def speak_blocking(self, text, voice_id=None, rate=1.0, volume=1.0) -> None:
        self.last_voice_id = voice_id

    def stop(self) -> None:
        pass

    def available_voices(self):
        return [
            VoiceInfo("pf_dora", "Dora", "pt-BR", "female", "", ["serene"]),
            VoiceInfo("af_heart", "Heart", "en-US", "female", "", ["serene"]),
        ]


def _router_with_configured_pt_voice():
    router = TTSRouter()
    provider = _VoicedProvider("Piper", "C")
    router.register_provider(provider)
    router.set_book_profile(VoiceProfile(
        role=NarrationRole.BOOK_NARRATOR,
        preferred_provider="piper",
        voice_id="pf_dora",      # voz PT-BR escolhida pelo usuário (caso do bug)
        language="pt-BR",
    ))
    return router, provider


# ── Detecção no caminho do botão "Ouvir" (AudioWorker) ────────────────

def test_audio_worker_detects_english_text():
    from src.gui.workers.audio_worker import AudioWorker
    worker = AudioWorker("This is clearly an English sentence for testing.",
                         router=None, parent=None)
    assert worker._language == "en-US"


def test_audio_worker_detects_portuguese_text():
    from src.gui.workers.audio_worker import AudioWorker
    worker = AudioWorker("Isto é português com acentuação para os testes.",
                         router=None, parent=None)
    assert worker._language == "pt-BR"


def test_audio_worker_respects_explicit_language():
    from src.gui.workers.audio_worker import AudioWorker
    worker = AudioWorker("qualquer texto", language="en-US",
                         router=None, parent=None)
    assert worker._language == "en-US"


# ── Router honra o idioma do texto na resolução de voz ────────────────

def test_english_text_uses_english_voice_despite_configured_pt_voice():
    router, provider = _router_with_configured_pt_voice()
    router.speak("This is an English page about companionship.", language="en-US")
    # Resolveu uma voz de INGLÊS, não a PT-BR configurada.
    assert provider.last_voice_id == "af_heart"


def test_portuguese_text_keeps_configured_voice():
    router, provider = _router_with_configured_pt_voice()
    router.speak("Uma página em português com acentuação.", language="pt-BR")
    # Idioma bate com o perfil → mantém a voz escolhida pelo usuário.
    assert provider.last_voice_id == "pf_dora"


def test_no_language_override_keeps_configured_voice():
    router, provider = _router_with_configured_pt_voice()
    router.speak("Texto sem override de idioma.")  # language=None
    assert provider.last_voice_id == "pf_dora"


# ── Helper de idioma primário ─────────────────────────────────────────

def test_primary_language_helper():
    assert TTSRouter._primary_language("en-US") == "en"
    assert TTSRouter._primary_language("pt_BR") == "pt"
    assert TTSRouter._primary_language("pt") == "pt"
    assert TTSRouter._primary_language(None) == ""


def test_detect_language_matches_worker_default():
    # A detecção usada pelo worker é a mesma função pura.
    assert detect_language("The book was open on the table for everyone") == "en-US"
