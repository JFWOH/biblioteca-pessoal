"""Testes do ProactiveReaderService: conformidade ADR-006 e política skip-if-busy."""
import importlib

import pytest
from unittest.mock import patch


def test_service_moved_out_of_core():
    """ADR-006: o serviço (QObject + QThread) não pode mais viver em src/core."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.core.proactive_reader_service")
    # E deve existir na camada GUI:
    importlib.import_module("src.gui.proactive_reader_service")


def test_service_disabled_does_nothing(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Desligado"
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        svc.process_page_context("Texto " * 50, 5)
        MockWorker.assert_not_called()


def test_service_skips_when_worker_running(qtbot):
    """skip-if-busy: enquanto uma observação é gerada, não cria um segundo worker
    (substitui o antigo QThread.terminate() inseguro)."""
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
             patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
             patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
            svc.process_page_context("Texto longo " * 30, 10)
            assert MockWorker.call_count == 1  # primeiro disparo cria o worker

            svc.process_page_context("Outro texto " * 30, 12)
            assert MockWorker.call_count == 1  # worker ocupado → pulou, sem novo worker


def test_service_creates_worker_when_idle(qtbot):
    """Com worker ocioso e disparo válido, cria e inicia um novo worker."""
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
             patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
             patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
            svc.process_page_context("Texto longo " * 30, 10)

        assert MockWorker.call_count == 1
        MockWorker.return_value.start.assert_called_once()


# ── Confiabilidade: resolução de modelo + erros visíveis ──────────────────────

def test_resolve_model_prefers_fast_e4b(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["gemma4:12b", "gemma4:e4b", "mistral:latest"]):
        # proativo favorece velocidade → e4b mesmo com o tier pedindo 12b
        assert svc._resolve_model("gemma4:12b") == "gemma4:e4b"


def test_resolve_model_falls_back_to_tier(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["gemma4:12b", "mistral:latest"]):
        # e4b não instalado → usa o gemma4 instalado (12b)
        assert svc._resolve_model("gemma4:12b") == "gemma4:12b"


def test_resolve_model_last_resort_any_installed(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["phi3:latest"]):
        assert svc._resolve_model("gemma4:12b") == "phi3:latest"


def test_resolve_model_none_when_nothing_installed(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=[]):
        assert svc._resolve_model("gemma4:12b") is None


def test_process_emits_error_when_no_models(qtbot):
    """Antes a falha era silenciosa; agora o usuário recebe um aviso."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    errors = []
    svc.error_occurred.connect(errors.append)
    with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:12b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=[]):
        svc.process_page_context("Texto longo " * 30, 5)
    assert len(errors) == 1
    assert "modelo" in errors[0].lower()


def test_process_uses_resolved_model(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker, \
         patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:12b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5)
        MockWorker.assert_called_once()
        assert MockWorker.call_args[0][0] == "gemma4:e4b"  # modelo resolvido (rápido)


def test_process_passes_search_fn_and_book_id(qtbot):
    """O cross-ref injetado e o book_id são repassados ao worker."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    fn = lambda text: []
    svc.set_cross_reference(fn)
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker, \
         patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        assert MockWorker.call_args.kwargs.get("book_id") == 7
        assert MockWorker.call_args.kwargs.get("search_fn") is fn
