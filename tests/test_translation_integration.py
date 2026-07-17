"""Testes de integração para o TranslationService (Fase 8).

Valida que o worker assíncrono dispara callbacks corretamente via Qt event loop,
usando backend mockado (sem download do modelo real).
"""
import pytest


@pytest.mark.integration
class TestTranslationWorkerIntegration:
    """Testa se o pipeline worker → callback funciona end-to-end (sem modelo real)."""

    def test_successful_translation_emits_result(self, qtbot):
        from src.gui.translation_service import TranslationService

        TranslationService.reset_instance()
        service = TranslationService.get_instance()

        # Mock do backend para não baixar modelo
        service.backend._is_loaded = True
        service.backend._device = "cpu"
        service.backend.translate = lambda text, src, tgt: f"Traduzido: {text}"
        # Hermético: sem revisão via LLM (o caminho da revisão tem testes
        # próprios mockados em test_translation_quality.py).
        service.config["revise_with_llm"] = False

        results = []
        service.translate_async(
            "Hello world",
            on_success=lambda res: results.append(res),
        )

        qtbot.waitUntil(lambda: len(results) > 0, timeout=3000)
        assert results[0] == "Traduzido: Hello world"

        TranslationService.reset_instance()

    def test_error_in_backend_emits_error_callback(self, qtbot):
        from src.gui.translation_service import TranslationService

        TranslationService.reset_instance()
        service = TranslationService.get_instance()

        # Simula falha controlada
        def failing_translate(text, src, tgt):
            raise RuntimeError("Modelo indisponível offline")

        service.backend._is_loaded = True
        service.backend._device = "cpu"
        service.backend.translate = failing_translate

        errors = []
        service.translate_async(
            "Test",
            on_error=lambda err: errors.append(err),
        )

        qtbot.waitUntil(lambda: len(errors) > 0, timeout=3000)
        assert "Modelo indisponível offline" in errors[0]

        TranslationService.reset_instance()

    def test_worker_cleanup_after_completion(self, qtbot):
        """Verifica que o worker é removido da lista de ativos após terminar."""
        from src.gui.translation_service import TranslationService

        TranslationService.reset_instance()
        service = TranslationService.get_instance()

        service.backend._is_loaded = True
        service.backend._device = "cpu"
        service.backend.translate = lambda text, src, tgt: "OK"
        service.config["revise_with_llm"] = False  # hermético (sem Ollama real)

        done = []
        service.translate_async(
            "test",
            on_success=lambda res: done.append(True),
        )

        qtbot.waitUntil(lambda: len(done) > 0, timeout=3000)

        # Dá tempo pro cleanup executar
        qtbot.wait(200)
        assert len(service._active_workers) == 0

        TranslationService.reset_instance()
