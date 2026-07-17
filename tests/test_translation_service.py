"""Testes unitários para o backend NLLB e TranslationService (Fase 8).

Todos os testes usam mocks completos para evitar download do modelo real.
Cobre: truncamento, singleton, fallback sem modelo e backend indisponível.
"""
import pytest
from unittest.mock import MagicMock, patch


# ── Backend: Truncamento ─────────────────────────────────────────────────────

class TestNLLBBackendTruncation:
    """Garante que textos acima de max_input_length são truncados antes da inferência."""

    def test_text_is_truncated_to_max_length(self):
        from src.core.translation_backends.nllb_backend import NLLBBackend

        backend = NLLBBackend(model_id="test_model")
        backend._is_loaded = True
        backend._device = "cpu"

        # Mocks para tokenizer e model
        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        # Simula retorno do tokenizer: dict de tensors
        tensor_mock = MagicMock()
        tensor_mock.to.return_value = tensor_mock
        mock_tokenizer.return_value = {"input_ids": tensor_mock, "attention_mask": tensor_mock}
        mock_tokenizer.convert_tokens_to_ids.return_value = 256047  # ID fictício
        mock_tokenizer.batch_decode.return_value = ["Texto traduzido"]
        mock_model.generate.return_value = [MagicMock()]

        backend._tokenizer = mock_tokenizer
        backend._model = mock_model

        long_text = "A" * 3000
        result = backend.translate(long_text, "en", "pt")

        assert result == "Texto traduzido"

        # Verifica que o texto passado ao tokenizer foi truncado
        call_args = mock_tokenizer.call_args[0][0]
        assert len(call_args) <= backend.max_input_length

    def test_short_text_is_not_truncated(self):
        from src.core.translation_backends.nllb_backend import NLLBBackend

        backend = NLLBBackend(model_id="test_model")
        backend._is_loaded = True
        backend._device = "cpu"

        mock_tokenizer = MagicMock()
        mock_model = MagicMock()

        tensor_mock = MagicMock()
        tensor_mock.to.return_value = tensor_mock
        mock_tokenizer.return_value = {"input_ids": tensor_mock, "attention_mask": tensor_mock}
        mock_tokenizer.convert_tokens_to_ids.return_value = 256047
        mock_tokenizer.batch_decode.return_value = ["Translated"]
        mock_model.generate.return_value = [MagicMock()]

        backend._tokenizer = mock_tokenizer
        backend._model = mock_model

        short_text = "Hello world"
        result = backend.translate(short_text, "en", "pt")

        assert result == "Translated"
        call_args = mock_tokenizer.call_args[0][0]
        assert call_args == short_text

    def test_empty_text_returns_empty(self):
        from src.core.translation_backends.nllb_backend import NLLBBackend

        backend = NLLBBackend(model_id="test_model")
        assert backend.translate("", "en", "pt") == ""
        assert backend.translate("   ", "en", "pt") == ""


# ── Backend: Fallback sem modelo ─────────────────────────────────────────────

class TestNLLBBackendFallback:
    """Garante que a falha na carga do modelo produz RuntimeError (não crash silencioso)."""

    def test_load_failure_raises_runtime_error(self):
        from src.core.translation_backends.nllb_backend import NLLBBackend

        backend = NLLBBackend(model_id="modelo_inexistente_xyz")

        # Patcha os imports internos para simular falha de rede/disco
        with patch.dict("sys.modules", {"transformers": MagicMock()}):
            # Faz o from_pretrained levantar exceção
            import sys
            mock_transformers = sys.modules["transformers"]
            mock_transformers.AutoTokenizer.from_pretrained.side_effect = OSError(
                "Can't load tokenizer — no internet and no local cache."
            )

            with pytest.raises(RuntimeError, match="Falha ao carregar modelo"):
                backend._load_model_lazy()

        # Confirma que o backend não ficou em estado inconsistente
        assert not backend.is_loaded()

    def test_missing_transformers_raises_runtime_error(self):
        from src.core.translation_backends.nllb_backend import NLLBBackend

        backend = NLLBBackend(model_id="test_model")

        # Simula ImportError quando transformers não está instalado
        with patch("builtins.__import__", side_effect=ImportError("No module named 'transformers'")):
            with pytest.raises((RuntimeError, ImportError)):
                backend._load_model_lazy()

        assert not backend.is_loaded()


# ── Service: Singleton ───────────────────────────────────────────────────────

class TestTranslationServiceSingleton:
    """Garante que TranslationService é singleton."""

    def test_singleton_returns_same_instance(self):
        from src.gui.translation_service import TranslationService

        # Reset para isolar o teste
        TranslationService.reset_instance()

        s1 = TranslationService.get_instance()
        s2 = TranslationService.get_instance()
        assert s1 is s2

        # Cleanup
        TranslationService.reset_instance()


# ── Service: Worker assíncrono com erro ──────────────────────────────────────

class TestTranslationServiceErrorHandling:
    """Garante que erros no worker são propagados via callback on_error, sem crash."""

    def test_error_callback_is_invoked(self, qtbot):
        from src.gui.translation_service import TranslationService

        TranslationService.reset_instance()
        service = TranslationService.get_instance()

        # Faz o backend levantar exceção
        service.backend._is_loaded = True
        service.backend._device = "cpu"
        service.backend._tokenizer = MagicMock()
        service.backend._model = MagicMock()
        service.backend._model.generate.side_effect = RuntimeError("Inferência explodiu")

        errors = []
        service.translate_async(
            text="Test",
            on_error=lambda err: errors.append(err),
        )

        qtbot.waitUntil(lambda: len(errors) > 0, timeout=3000)
        assert "Inferência explodiu" in errors[0] or "Erro" in errors[0]

        TranslationService.reset_instance()
