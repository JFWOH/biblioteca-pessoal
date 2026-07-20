import logging
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.tts.tts_router import TTSRouter
from src.core.tts.voice_profile import NarrationRole
from src.core.tts.text_preprocessor import TTSTextPreprocessor
from src.core.tts.language_detect import detect_language_confident
from src.core.audio.tts_backend import TTSBackendUnavailable

logger = logging.getLogger(__name__)


class AudioWorker(QThread):
    """Worker assíncrono para reprodução de áudio na thread de background.

    Phase 13: Now uses the unified TTSRouter instead of direct pyttsx3.
    Supports distinct narration roles (book narrator vs assistant).
    Garante que a interface gráfica permaneça 100% responsiva.
    """

    playback_started = pyqtSignal()
    playback_finished = pyqtSignal(int)  # quantidade de chunks falados
    error_occurred = pyqtSignal(str)
    provider_changed = pyqtSignal(str)  # emitted when fallback occurs

    def __init__(self, text: str, rate: float = 1.0, volume: float = 1.0,
                 role: NarrationRole = NarrationRole.BOOK_NARRATOR,
                 router: TTSRouter | None = None,
                 language: str | None = None,
                 prepared: list | None = None,
                 parent=None):
        super().__init__(parent)
        self._text = text
        self._rate = rate
        self._volume = volume
        self._role = role
        self._router = router
        # Áudio JÁ sintetizado pela pré-síntese (tarefa 3.6). Quando presente,
        # o worker TOCA direto no player contínuo, sem re-sintetizar (corta o
        # gap entre páginas). Cada item: {audio_data, sample_rate, channels, dtype}.
        self._prepared = prepared
        self._prepared_player = None
        # Idioma da narração: explícito (ex.: tradução) ou autodetectado do texto,
        # para que páginas em inglês sejam lidas com voz em inglês. Usa a detecção
        # CONFIANTE: em texto ambíguo/misto ela devolve None e NÃO forçamos
        # override — a voz do perfil prevalece (evita a regressão "anglicada" em
        # traduções PT salpicadas de termos técnicos EN).
        self._language = language or detect_language_confident(text)
        self._is_cancelled = False
        
        # Load configuration profiles from MainWindow IN THE MAIN THREAD
        self._book_profile_data = None
        self._assistant_profile_data = None
        if parent is not None and hasattr(parent, "window"):
            parent_window = parent.window()
            config = getattr(parent_window, "_config", None)
            if config:
                tts_cfg = config.tts_config
                self._book_profile_data = tts_cfg.get("book_narrator", {})
                self._assistant_profile_data = tts_cfg.get("assistant", {})

    def run(self) -> None:
        """Execução paralela na thread de background."""
        try:
            # Modo pré-sintetizado (3.6): toca o áudio já pronto, sem síntese.
            if self._prepared:
                self._run_prepared()
                return

            # Initialize router if not provided
            if self._router is None:
                logger.info("AUDIO_WORKER: ROUTER_REUSED=false (creating new router)")
                self._router = TTSRouter(TTSTextPreprocessor())
                self._router.auto_register_providers()
                self._router.initialize()
            else:
                logger.info("AUDIO_WORKER: ROUTER_REUSED=true (reusing persistent router)")

            # Apply loaded profiles
            if self._book_profile_data is not None and self._assistant_profile_data is not None:
                from src.core.tts.voice_profile import VoiceProfile
                self._router.set_book_profile(VoiceProfile.from_dict(self._book_profile_data))
                self._router.set_assistant_profile(VoiceProfile.from_dict(self._assistant_profile_data))
                logger.info("AUDIO_WORKER: Loaded voice profiles from config")

            # Apply rate/volume overrides to the appropriate profile
            if self._role == NarrationRole.BOOK_NARRATOR:
                profile = self._router.get_book_profile()
            else:
                profile = self._router.get_assistant_profile()

            if self._rate != 1.0:
                profile.rate = self._rate
            if self._volume != 1.0:
                profile.volume = self._volume

            self.playback_started.emit()

            # Report active provider
            active = self._router.get_active_provider_name()
            if active != "none":
                self.provider_changed.emit(active)

            # Rodada 4 (auditoria A1): worker APOSENTADO antes de chegar aqui
            # não pode prosseguir — router.speak() reseta _is_cancelled do
            # ROUTER na entrada e apagaria o próprio stop, narrando a página
            # inteira em background. Checagem imediatamente antes do speak().
            if self._is_cancelled or self.isInterruptionRequested():
                logger.info("AUDIO_WORKER: cancelado antes do speak — abortando")
                return

            # Synthesize and play through the router
            chunks_spoken = self._router.speak(
                self._text,
                role=self._role,
                preprocess=True,
                language=self._language,
            )

            # Report final provider used
            final_provider = self._router.get_active_provider_name()
            if final_provider != "none":
                self.provider_changed.emit(final_provider)

            self.playback_finished.emit(chunks_spoken)

        except TTSBackendUnavailable as e:
            logger.error("AUDIO_WORKER: Backend indisponivel: %s", e)
            self.error_occurred.emit(str(e))
        except Exception as e:
            logger.error("AUDIO_WORKER: Erro inesperado: %s", e)
            self.error_occurred.emit(f"Erro ao reproduzir audio: {e}")

    def _run_prepared(self) -> None:
        """Toca áudio JÁ sintetizado (pré-síntese 3.6) direto no player contínuo.

        Espelha exatamente o ``enqueue`` que o TTSRouter faz internamente
        (audio_data + sample_rate + channels + dtype), mas sem re-sintetizar —
        é isso que corta o gap ao virar de página. ADR-005: lista vazia ou
        falha vira "0 chunks", nunca crash (o chamador cai no caminho normal).
        """
        from src.core.audio.continuous_player import ContinuousAudioPlayer

        segments = self._prepared or []
        if not segments:
            self.playback_finished.emit(0)
            return

        sample_rate = int(segments[0].get("sample_rate") or 24000)
        player = ContinuousAudioPlayer(sample_rate=sample_rate)
        player.start()
        self._prepared_player = player
        self.playback_started.emit()

        spoken = 0
        try:
            for seg in segments:
                if self._is_cancelled:
                    break
                audio = seg.get("audio_data")
                if audio is None:
                    continue
                player.enqueue(
                    audio,
                    int(seg.get("sample_rate") or sample_rate),
                    channels=int(seg.get("channels") or 1),
                    dtype=seg.get("dtype") or "float32",
                )
                spoken += 1

            if self._is_cancelled:
                player.stop()
            else:
                player.wait_until_done()
                player.stop()
        finally:
            self._prepared_player = None

        self.playback_finished.emit(spoken)

    def stop(self) -> None:
        """Interrompe a leitura de forma best-effort e graciosa."""
        self._is_cancelled = True
        if self._prepared_player is not None:
            try:
                self._prepared_player.stop()
            except Exception:
                pass
        elif self._router:
            self._router.stop()
        self.requestInterruption()

    def pause(self) -> None:
        """Pausa a reprodução (retomável no mesmo ponto via resume())."""
        if self._prepared_player is not None:
            self._prepared_player.pause()
        elif self._router:
            self._router.pause()

    def resume(self) -> None:
        """Retoma a reprodução pausada a partir do ponto exato."""
        if self._prepared_player is not None:
            self._prepared_player.resume()
        elif self._router:
            self._router.resume()


class PreSynthesisWorker(QThread):
    """Sintetiza (SEM tocar) o áudio da PRÓXIMA página em background (3.6).

    Enquanto a página atual é narrada, este worker sintetiza a próxima e guarda
    os segmentos no ``PreSynthesisCache`` (core puro). A reprodução acontece
    depois, pelo ``AudioWorker`` em modo ``prepared`` — sem gap de síntese.

    Reaproveita a seleção de provedor/voz do ``TTSRouter`` (uso somente-leitura
    dos seus helpers), sem tocar no router. ADR-006: o threading vive aqui, na
    GUI. ADR-005: qualquer falha apenas NÃO preenche o cache (a leitura
    contínua cai no caminho normal de síntese+reprodução).
    """

    ready = pyqtSignal(object)   # key (o cache já foi preenchido)
    failed = pyqtSignal(str)

    def __init__(self, text: str, key, cache, router: TTSRouter | None,
                 role: NarrationRole = NarrationRole.BOOK_NARRATOR,
                 language: str | None = None, parent=None):
        super().__init__(parent)
        self._text = text or ""
        self._key = key
        self._cache = cache
        self._router = router
        self._role = role
        self._language = language
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self) -> None:
        try:
            segments = self._synthesize()
            if self._cancelled or not segments:
                return
            self._cache.store(self._key, segments)
            self.ready.emit(self._key)
        except Exception as exc:  # ADR-005: nunca derruba a narração em curso
            logger.warning("PreSynthesisWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))

    def _synthesize(self) -> list:
        """Delegado à API pública do router (débito 3.6 pago na rodada B2):
        o pipeline de síntese-sem-tocar vive em
        ``TTSRouter.synthesize_segments`` — a GUI não acessa mais helpers
        privados do router."""
        router = self._router
        if router is None:
            return []
        return router.synthesize_segments(
            self._text, role=self._role, language=self._language,
            cancel_check=lambda: self._cancelled)
