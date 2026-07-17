"""Consistência voz configurada × idioma explícito do texto (caso real 2026-07-17).

Sintoma: em leitura TRADUZIDA (language="pt" explícito), o usuário escolheu uma
voz INGLESA no menu ("trocar para leitura em inglês") — o perfil é pt-BR, então
a checagem de mismatch por PERFIL não disparava e a tradução portuguesa saía na
voz inglesa ("anglicado"). Com idioma explícito, a voz CONFIGURADA só vale se
for do idioma do texto; senão o router resolve pelo idioma do texto.

Player de áudio FAKE obrigatório: no CI Linux não há dispositivo e o enqueue
real aborta a narração após o 1º chunk (lição do PR #34).
"""
from typing import Optional

import pytest

from src.core.tts.base_tts_provider import BaseTTSProvider, SynthesisResult, VoiceInfo
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.tts_router import TTSRouter


TEXTO_PT = "Ele disse que não era para todos os alunos da turma inteira."


class _FakePlayer:
    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def enqueue(self, *args, **kwargs):
        pass

    def wait_until_done(self):
        pass

    def stop(self):
        pass

    def pause(self):
        pass

    def resume(self):
        pass


@pytest.fixture(autouse=True)
def _fake_audio_player(monkeypatch):
    import src.core.audio.continuous_player as cp
    monkeypatch.setattr(cp, "ContinuousAudioPlayer", _FakePlayer)


class _Bilingual(BaseTTSProvider):
    def __init__(self, name="Kokoro", tier="B"):
        self._name = name
        self._tier = tier
        self.calls: list[tuple] = []
        self.is_ready = True

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
        self.calls.append((voice_id, text))

    def stop(self) -> None:
        pass

    def available_voices(self):
        return [
            VoiceInfo("pf_dora", "Dora", "pt-BR", "female", "", ["serene"]),
            VoiceInfo("af_heart", "Heart", "en-US", "female", "", ["serene"]),
        ]


def _router(provider, voice_id=None):
    router = TTSRouter()
    router.register_provider(provider)
    router.set_book_profile(VoiceProfile(
        role=NarrationRole.BOOK_NARRATOR, preferred_provider=provider.name.lower(),
        language="pt-BR", style="serene", voice_id=voice_id))
    return router


def test_voz_inglesa_configurada_nao_le_traducao_pt(qtbot=None):
    """O caso reportado: voz EN no perfil + tradução PT → voz PT, não a EN."""
    prov = _Bilingual()
    router = _router(prov, voice_id="af_heart")
    router.speak(TEXTO_PT, language="pt-BR")
    voices = {v for v, _ in prov.calls}
    assert "af_heart" not in voices
    assert voices == {"pf_dora"}


def test_voz_configurada_do_mesmo_idioma_e_respeitada():
    prov = _Bilingual()
    router = _router(prov, voice_id="pf_dora")
    router.speak(TEXTO_PT, language="pt-BR")
    assert {v for v, _ in prov.calls} == {"pf_dora"}


def test_voz_desconhecida_do_provider_e_mantida():
    """Voz fora da lista do provider → sem afirmação de mismatch (ADR-005)."""
    prov = _Bilingual()
    router = _router(prov, voice_id="voz_customizada_x")
    router.speak(TEXTO_PT, language="pt-BR")
    assert {v for v, _ in prov.calls} == {"voz_customizada_x"}


def test_sem_idioma_explicito_comportamento_inalterado():
    """language=None (autodetecção/segmentação) não força re-resolução."""
    prov = _Bilingual()
    router = _router(prov, voice_id="pf_dora")
    router.speak(TEXTO_PT)  # PT puro → 1 run → voz configurada
    assert {v for v, _ in prov.calls} == {"pf_dora"}
