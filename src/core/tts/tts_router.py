"""
TTS Router — Backend selection, capability detection, and fallback management.

Implements the tiered fallback hierarchy from the Phase 13 contract:
    Tier A → Qwen3-TTS (when supported and advantageous)
    Tier B → Kokoro (MVP default quality)
    Tier C → Piper (lightweight fallback)
    Tier D → Sherpa-ONNX / runtime alternative
    Legacy → pyttsx3 (ultimate fallback)

ADR-005 compliance: Graceful degradation, never crash.
ADR-006 compliance: No PyQt6 imports.
"""

import logging
import time
from typing import Optional

from src.core.tts.base_tts_provider import (
    BaseTTSProvider,
    TTSProviderError,
)
from src.core.tts.voice_profile import VoiceProfile, NarrationRole
from src.core.tts.text_preprocessor import TTSTextPreprocessor
from src.core.tts.language_detect import detect_language_confident
from src.core.tts.language_segments import split_language_runs

# Espera de prontidão do Kokoro no início da narração (caso real 2026-08-10:
# warmup concorrendo com OCR de PDF escaneado estourava os 3s e, sem Piper,
# o play falhava duro — com o motor a segundos de ficar pronto).
_READINESS_WAIT_FALLBACK_S = 3.0  # há reserva saudável: espera curta e cai p/ ela
_READINESS_WAIT_SOLO_S = 20.0     # sem reserva: esperar > falhar (cancelável)

logger = logging.getLogger(__name__)

# Tier ordering: highest quality first
TIER_ORDER = ["A", "B", "C", "D", "legacy"]


class _SLOFallbackSwap(Exception):
    """Sinal interno: o SLO de TTFB estourou e ``_mid_stream_fallback`` JÁ
    aplicou a troca de provider/voz no ``state``.

    NÃO é uma falha de síntese. Quem sintetiza deve RE-sintetizar o chunk
    corrente com o provider já trocado — sem recomputar ``_get_fallback_provider``
    nem parar a reprodução. (Débito da rodada 3: o handler genérico recomputava
    o fallback sobre o provider já trocado, não achava nada abaixo do Piper e
    dava ``break``, parando o áudio justamente quando o reserva TINHA a voz.)
    """


class TTSRouter:
    """Routes TTS requests to the best available provider with fallback.

    The router:
    1. Maintains a registry of available providers.
    2. Selects the best provider based on voice profile preferences.
    3. Falls back through tiers on failure.
    4. Applies text preprocessing before synthesis.
    5. Reports which provider was actually used.
    """

    # SLO de TTFB (segundos): se o 1º chunk demora mais que isto, tenta trocar
    # de motor (ver _mid_stream_fallback). Atributo de classe p/ os testes
    # ajustarem sem sleeps reais.
    _TTFB_SLO_SECONDS = 3.0

    def __init__(self, preprocessor: Optional[TTSTextPreprocessor] = None):
        self._providers: dict[str, BaseTTSProvider] = {}
        self._preprocessor = preprocessor or TTSTextPreprocessor()
        self._active_provider: Optional[BaseTTSProvider] = None
        # Player da reprodução em andamento. stop() precisa pará-lo diretamente:
        # senão, com o áudio já no buffer, wait_until_done() ignora _is_cancelled
        # e a página toca até o fim mesmo após o STOP.
        self._active_player = None
        self._book_profile = VoiceProfile.default_book_narrator()
        self._assistant_profile = VoiceProfile.default_assistant()
        self._initialized = False
        self._is_cancelled = False

    # ── Provider Registration ─────────────────────────────────────────

    def register_provider(self, provider: BaseTTSProvider) -> None:
        """Register a TTS provider. Safe to call multiple times."""
        name = provider.name.lower()
        self._providers[name] = provider
        logger.info("TTS_ROUTER: Registered provider '%s' (tier %s)", name, provider.tier)

    def unregister_provider(self, name: str) -> None:
        """Remove a provider from the registry."""
        name_lower = name.lower()
        if name_lower in self._providers:
            del self._providers[name_lower]
            logger.info("TTS_ROUTER: Unregistered provider '%s'", name_lower)

    # ── Profile Management ────────────────────────────────────────────

    def set_book_profile(self, profile: VoiceProfile) -> None:
        """Set the voice profile for book narration."""
        self._book_profile = profile
        logger.info("TTS_ROUTER: Book profile set to provider='%s', style='%s'",
                     profile.preferred_provider, profile.style)

    def set_assistant_profile(self, profile: VoiceProfile) -> None:
        """Set the voice profile for assistant narration."""
        self._assistant_profile = profile
        logger.info("TTS_ROUTER: Assistant profile set to provider='%s', style='%s'",
                     profile.preferred_provider, profile.style)

    def get_book_profile(self) -> VoiceProfile:
        return self._book_profile

    def get_assistant_profile(self) -> VoiceProfile:
        return self._assistant_profile

    # ── Initialization ────────────────────────────────────────────────

    def initialize(self) -> None:
        """Initialize all registered providers. Non-fatal on individual failures."""
        for name, provider in self._providers.items():
            try:
                provider.initialize()
                logger.info("TTS_ROUTER: Provider '%s' initialized", name)
            except Exception as e:
                logger.warning("TTS_ROUTER: Provider '%s' failed init: %s", name, e)
        self._initialized = True

    def auto_register_providers(self) -> None:
        """Attempt to auto-discover and register available providers.

        Tries each provider in tier order, skipping those whose
        dependencies are not installed.
        """
        # Tier B — Kokoro (MVP default)
        try:
            from src.core.tts.kokoro_provider import KokoroProvider
            self.register_provider(KokoroProvider())
        except Exception as e:
            logger.info("TTS_ROUTER: Kokoro not available: %s", e)

        # Tier C — Piper (fallback)
        try:
            from src.core.tts.piper_provider import PiperProvider
            self.register_provider(PiperProvider())
        except Exception as e:
            logger.info("TTS_ROUTER: Piper not available: %s", e)

        # Tier A — Qwen3-TTS (advanced optional)
        try:
            from src.core.tts.qwen3_tts_provider import Qwen3TTSProvider
            self.register_provider(Qwen3TTSProvider())
        except Exception as e:
            logger.info("TTS_ROUTER: Qwen3-TTS not available: %s", e)

        # Tier D — Sherpa-ONNX (runtime)
        try:
            from src.core.tts.sherpa_onnx_provider import SherpaOnnxProvider
            self.register_provider(SherpaOnnxProvider())
        except Exception as e:
            logger.info("TTS_ROUTER: Sherpa-ONNX not available: %s", e)

        # Legacy pyttsx3 is explicitly NOT registered automatically for this chunked/gapless pipeline.

    # ── Provider Selection ────────────────────────────────────────────

    def synthesize_segments(self, text: str, role: NarrationRole,
                            language: str | None = None,
                            cancel_check=None) -> list[dict]:
        """Sintetiza *text* SEM tocar — API pública da pré-síntese (débito 3.6).

        Retorna segmentos no formato que o ``AudioWorker(prepared=...)``
        consome (``audio_data``/``sample_rate``/``channels``/``dtype``),
        espelhando as decisões de voz do ``speak()``: detecção confiante
        quando ``language`` é ``None``, pré-processamento por estilo, voz do
        perfil (ou resolvida por idioma) e voz por SENTENÇA em texto misto.

        NÃO toca no estado de reprodução (``_is_cancelled``/``_active_player``)
        — é seguro rodar em PARALELO a um ``speak()`` em andamento (é o design
        da pré-síntese). Sem SLO/fallback-swap (comportamento histórico da
        pré-síntese, preservado). ``cancel_check``: chamável consultado entre
        chunks; verdadeiro → aborta e devolve ``[]``. Chunk que falha é pulado
        (ADR-005); provider ausente ou pyttsx3 (sem ``audio_data``) → ``[]``.
        """
        if not text or not text.strip():
            return []
        profile = (self.get_book_profile()
                   if role == NarrationRole.BOOK_NARRATOR
                   else self.get_assistant_profile())
        language = language or detect_language_confident(text)
        effective_language = language or profile.language

        try:
            processed = self._preprocessor.prepare_for_speech(
                text, style=profile.style)
        except Exception:
            processed = text
        if not processed or not processed.strip():
            return []

        provider = self._get_provider_for_profile(profile)
        # pyttsx3 não expõe audio_data — não dá para sintetizar sem tocar.
        if provider is None or provider.name.lower() == "pyttsx3":
            return []

        voice_id = profile.voice_id
        if not voice_id:
            try:
                voice_id = self._resolve_voice(
                    provider, effective_language, profile.style)
            except Exception:
                voice_id = None

        max_chars = 200 if provider.latency_profile() == "high" else 800

        # Voz por SENTENÇA (item 6): idioma não fixado E detecção ambígua →
        # cada run de idioma com a sua voz (mesma condição do multi-run do
        # speak). Um único run mantém o caminho simples (mesma voz).
        work: list[tuple] = []  # (voice_id, chunk)
        lang_runs = (split_language_runs(processed, profile.language)
                     if language is None else [])
        if len(lang_runs) > 1:
            prev_voice = voice_id
            for run_lang, run_text in lang_runs:
                try:
                    run_voice = self._resolve_voice(
                        provider, run_lang, profile.style)
                except Exception:
                    run_voice = None
                if run_voice is None:
                    run_voice = prev_voice  # degradação graciosa: herda a voz
                else:
                    prev_voice = run_voice
                for chunk in self._split_preprocessed_text(
                        run_text, max_chars=max_chars):
                    work.append((run_voice, chunk))
        else:
            for chunk in self._split_preprocessed_text(
                    processed, max_chars=max_chars):
                work.append((voice_id, chunk))

        segments: list[dict] = []
        for chunk_voice, chunk in work:
            if cancel_check is not None and cancel_check():
                return []
            if not chunk.strip():
                continue
            result = provider.synthesize(
                chunk, voice_id=chunk_voice, rate=profile.rate,
                volume=profile.volume)
            if not getattr(result, "success", False) or result.audio_data is None:
                continue
            segments.append({
                "audio_data": result.audio_data,
                "sample_rate": result.sample_rate,
                "channels": provider.channels,
                "dtype": provider.dtype,
            })
        return segments

    def _get_provider_for_profile(self, profile: VoiceProfile) -> Optional[BaseTTSProvider]:
        """Select the best provider for a given voice profile.

        Priority:
        1. Preferred provider from profile (if healthy).
        2. Fallback through tiers: A → B → C → D → legacy.
        """
        # 1. Try preferred provider
        preferred_name = profile.preferred_provider.lower()
        if preferred_name == "pyttsx3" and "pyttsx3" not in self._providers:
            try:
                from src.core.tts.pyttsx3_provider import Pyttsx3Provider
                self.register_provider(Pyttsx3Provider())
                logger.info("TTS_ROUTER: Registered legacy pyttsx3 provider on-demand.")
            except Exception as e:
                logger.warning("TTS_ROUTER: Failed to register pyttsx3 on-demand: %s", e)
        if preferred_name in self._providers:
            provider = self._providers[preferred_name]
            try:
                if provider.health_check():
                    return provider
            except Exception as e:
                logger.warning("TTS_ROUTER: Preferred provider '%s' unhealthy: %s",
                               preferred_name, e)

        # 2. Fallback through tiers (excluding pyttsx3/legacy)
        for tier in TIER_ORDER:
            if tier == "legacy":
                continue
            for name, provider in self._providers.items():
                if provider.tier == tier and name != preferred_name:
                    if name == "pyttsx3":
                        continue
                    try:
                        if provider.health_check():
                            logger.info("TTS_ROUTER: Falling back to '%s' (tier %s)",
                                        name, tier)
                            return provider
                    except Exception:
                        continue

        return None

    def get_active_provider_name(self) -> str:
        """Returns the name of the currently active provider, or 'none'."""
        if self._active_provider:
            return self._active_provider.name
        return "none"

    def get_available_providers(self) -> list[dict]:
        """List all registered providers with their status."""
        result = []
        for name, provider in self._providers.items():
            try:
                healthy = provider.health_check()
            except Exception:
                healthy = False
            result.append({
                "name": name,
                "tier": provider.tier,
                "healthy": healthy,
                "latency": provider.latency_profile(),
                "streaming": provider.supports_streaming(),
            })
        return result

    # ── Synthesis ─────────────────────────────────────────────────────

    def speak(self, text: str,
              role: NarrationRole = NarrationRole.BOOK_NARRATOR,
              preprocess: bool = True,
              language: Optional[str] = None) -> int:
        """Synthesize and play text with the appropriate voice profile.

        This is the main entry point for the GUI/AudioWorker layer.

        Args:
            text: Raw text to narrate.
            role: Whether this is book narration or assistant output.
            preprocess: Whether to apply text preprocessing.
            language: Optional language override (e.g. 'en-US') for voice
                resolution. When None, uses the profile's language. Lets the
                caller narrate English text with an English voice.

        Returns:
            Number of chunks successfully spoken.
        """
        logger.info("PLAY_REQUESTED: role=%s, text_length=%d, preprocess=%s", role, len(text), preprocess)
        if not text or not text.strip():
            logger.info("PLAY_REQUESTED_EMPTY: text was empty, returning.")
            return 0

        profile = (self._book_profile
                   if role == NarrationRole.BOOK_NARRATOR
                   else self._assistant_profile)

        # Idioma efetivo: override do chamador (ex.: texto em inglês) ou o do perfil.
        effective_language = language or profile.language

        # Apply text preprocessing
        if preprocess:
            processed_text = self._preprocessor.prepare_for_speech(
                text, style=profile.style
            )
        else:
            processed_text = text

        if not processed_text or not processed_text.strip():
            logger.info("PLAY_REQUESTED_PREPROCESS_EMPTY: text preprocessed to empty string.")
            return 0

        # Select provider
        provider = self._get_provider_for_profile(profile)
        logger.info("PROVIDER_SELECTED_REASON: Preferred was '%s', selected '%s'", 
                    profile.preferred_provider, provider.name if provider else "None")
        if provider is None:
            logger.error("TTS_ROUTER: No TTS provider available")
            raise TTSProviderError("Nenhum motor de voz (TTS) local registrado ou disponível.")

        self._active_provider = provider
        was_fallback = provider.name.lower() != profile.preferred_provider.lower()

        logger.info("ACTIVE_PROVIDER: %s", provider.name)

        # Check readiness for Kokoro before starting play
        if provider.name.lower() == "kokoro":
            logger.info("PROVIDER_READY: provider=Kokoro, is_ready=%s", getattr(provider, "is_ready", False))
            if not getattr(provider, "is_ready", False):
                # Orçamento condicional (ADR-005): com reserva saudável, espera
                # curta e cai para ela; SEM reserva, esperar mais é estritamente
                # melhor que falhar — sob carga pesada (OCR/indexação em
                # background) o warmup do Kokoro passa fácil dos 3s. A espera é
                # cancelável via stop() em passos de 0,5s.
                piper_probe = self._providers.get("piper")
                has_fallback = bool(piper_probe and piper_probe.health_check())
                budget = _READINESS_WAIT_FALLBACK_S if has_fallback else _READINESS_WAIT_SOLO_S
                logger.info("TTS_ROUTER: Kokoro is not ready yet at startup. Waiting up to %.1fs for warmup (fallback=%s)...",
                            budget, has_fallback)
                warmup_event = getattr(provider, "_warmup_event", None)
                waited = 0.0
                while waited < budget and not getattr(provider, "is_ready", False):
                    if self._is_cancelled:
                        logger.info("TTS_ROUTER: readiness wait cancelled by stop().")
                        return 0
                    step = min(0.5, budget - waited)
                    if warmup_event is not None:
                        warmup_event.wait(timeout=step)
                    else:
                        time.sleep(step)
                    waited += step
                if not getattr(provider, "is_ready", False):
                    logger.warning("READINESS_TIMEOUT: Kokoro readiness wait timed out after %.1fs", budget)

            # Re-check readiness after wait
            if not getattr(provider, "is_ready", False):
                logger.warning("TTS_ROUTER: Kokoro is not ready at startup after waiting.")
                piper_provider = self._providers.get("piper")
                if piper_provider and piper_provider.health_check():
                    logger.info("TTS_ROUTER_FALLBACK_TO_PIPER: Kokoro not ready at startup, falling back to Piper.")
                    provider = piper_provider
                    self._active_provider = provider
                    was_fallback = True
                else:
                    logger.error("TTS_ROUTER: Kokoro is not ready and Piper is not available.")
                    raise TTSProviderError(
                        "O motor de voz (Kokoro) ainda está inicializando e não há reserva (Piper) instalada. "
                        "Tarefas pesadas em segundo plano (OCR/indexação) podem atrasar a inicialização — "
                        "tente novamente em instantes."
                    )
            else:
                logger.info("PROVIDER_READY: provider=Kokoro, is_ready=True")

        if was_fallback:
            logger.info("TTS_ROUTER: Using fallback provider '%s' (preferred was '%s')",
                        provider.name, profile.preferred_provider)

        # Item 3 (fallback honesto): quando o chamador informou o idioma-alvo
        # (ex.: tradução PT, ou detecção confiante) e o provider ESCOLHIDO tem
        # vozes mas NENHUMA nesse idioma, é melhor um erro claro do que ler com
        # a voz do idioma errado. Só barra quando SABEMOS o idioma (override
        # explícito) e o provider afirma não ter a voz — nunca no idioma-do-perfil.
        if language is not None and self._language_support(provider, effective_language) is False:
            prim = self._primary_language(effective_language)
            lang_name = {"pt": "português", "en": "inglês"}.get(prim, prim or effective_language)
            logger.error("TTS_ROUTER: Provider '%s' sem voz em %s (idioma pedido='%s').",
                         provider.name, lang_name, effective_language)
            raise TTSProviderError(
                f"Motor reserva '{provider.name}' sem voz em {lang_name}. "
                f"Instale a voz pt_BR do Piper para a narração de reserva."
            )

        # Resolve voice ID dynamically if not explicitly specified or if fallback occurred.
        # Também resolvemos quando o idioma do TEXTO (override do chamador — ex.:
        # página em inglês detectada pelo AudioWorker) difere do idioma do PERFIL:
        # senão uma página em inglês seria lida com a voz portuguesa CONFIGURADA
        # (voice_id fixo do perfil). Só a voz troca — rate/volume/estilo do
        # usuário são preservados.
        voice_id = profile.voice_id
        language_mismatch = (
            language is not None
            and self._primary_language(effective_language)
            != self._primary_language(profile.language)
        )
        # Consistência voz×idioma (caso real 2026-07-17): usuário em leitura
        # TRADUZIDA (language="pt" explícito) escolheu uma voz INGLESA no menu
        # querendo "ouvir em inglês" — o perfil é pt-BR, então não havia
        # mismatch de PERFIL e a tradução PT saía na voz EN ("anglicado").
        # Com idioma explícito, a voz CONFIGURADA só vale se for do idioma do
        # texto; senão resolvemos pelo idioma do texto (rate/estilo mantidos).
        voice_language_mismatch = False
        if language is not None and voice_id:
            vlang = self._voice_language(provider, voice_id)
            voice_language_mismatch = (
                vlang is not None
                and self._primary_language(vlang)
                != self._primary_language(effective_language)
            )
        if not voice_id or was_fallback or language_mismatch or voice_language_mismatch:
            voice_id = self._resolve_voice(provider, effective_language, profile.style)

        # Chunk the text for interruptible playback
        # Use the already-preprocessed text. Chunk sizes adapted for role and provider latency.
        is_high_latency = provider.latency_profile() == "high"
        max_chars = 200 if is_high_latency else (400 if role == NarrationRole.ASSISTANT else 800)
        
        chunks = self._split_preprocessed_text(
            processed_text, 
            max_chars=max_chars
        )
        logger.info("SPLIT_PREPROCESSED_TEXT: chunks_count=%d, max_chars=%d", len(chunks), max_chars)

        self._is_cancelled = False
        
        # If pyttsx3 is selected, run legacy blocking speak sequentially
        if provider.name.lower() == "pyttsx3":
            logger.info("TTS_ROUTER: Playing via pyttsx3 (legacy manual mode)")
            spoken_count = 0
            for chunk in chunks:
                if self._is_cancelled:
                    break
                try:
                    provider.speak_blocking(chunk, voice_id=voice_id, rate=profile.rate, volume=profile.volume)
                    spoken_count += 1
                except Exception as e:
                    logger.error("TTS_ROUTER: pyttsx3 speak failed: %s", e)
                    break
            self._active_provider = None
            return spoken_count
        
        import threading
        from src.core.audio.continuous_player import ContinuousAudioPlayer

        logger.info("PLAYER_STREAM_OPENING: sample_rate=%d", 24000 if provider.name.lower() == "kokoro" else 22050)
        player = ContinuousAudioPlayer(sample_rate=24000 if provider.name.lower() == "kokoro" else 22050)
        player.start()
        # Expõe o player para que stop() possa interromper a reprodução já
        # bufferizada (ver _active_player em __init__).
        self._active_player = player

        # ── Voz por SENTENÇA em texto misto PT/EN (item 6) ────────────────
        # Só quando o chamador NÃO fixou o idioma (o fluxo traduzido é
        # single-language e continua intocado). Segmentamos o texto já
        # pré-processado em runs de idioma e resolvemos a voz por run; um único
        # run mantém o caminho atual byte-a-byte (mesma voz, mesmos chunks).
        runs_plan: list[dict] = [{
            "language": effective_language,
            "voice_id": voice_id,
            "chunks": chunks,
        }]
        if language is None:
            lang_runs = split_language_runs(processed_text, profile.language)
            if len(lang_runs) > 1:
                planned: list[dict] = []
                prev_voice = voice_id  # voz do perfil/base: reserva graciosa
                for run_lang, run_text in lang_runs:
                    resolved = self._resolve_voice(provider, run_lang, profile.style)
                    if resolved is None:
                        # Sem voz para o idioma do run → herda a voz anterior/perfil
                        # (degradação graciosa; nunca aborta a narração).
                        resolved = prev_voice
                    else:
                        prev_voice = resolved
                    run_chunks = self._split_preprocessed_text(run_text, max_chars=max_chars)
                    if run_chunks:
                        planned.append({
                            "language": run_lang,
                            "voice_id": resolved,
                            "chunks": run_chunks,
                        })
                if planned:
                    runs_plan = planned

        original_provider = provider
        state = {
            "provider": provider,
            "voice_id": voice_id,
            "spoken_count": 0,
            "first_chunk": True,
            "language": effective_language,
        }

        def _synthesize_one(chunk, idx):
            """Sintetiza e enfileira UM chunk com o provider/voz atuais do state.

            Levanta ``_SLOFallbackSwap`` quando o SLO de TTFB estoura e a troca
            já foi aplicada ao state (o chamador RE-sintetiza este chunk com o
            provider trocado). Levanta ``TTSProviderError`` em falha de síntese.
            """
            prov = state["provider"]

            if prov.name.lower() == "pyttsx3":
                player.wait_until_done()
                prov.speak_blocking(chunk, voice_id=state["voice_id"],
                                    rate=profile.rate, volume=profile.volume)
                state["spoken_count"] += 1
                return

            if prov.supports_streaming():
                logger.info("CHUNK_%d_GENERATING_STREAM: length=%d", idx, len(chunk))
                start_time = time.time()
                stream = prov.synthesize_stream(
                    chunk,
                    voice_id=state["voice_id"],
                    rate=profile.rate,
                    volume=profile.volume,
                )
                for segment_result in stream:
                    if self._is_cancelled:
                        break
                    if not segment_result.success:
                        raise TTSProviderError(segment_result.error)
                    if state["first_chunk"]:
                        ttfb = time.time() - start_time
                        logger.info("TTS_ROUTER_TTFB_MS: %.2f ms (first segment of stream)", ttfb * 1000.0)
                        # Check TTFB SLO. Rodada 3: só troca de motor se o reserva
                        # puder falar o idioma do run — senão continua no atual
                        # (lento > "anglicado"). Ver _mid_stream_fallback.
                        if ttfb > self._TTFB_SLO_SECONDS:
                            logger.warning("TTS_ROUTER: TTFB for '%s' was %.2fs (SLO violated).", prov.name, ttfb)
                            fallback, fb_voice = self._mid_stream_fallback(
                                state["provider"], state["language"],
                                profile.style, language is not None)
                            if fallback is not None:
                                if state["provider"].name.lower() == "kokoro" and fallback.name.lower() == "piper":
                                    logger.info("TTS_ROUTER_FALLBACK_TO_PIPER: Falling back from Kokoro to Piper due to TTFB SLO violation (%.2fs)", ttfb)
                                state["provider"] = fallback
                                self._active_provider = fallback
                                state["voice_id"] = fb_voice
                                state["first_chunk"] = False
                                raise _SLOFallbackSwap()
                            # Sem reserva utilizável (inexistente ou sem voz no
                            # idioma explícito): mantém o provider atual.
                            logger.warning(
                                "TTS_ROUTER: SLO violado (%.2fs) mas mantendo '%s' — reserva ausente ou sem voz em '%s'.",
                                ttfb, state["provider"].name, state["language"])
                        state["first_chunk"] = False
                    if not self._is_cancelled and segment_result.audio_data is not None:
                        player.enqueue(
                            segment_result.audio_data,
                            segment_result.sample_rate,
                            channels=prov.channels,
                            dtype=prov.dtype,
                        )
                if not self._is_cancelled:
                    state["spoken_count"] += 1
            else:
                logger.info("CHUNK_%d_GENERATING: length=%d", idx, len(chunk))
                start_time = time.time()
                result = prov.synthesize(
                    chunk,
                    voice_id=state["voice_id"],
                    rate=profile.rate,
                    volume=profile.volume,
                )
                if not result.success:
                    raise TTSProviderError(result.error)
                ttfb = time.time() - start_time
                logger.info("CHUNK_%d_GENERATED: bytes=%d, rate=%d, ttfb=%.2fs (%.2f ms)",
                            idx, len(result.audio_data) if result.audio_data is not None else 0,
                            result.sample_rate, ttfb, ttfb * 1000.0)
                logger.info("TTS_ROUTER_TTFB_MS: %.2f ms", ttfb * 1000.0)
                # Check TTFB SLO (ver comentário no ramo de streaming).
                if state["first_chunk"] and ttfb > self._TTFB_SLO_SECONDS:
                    logger.warning("TTS_ROUTER: TTFB for '%s' was %.2fs (SLO violated).", prov.name, ttfb)
                    fallback, fb_voice = self._mid_stream_fallback(
                        state["provider"], state["language"],
                        profile.style, language is not None)
                    if fallback is not None:
                        if state["provider"].name.lower() == "kokoro" and fallback.name.lower() == "piper":
                            logger.info("TTS_ROUTER_FALLBACK_TO_PIPER: Falling back from Kokoro to Piper due to TTFB SLO violation (%.2fs)", ttfb)
                        state["provider"] = fallback
                        self._active_provider = fallback
                        state["voice_id"] = fb_voice
                        state["first_chunk"] = False
                        logger.info("TTS_ROUTER: Switched to '%s' for next chunks", fallback.name)
                        raise _SLOFallbackSwap()
                    logger.warning(
                        "TTS_ROUTER: SLO violado (%.2fs) mas mantendo '%s' — reserva ausente ou sem voz em '%s'.",
                        ttfb, state["provider"].name, state["language"])
                state["first_chunk"] = False
                if (not self._is_cancelled and result.audio_data is not None
                        and prov.name.lower() != "pyttsx3"):
                    player.enqueue(
                        result.audio_data,
                        result.sample_rate,
                        channels=prov.channels,
                        dtype=prov.dtype,
                    )
                    state["spoken_count"] += 1

        def _handle_generic_failure(chunk, idx, exc) -> bool:
            """Fallback por FALHA REAL de síntese (não-SLO): recomputa o próximo
            motor abaixo e re-sintetiza o chunk. Retorna ``False`` quando não há
            reserva utilizável (o chamador para o loop)."""
            logger.error("TTS_ROUTER: Provider '%s' failed on chunk %d: %s",
                         state["provider"].name, idx, exc)
            fallback = self._get_fallback_provider(state["provider"])
            if not fallback:
                return False
            if state["provider"].name.lower() == "kokoro" and fallback.name.lower() == "piper":
                logger.info("TTS_ROUTER_FALLBACK_TO_PIPER: Falling back from Kokoro to Piper mid-stream. Reason: %s", exc)
            logger.info("TTS_ROUTER: Switching to fallback '%s' mid-stream", fallback.name)
            state["provider"] = fallback
            self._active_provider = fallback
            state["voice_id"] = self._resolve_voice(fallback, state["language"], profile.style)
            try:
                if fallback.name.lower() == "pyttsx3":
                    player.wait_until_done()
                    fallback.speak_blocking(chunk, voice_id=state["voice_id"],
                                            rate=profile.rate, volume=profile.volume)
                    state["spoken_count"] += 1
                elif state["provider"].supports_streaming():
                    stream = state["provider"].synthesize_stream(
                        chunk,
                        voice_id=state["voice_id"],
                        rate=profile.rate,
                        volume=profile.volume,
                    )
                    for r in stream:
                        if r.success and not self._is_cancelled and r.audio_data is not None:
                            player.enqueue(
                                r.audio_data,
                                r.sample_rate,
                                channels=state["provider"].channels,
                                dtype=state["provider"].dtype,
                            )
                    if not self._is_cancelled:
                        state["spoken_count"] += 1
                else:
                    result = state["provider"].synthesize(
                        chunk,
                        voice_id=state["voice_id"],
                        rate=profile.rate,
                        volume=profile.volume,
                    )
                    if result.success and not self._is_cancelled and result.audio_data is not None:
                        player.enqueue(
                            result.audio_data,
                            result.sample_rate,
                            channels=state["provider"].channels,
                            dtype=state["provider"].dtype,
                        )
                        state["spoken_count"] += 1
            except Exception as exc2:
                logger.error("TTS_ROUTER: Fallback also failed: %s", exc2)
                return False
            return True

        def synthesis_worker():
            stop = False
            for run in runs_plan:
                if stop or self._is_cancelled:
                    break
                state["language"] = run["language"]
                # Resolve a voz do run para o provider ATUAL: se um fallback já
                # trocou o motor, re-resolve; senão usa a voz pré-calculada.
                if state["provider"] is original_provider:
                    state["voice_id"] = run["voice_id"]
                else:
                    rv = self._resolve_voice(state["provider"], run["language"], profile.style)
                    if rv is not None:
                        state["voice_id"] = rv
                for idx, chunk in enumerate(run["chunks"]):
                    if self._is_cancelled:
                        logger.info("TTS_ROUTER: Synthesis cancelled mid-stream.")
                        stop = True
                        break
                    if not chunk.strip():
                        continue
                    try:
                        _synthesize_one(chunk, idx)
                    except _SLOFallbackSwap:
                        # Troca por SLO já aplicada no state: RE-sintetiza ESTE
                        # chunk com o provider trocado (sem recomputar fallback,
                        # sem parar). first_chunk=False ⇒ não re-dispara o SLO.
                        try:
                            _synthesize_one(chunk, idx)
                        except TTSProviderError as exc:
                            if not _handle_generic_failure(chunk, idx, exc):
                                stop = True
                                break
                        except Exception as exc:
                            logger.error("TTS_ROUTER: Unexpected error on chunk %d: %s", idx, exc)
                            stop = True
                            break
                    except TTSProviderError as exc:
                        if not _handle_generic_failure(chunk, idx, exc):
                            stop = True
                            break
                    except Exception as exc:
                        logger.error("TTS_ROUTER: Unexpected error on chunk %d: %s", idx, exc)
                        stop = True
                        break

        synth_thread = threading.Thread(target=synthesis_worker, daemon=True)
        synth_thread.start()

        while synth_thread.is_alive() and not self._is_cancelled:
            time.sleep(0.1)

        if self._is_cancelled:
            player.stop()
        else:
            player.wait_until_done()
            player.stop()

        synth_thread.join(timeout=1.0)

        spoken_count = state["spoken_count"]
        logger.info("TTS_ROUTER: Spoke %d/%d chunks using '%s'",
                     spoken_count, len(chunks), state["provider"].name)
        self._active_provider = None
        self._active_player = None
        return spoken_count

    def stop(self) -> None:
        """Stop any ongoing synthesis/playback."""
        self._is_cancelled = True
        if self._active_provider:
            try:
                self._active_provider.stop()
            except Exception as e:
                logger.warning("TTS_ROUTER: Error stopping active provider: %s", e)
        # Interrompe a reprodução imediatamente: sem isto, o áudio já enfileirado
        # continua tocando até o fim mesmo com _is_cancelled=True, porque
        # wait_until_done() só observa o estado do próprio player.
        if self._active_player:
            try:
                self._active_player.stop()
            except Exception as e:
                logger.warning("TTS_ROUTER: Error stopping active player: %s", e)

    def voices_by_language(self, provider_name: str,
                           languages: tuple[str, ...] = ("pt", "en")) -> dict:
        """Vozes do provider agrupadas por prefixo de idioma (p/ menu da GUI).

        Devolve {"pt": [VoiceInfo...], "en": [...]}; vazio se o provider não
        existe ou não lista vozes (graceful — o menu mostra 'automática').
        """
        provider = self._providers.get((provider_name or "").lower())
        if provider is None:
            return {}
        try:
            voices = provider.available_voices()
        except Exception as e:
            logger.warning("TTS_ROUTER: available_voices('%s') falhou: %s",
                           provider_name, e)
            return {}
        out: dict = {}
        for voice in voices or []:
            lang = (voice.language or "").lower()
            for prefix in languages:
                if lang.startswith(prefix):
                    out.setdefault(prefix, []).append(voice)
                    break
        return out

    def pause(self) -> None:
        """Pausa a reprodução atual (retomável no mesmo ponto via resume())."""
        if self._active_player:
            try:
                self._active_player.pause()
            except Exception as e:
                logger.warning("TTS_ROUTER: Error pausing active player: %s", e)

    def resume(self) -> None:
        """Retoma a reprodução pausada a partir do ponto exato."""
        if self._active_player:
            try:
                self._active_player.resume()
            except Exception as e:
                logger.warning("TTS_ROUTER: Error resuming active player: %s", e)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _primary_language(language: Optional[str]) -> str:
        """Subtag primário de um código de idioma ('en-US'→'en', 'pt_BR'→'pt')."""
        if not language:
            return ""
        return language.strip().lower().replace("_", "-").split("-")[0]

    def _resolve_voice(self, provider: BaseTTSProvider, language: str, style: str) -> Optional[str]:
        """Resolve a suitable voice ID for the given provider, language, and style.

        Searches the provider's available voices for a match.
        """
        try:
            voices = provider.available_voices()
        except Exception as e:
            logger.warning("TTS_ROUTER: Failed to get voices from '%s': %s", provider.name, e)
            return None

        if not voices:
            return None

        target_lang = language.lower()
        target_style = style.lower()

        # Step 1: Filter by language match (exact or prefix/overlap, e.g. 'pt-BR' matches 'pt-br' or 'pt')
        lang_matches = []
        for voice in voices:
            voice_lang = voice.language.lower()
            if voice_lang == target_lang or voice_lang.startswith(target_lang) or target_lang.startswith(voice_lang):
                lang_matches.append(voice)

        # Item 3 (fallback honesto): se o provider TEM vozes mas NENHUMA no
        # idioma pedido, NÃO devolvemos uma voz de idioma errado (antes caía em
        # voices[0] → português lido com voz inglesa). Retorna None; quem chama
        # (speak) decide sinalizar erro claro à GUI em vez de sintetizar errado.
        if not lang_matches:
            logger.info("TTS_ROUTER: Provider '%s' tem vozes, mas nenhuma no idioma '%s' — sem resolução.",
                        provider.name, language)
            return None

        # Step 2: Look for a language candidate with matching style tag
        for voice in lang_matches:
            if target_style in [tag.lower() for tag in voice.tags]:
                logger.info("TTS_ROUTER: Resolved voice '%s' for provider '%s' (lang='%s', style='%s')",
                            voice.voice_id, provider.name, language, style)
                return voice.voice_id

        # Step 3: Fall back to first matching language candidate
        logger.info("TTS_ROUTER: Resolved default voice '%s' for provider '%s' matching language '%s'",
                    lang_matches[0].voice_id, provider.name, language)
        return lang_matches[0].voice_id

    def _language_support(self, provider: BaseTTSProvider, language: str) -> Optional[bool]:
        """Se o provider tem/《não tem》voz no idioma pedido (item 3).

        Retorna ``True`` (tem), ``False`` (tem vozes, mas nenhuma no idioma) ou
        ``None`` (lista vazia/indisponível ⇒ não sabemos; usa a voz interna
        padrão do motor). Só ``False`` justifica um erro honesto na GUI.
        """
        try:
            voices = provider.available_voices()
        except Exception:
            return None
        if not voices:
            return None
        target = self._primary_language(language)
        if not target:
            return None
        for voice in voices:
            vlang = self._primary_language(voice.language)
            if vlang and (vlang == target or vlang.startswith(target) or target.startswith(vlang)):
                return True
        return False

    def _voice_language(self, provider: BaseTTSProvider, voice_id: str) -> Optional[str]:
        """Idioma da voz *voice_id* segundo ``available_voices()`` do provider.

        ``None`` quando a voz não está listada ou a lista é indisponível —
        nesse caso NÃO dá para afirmar mismatch e a voz configurada é mantida
        (degradação graciosa, ADR-005).
        """
        try:
            voices = provider.available_voices()
        except Exception:
            return None
        for voice in voices or []:
            if voice.voice_id == voice_id:
                return voice.language or None
        return None

    def _mid_stream_fallback(
        self, current: BaseTTSProvider, language: str, style: str,
        language_explicit: bool,
    ) -> tuple[Optional[BaseTTSProvider], Optional[str]]:
        """Decide o fallback por violação do SLO de TTFB no meio da narração.

        Retorna ``(fallback, voice_id)`` quando a troca é segura, ou
        ``(None, None)`` quando NÃO se deve trocar — nesse caso quem chama
        CONTINUA com o provider atual (lento, porém com o áudio correto).

        Racional (rodada 3 de ajustes de TTS): sob indexação concorrente o TTFB
        do Kokoro estourava o SLO de 3s e o roteador trocava para o Piper. Mas
        se o motor de reserva NÃO tem voz no idioma efetivo (caso real: só o
        modelo EN do Piper instalado e a página é PT), a troca produzia áudio
        "anglicado" (``_resolve_voice`` devolvia ``None`` → o Piper lia PT com o
        modelo default EN) ou abortava a narração no meio (a checagem honesta de
        idioma no re-início). Áudio CORRETO porém lento é melhor que áudio
        errado ou silêncio. Por isso só barramos a troca quando SABEMOS o idioma
        (override explícito do chamador) E o reserva AFIRMA não ter voz nele
        (``_language_support`` retorna ``False``). Sem idioma explícito, ou com
        capacidade de idioma desconhecida (lista de vozes vazia → ``None``), o
        comportamento antigo é preservado. Com a Tarefa A (cancelar a indexação
        ao iniciar o áudio), a causa da lentidão some e o SLO raramente dispara.
        """
        fallback = self._get_fallback_provider(current)
        if fallback is None:
            return None, None
        if language_explicit and self._language_support(fallback, language) is False:
            # Reserva sem voz no idioma pedido → não troca (mantém o atual).
            return None, None
        # Reserva com voz no idioma (ou capacidade desconhecida): resolve a voz
        # correta. Quando HÁ vozes no idioma, _resolve_voice devolve uma delas
        # (nunca None), garantindo que não sintetizamos com voice_id=None tendo
        # idioma explícito e vozes listadas no idioma.
        return fallback, self._resolve_voice(fallback, language, style)

    def _get_fallback_provider(self, exclude: BaseTTSProvider) -> Optional[BaseTTSProvider]:
        """Find the next healthy provider after the excluded one, excluding legacy pyttsx3."""
        exclude_tier_idx = TIER_ORDER.index(exclude.tier) if exclude.tier in TIER_ORDER else -1

        for tier in TIER_ORDER[exclude_tier_idx + 1:]:
            if tier == "legacy":
                continue
            for name, provider in self._providers.items():
                if provider is not exclude and provider.tier == tier:
                    if name == "pyttsx3":
                        continue
                    try:
                        if provider.health_check():
                            return provider
                    except Exception:
                        continue
        
        return None

    @staticmethod
    def _split_preprocessed_text(text: str, max_chars: int = 600) -> list[str]:
        """Split already-preprocessed text into chunks for playback.

        Similar to split_text_for_tts but skips the cleaning step
        since text is already preprocessed.
        """
        import re

        if not text.strip():
            return []

        paragraphs = text.split("\n\n")
        chunks = []

        for p in paragraphs:
            p_strip = p.strip()
            if not p_strip:
                continue

            if len(p_strip) <= max_chars:
                chunks.append(p_strip)
            else:
                sentences = re.split(r'(?<=[.!?])\s+', p_strip)
                current = ""
                for s in sentences:
                    s = s.strip()
                    if not s:
                        continue
                    if not current:
                        current = s
                    elif len(current) + 1 + len(s) <= max_chars:
                        current += " " + s
                    else:
                        chunks.append(current)
                        current = s
                if current:
                    chunks.append(current)

        return chunks

    # ── Lifecycle ─────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Shut down all providers cleanly."""
        self.stop()
        for name, provider in self._providers.items():
            try:
                provider.shutdown()
            except Exception as e:
                logger.warning("TTS_ROUTER: Error shutting down '%s': %s", name, e)
        self._providers.clear()
        logger.info("TTS_ROUTER: All providers shut down")
