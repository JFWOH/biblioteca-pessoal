"""Testes do pull automático de modelos do Ollama (onboarding sem terminal)."""
import io
import json

from src.core.ollama_installer import OllamaInstaller


class _FakeStreamResp(io.BytesIO):
    """Resposta streaming do /api/pull: iterável linha a linha (JSON lines)."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _stream(lines: list[dict]):
    body = b"\n".join(json.dumps(ln).encode() for ln in lines) + b"\n"

    def _fake(req, timeout=0):
        return _FakeStreamResp(body)

    return _fake


def test_pull_model_success_with_progress(monkeypatch):
    lines = [
        {"status": "pulling manifest"},
        {"status": "downloading", "total": 1000, "completed": 250},
        {"status": "downloading", "total": 1000, "completed": 1000},
        {"status": "success"},
    ]
    monkeypatch.setattr("urllib.request.urlopen", _stream(lines))
    progress = []
    ok = OllamaInstaller.pull_model("gemma4:e4b",
                                    progress_cb=lambda p, m: progress.append((p, m)))
    assert ok is True
    pcts = [p for p, _ in progress]
    assert 25 in pcts and 100 in pcts  # progresso real reportado
    assert any("gemma4:e4b" in m for _, m in progress)


def test_pull_model_error_chunk_returns_false(monkeypatch):
    lines = [{"status": "pulling manifest"}, {"error": "model not found"}]
    monkeypatch.setattr("urllib.request.urlopen", _stream(lines))
    assert OllamaInstaller.pull_model("inexistente:1b") is False


def test_pull_model_network_failure_returns_false(monkeypatch):
    def _boom(req, timeout=0):
        raise OSError("daemon fora do ar")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert OllamaInstaller.pull_model("gemma4:e4b") is False


def test_list_installed_models(monkeypatch):
    body = json.dumps({"models": [{"name": "gemma4:e4b"}, {"name": "bge-m3:latest"}]}).encode()

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout=0: _Resp(body))
    assert OllamaInstaller.list_installed_models() == ["gemma4:e4b", "bge-m3:latest"]


def test_list_installed_models_failure_is_empty(monkeypatch):
    def _boom(req, timeout=0):
        raise OSError("x")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert OllamaInstaller.list_installed_models() == []


# ── Workers (Qt, sem daemon real) ─────────────────────────────────────

def test_install_worker_pulls_recommended_models(qtbot, monkeypatch):
    """Após instalar+daemon OK, o worker baixa LLM recomendado + embeddings."""
    from src.gui.workers.install_worker import OllamaInstallWorker

    pulled = []
    monkeypatch.setattr(OllamaInstaller, "download", lambda *a, **k: None)
    monkeypatch.setattr(OllamaInstaller, "install", lambda *a, **k: True)
    monkeypatch.setattr(OllamaInstaller, "start_daemon", lambda: True)
    monkeypatch.setattr(OllamaInstaller, "verify", lambda: True)
    monkeypatch.setattr(
        OllamaInstaller, "pull_model",
        lambda model, progress_cb=None, timeout=0: pulled.append(model) or True)
    monkeypatch.setattr("time.sleep", lambda s: None)

    from src.core.hardware_capability_service import HardwareCapabilityService
    monkeypatch.setattr(HardwareCapabilityService, "get_recommended_llm_model",
                        lambda self: "gemma4:e4b")

    worker = OllamaInstallWorker()
    results = []
    worker.install_complete.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()  # síncrono no teste

    assert pulled == ["gemma4:e4b", "bge-m3"]
    assert results and results[0][0] is True
    assert "modelos de IA baixados" in results[0][1]


def test_install_worker_pull_failure_still_completes_with_warning(qtbot, monkeypatch):
    from src.gui.workers.install_worker import OllamaInstallWorker

    monkeypatch.setattr(OllamaInstaller, "download", lambda *a, **k: None)
    monkeypatch.setattr(OllamaInstaller, "install", lambda *a, **k: True)
    monkeypatch.setattr(OllamaInstaller, "start_daemon", lambda: True)
    monkeypatch.setattr(OllamaInstaller, "verify", lambda: True)
    monkeypatch.setattr(OllamaInstaller, "pull_model",
                        lambda model, progress_cb=None, timeout=0: False)
    monkeypatch.setattr("time.sleep", lambda s: None)

    worker = OllamaInstallWorker()
    results = []
    worker.install_complete.connect(lambda ok, msg: results.append((ok, msg)))
    worker.run()

    assert results and results[0][0] is True  # instalação em si teve sucesso
    assert "não terminou" in results[0][1]    # mas avisa sobre os modelos


def test_model_pull_worker_reports_progress_and_result(qtbot, monkeypatch):
    from src.gui.workers.install_worker import OllamaModelPullWorker

    pulled = []
    monkeypatch.setattr(
        OllamaInstaller, "pull_model",
        lambda model, progress_cb=None, timeout=0: pulled.append(model) or True)

    worker = OllamaModelPullWorker(["gemma4:e4b", "bge-m3"])
    messages, results = [], []
    worker.progress_updated.connect(messages.append)
    worker.finished_pull.connect(results.append)
    worker.run()

    assert pulled == ["gemma4:e4b", "bge-m3"]
    assert results == [True]
    assert any("gemma4:e4b" in m for m in messages)
