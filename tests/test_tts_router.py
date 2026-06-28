"""
Tests for the Phase 13 TTS Router.

Validates:
- Provider registration and selection
- Tiered fallback chain
- Voice profile routing (book narrator vs assistant)
- Text preprocessing integration
- Graceful degradation on failure
- Provider health checks
"""

import pytest
from unittest.mock import MagicMock, patch
from typing import Optional

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    SynthesisResult,
    TTSCapability,
    TTSProviderError,
    VoiceInfo,
)
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.tts_router import TTSRouter
from src.core.tts.text_preprocessor import TTSTextPreprocessor


# ── Fake Providers for Testing ───────────────────────────────────────

class FakeProvider(BaseTTSProvider):
    """Configurable fake TTS provider for testing."""

    def __init__(self, provider_name: str = "FakeProvider",
                 provider_tier: str = "B", healthy: bool = True,
                 fail_on_speak: bool = False):
        self._name = provider_name
        self._tier = provider_tier
        self._healthy = healthy
        self._fail_on_speak = fail_on_speak
        self.spoken_texts: list[str] = []
        self.stop_called = False
        self.is_ready = True

    @property
    def name(self) -> str:
        return self._name

    @property
    def tier(self) -> str:
        return self._tier

    def synthesize(self, text: str, voice_id: Optional[str] = None,
                   rate: float = 1.0, volume: float = 1.0) -> SynthesisResult:
        if self._fail_on_speak:
            return SynthesisResult(error=f"{self.name} speak failed", provider_name=self.name)
        self.spoken_texts.append(text)
        return SynthesisResult(audio_data=b"fake" + b"\x00" * 44, sample_rate=24000, format="wav", provider_name=self.name)

    def speak_blocking(self, text: str, voice_id: Optional[str] = None,
                       rate: float = 1.0, volume: float = 1.0) -> None:
        if self._fail_on_speak:
            raise TTSProviderError(f"{self.name} speak failed")
        self.spoken_texts.append(text)

    def stop(self) -> None:
        self.stop_called = True

    def health_check(self) -> bool:
        return self._healthy


# ── Registration & Selection ─────────────────────────────────────────

class TestProviderRegistration:
    def test_register_provider(self):
        router = TTSRouter()
        provider = FakeProvider("TestProv", "B")
        router.register_provider(provider)
        providers = router.get_available_providers()
        assert len(providers) == 1
        assert providers[0]["name"] == "testprov"

    def test_unregister_provider(self):
        router = TTSRouter()
        provider = FakeProvider("TestProv", "B")
        router.register_provider(provider)
        router.unregister_provider("TestProv")
        assert len(router.get_available_providers()) == 0

    def test_register_multiple_providers(self):
        router = TTSRouter()
        router.register_provider(FakeProvider("Alpha", "A"))
        router.register_provider(FakeProvider("Beta", "B"))
        router.register_provider(FakeProvider("Charlie", "C"))
        assert len(router.get_available_providers()) == 3

    def test_auto_register_tolerates_broken_optional_provider(self):
        """ADR-005: um provider opcional cuja dependência está quebrada
        (ex.: torch com DLL inválida → OSError no construtor) NÃO pode
        derrubar o registro nem o startup do aplicativo."""
        router = TTSRouter(TTSTextPreprocessor())

        class _BrokenProvider:
            def __init__(self, *args, **kwargs):
                raise OSError("[WinError 193] %1 não é um aplicativo Win32 válido")

        # Sem o fix, o OSError (não-ImportError) propagaria e abortaria o startup.
        with patch("src.core.tts.qwen3_tts_provider.Qwen3TTSProvider", _BrokenProvider):
            router.auto_register_providers()  # não deve levantar exceção

        # O provider quebrado foi ignorado graciosamente.
        assert "qwen3-tts" not in router._providers


# ── Tiered Fallback ──────────────────────────────────────────────────

class TestTieredFallback:
    def test_prefers_requested_provider(self):
        router = TTSRouter()
        kokoro = FakeProvider("Kokoro", "B")
        piper = FakeProvider("Piper", "C")
        router.register_provider(kokoro)
        router.register_provider(piper)

        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="kokoro",
        )
        router.set_book_profile(profile)
        router.speak("Test text")
        assert len(kokoro.spoken_texts) > 0
        assert len(piper.spoken_texts) == 0

    def test_speak_language_override_reaches_voice_resolution(self):
        """O override de idioma em speak() deve chegar ao _resolve_voice.

        Garante que narrar texto em inglês resolva uma voz em inglês, em vez de
        usar sempre o idioma do perfil (pt-BR).
        """
        router = TTSRouter()
        piper = FakeProvider("Piper", "C")
        router.register_provider(piper)
        router.set_book_profile(
            VoiceProfile(role=NarrationRole.BOOK_NARRATOR, preferred_provider="piper")
        )
        captured = {}
        original = router._resolve_voice

        def spy(provider, language, style):
            captured["language"] = language
            return original(provider, language, style)

        router._resolve_voice = spy
        router.speak("texto qualquer", language="en-US")
        assert captured.get("language") == "en-US"

    def test_falls_back_when_preferred_unhealthy(self):
        router = TTSRouter()
        kokoro = FakeProvider("Kokoro", "B", healthy=False)
        piper = FakeProvider("Piper", "C", healthy=True)
        router.register_provider(kokoro)
        router.register_provider(piper)

        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="kokoro",
        )
        router.set_book_profile(profile)
        router.speak("Test text")
        assert len(kokoro.spoken_texts) == 0
        assert len(piper.spoken_texts) > 0

    def test_mid_stream_fallback(self):
        router = TTSRouter()
        # First provider fails during speak
        kokoro = FakeProvider("Kokoro", "B", fail_on_speak=True)
        piper = FakeProvider("Piper", "C")
        router.register_provider(kokoro)
        router.register_provider(piper)

        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="kokoro",
        )
        router.set_book_profile(profile)
        count = router.speak("Short text.")
        # Should have fallen back to piper
        assert len(piper.spoken_texts) > 0

    def test_no_provider_returns_zero(self):
        router = TTSRouter()
        with pytest.raises(TTSProviderError):
            router.speak("Test text")

    def test_all_unhealthy_returns_zero(self):
        router = TTSRouter()
        router.register_provider(FakeProvider("A", "A", healthy=False))
        router.register_provider(FakeProvider("B", "B", healthy=False))
        with pytest.raises(TTSProviderError):
            router.speak("Test text")


# ── Voice Profiles ───────────────────────────────────────────────────

class TestVoiceProfiles:
    def test_book_narrator_default(self):
        router = TTSRouter()
        profile = router.get_book_profile()
        assert profile.role == NarrationRole.BOOK_NARRATOR
        assert profile.style == "serene"

    def test_assistant_default(self):
        router = TTSRouter()
        profile = router.get_assistant_profile()
        assert profile.role == NarrationRole.ASSISTANT
        assert profile.style == "didactic"

    def test_set_custom_book_profile(self):
        router = TTSRouter()
        custom = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="piper",
            style="technical",
            rate=1.2,
        )
        router.set_book_profile(custom)
        assert router.get_book_profile().preferred_provider == "piper"
        assert router.get_book_profile().style == "technical"

    def test_different_providers_for_narrator_and_assistant(self):
        router = TTSRouter()
        prov_a = FakeProvider("ProvA", "B")
        prov_b = FakeProvider("ProvB", "C")
        router.register_provider(prov_a)
        router.register_provider(prov_b)

        router.set_book_profile(VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="prova",
        ))
        router.set_assistant_profile(VoiceProfile(
            role=NarrationRole.ASSISTANT,
            preferred_provider="provb",
        ))

        router.speak("Book text", role=NarrationRole.BOOK_NARRATOR)
        router.speak("Assistant text", role=NarrationRole.ASSISTANT)

        assert len(prov_a.spoken_texts) > 0
        assert len(prov_b.spoken_texts) > 0


# ── Text Preprocessing Integration ───────────────────────────────────

class TestPreprocessingIntegration:
    def test_preprocessing_is_applied_by_default(self):
        router = TTSRouter()
        provider = FakeProvider("Test", "B")
        router.register_provider(provider)

        # Text with abbreviation that should be expanded
        router.speak("Dr. Silva chegou.")
        assert len(provider.spoken_texts) > 0
        # The spoken text should have expanded abbreviation
        assert "Doutor" in provider.spoken_texts[0]

    def test_preprocessing_can_be_disabled(self):
        router = TTSRouter()
        provider = FakeProvider("Test", "B")
        router.register_provider(provider)

        router.speak("Dr. Silva chegou.", preprocess=False)
        assert len(provider.spoken_texts) > 0
        assert "Dr." in provider.spoken_texts[0]


# ── Stop & Lifecycle ─────────────────────────────────────────────────

class TestStopAndLifecycle:
    def test_stop_delegates_to_active_provider(self):
        router = TTSRouter()
        provider = FakeProvider("Test", "B")
        router.register_provider(provider)
        router._active_provider = provider
        router.stop()
        assert provider.stop_called

    def test_shutdown_clears_providers(self):
        router = TTSRouter()
        router.register_provider(FakeProvider("A", "A"))
        router.register_provider(FakeProvider("B", "B"))
        router.shutdown()
        assert len(router.get_available_providers()) == 0

    def test_empty_text_returns_zero(self):
        router = TTSRouter()
        router.register_provider(FakeProvider("Test", "B"))
        assert router.speak("") == 0
        assert router.speak("   ") == 0


# ── Voice Profile Serialization ──────────────────────────────────────

class TestVoiceProfileSerialization:
    def test_to_dict(self):
        profile = VoiceProfile.default_book_narrator()
        d = profile.to_dict()
        assert d["role"] == "book_narrator"
        assert d["preferred_provider"] == "kokoro"
        assert d["style"] == "serene"

    def test_from_dict(self):
        data = {
            "role": "assistant",
            "preferred_provider": "piper",
            "style": "didactic",
            "rate": 1.1,
        }
        profile = VoiceProfile.from_dict(data)
        assert profile.role == NarrationRole.ASSISTANT
        assert profile.preferred_provider == "piper"
        assert profile.rate == 1.1

    def test_roundtrip(self):
        original = VoiceProfile.default_assistant()
        restored = VoiceProfile.from_dict(original.to_dict())
        assert restored.role == original.role
        assert restored.preferred_provider == original.preferred_provider
        assert restored.style == original.style
        assert restored.rate == original.rate

    def test_from_dict_invalid_role_defaults_to_narrator(self):
        data = {"role": "INVALID_ROLE"}
        profile = VoiceProfile.from_dict(data)
        assert profile.role == NarrationRole.BOOK_NARRATOR


# ── Provider Listing ─────────────────────────────────────────────────

class TestProviderListing:
    def test_get_available_providers_with_status(self):
        router = TTSRouter()
        router.register_provider(FakeProvider("Healthy", "A", healthy=True))
        router.register_provider(FakeProvider("Sick", "C", healthy=False))

        providers = router.get_available_providers()
        assert len(providers) == 2

        healthy = [p for p in providers if p["healthy"]]
        sick = [p for p in providers if not p["healthy"]]
        assert len(healthy) == 1
        assert len(sick) == 1

    def test_active_provider_name_default(self):
        router = TTSRouter()
        assert router.get_active_provider_name() == "none"


# ── Voice Resolution ─────────────────────────────────────────────────

class TestVoiceResolution:
    def test_resolves_voice_by_language_and_style(self):
        router = TTSRouter()
        provider = FakeProvider("Test", "B")

        # Mock available_voices on the provider
        provider.available_voices = MagicMock(return_value=[
            VoiceInfo("pf_dora", "Dora", "pt-BR", "female", "desc", ["serene"]),
            VoiceInfo("pm_santa", "Santa", "pt-BR", "male", "desc", ["didactic"]),
            VoiceInfo("af_heart", "Heart", "en-US", "female", "desc", ["serene"]),
        ])

        # Test Portuguese Serene
        v1 = router._resolve_voice(provider, "pt-BR", "serene")
        assert v1 == "pf_dora"

        # Test Portuguese Didactic
        v2 = router._resolve_voice(provider, "pt-BR", "didactic")
        assert v2 == "pm_santa"

        # Test English Serene
        v3 = router._resolve_voice(provider, "en-US", "serene")
        assert v3 == "af_heart"

        # Test fallback when style doesn't match
        v4 = router._resolve_voice(provider, "pt-BR", "nonexistent")
        assert v4 == "pf_dora"  # Default to first matching language candidate


class TestRouterReadinessFallback:
    def test_kokoro_not_ready_falls_back_to_piper(self):
        import threading
        router = TTSRouter()
        
        # Create a fake Kokoro provider that is NOT ready
        kokoro = FakeProvider("Kokoro", "B")
        kokoro.is_ready = False
        # Setup _warmup_event that will timeout
        kokoro._warmup_event = threading.Event()
        
        # Create a healthy Piper fallback provider
        piper = FakeProvider("Piper", "C")
        
        router.register_provider(kokoro)
        router.register_provider(piper)
        
        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="kokoro",
        )
        router.set_book_profile(profile)
        
        # Patch wait to return immediately (simulating timeout)
        with patch.object(kokoro._warmup_event, 'wait', return_value=False) as mock_wait:
            router.speak("Test text.")
            assert mock_wait.called
            # Verify it fell back to Piper
            assert len(piper.spoken_texts) > 0
            assert len(kokoro.spoken_texts) == 0


class TestAdaptiveChunking:
    def test_adaptive_chunking_high_latency(self):
        router = TTSRouter()
        # High latency provider
        provider = FakeProvider("SlowProvider", "B")
        provider.latency_profile = MagicMock(return_value="high")
        router.register_provider(provider)

        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="slowprovider",
        )
        router.set_book_profile(profile)

        long_sentence = "Esta e uma frase bem longa projetada para testar o comportamento de chunking adaptativo. " * 3
        router.speak(long_sentence)
        
        # If chunking was 200, it should split.
        assert len(provider.spoken_texts) > 1
        
    def test_adaptive_chunking_normal_latency(self):
        router = TTSRouter()
        # Normal latency provider
        provider = FakeProvider("FastProvider", "B")
        provider.latency_profile = MagicMock(return_value="medium")
        router.register_provider(provider)

        profile = VoiceProfile(
            role=NarrationRole.BOOK_NARRATOR,
            preferred_provider="fastprovider",
        )
        router.set_book_profile(profile)

        long_sentence = "Esta e uma frase bem longa projetada para testar o comportamento de chunking adaptativo. " * 3
        router.speak(long_sentence)
        
        # If normal (max_chars = 800), it should NOT split (1 chunk).
        assert len(provider.spoken_texts) == 1

