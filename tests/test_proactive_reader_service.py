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
             patch.object(svc.trigger_engine, "should_trigger", return_value=True):
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
             patch.object(svc.trigger_engine, "should_trigger", return_value=True):
            svc.process_page_context("Texto longo " * 30, 10)

        assert MockWorker.call_count == 1
        MockWorker.return_value.start.assert_called_once()
