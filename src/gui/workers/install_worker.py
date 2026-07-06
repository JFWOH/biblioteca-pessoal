"""QThread worker para download e instalação do Ollama em background."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.ollama_installer import OllamaInstaller


class OllamaInstallWorker(QThread):
    """Executa o download e instalação do Ollama fora da thread principal.

    Signals:
        progress_updated(int, str): Progresso percentual + mensagem.
        install_complete(bool, str): (sucesso, mensagem_final).
    """

    progress_updated = pyqtSignal(int, str)   # percent, message
    install_complete = pyqtSignal(bool, str)  # success, message

    def run(self) -> None:
        """Baixa, instala e verifica o Ollama."""
        try:
            plat = OllamaInstaller.detect_platform()
            ext = ".exe" if plat == "windows" else (".sh" if plat == "linux" else ".zip")

            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, prefix="ollama_setup"
            ) as tmp:
                tmp_path = Path(tmp.name)

            # 1. Download
            def on_progress(pct: int, msg: str) -> None:
                self.progress_updated.emit(pct, msg)

            self.progress_updated.emit(0, "Iniciando download do Ollama…")
            OllamaInstaller.download(tmp_path, progress_cb=on_progress)

            if self.isInterruptionRequested():
                self.install_complete.emit(False, "Cancelado pelo usuário.")
                return

            # 2. Instalação
            self.progress_updated.emit(100, "Instalando Ollama…")
            success = OllamaInstaller.install(tmp_path)

            if not success:
                self.install_complete.emit(
                    False,
                    "Não foi possível instalar automaticamente.\n"
                    "Acesse https://ollama.com para instalar manualmente.",
                )
                return

            # 3. Inicia daemon
            self.progress_updated.emit(100, "Iniciando o daemon Ollama…")
            OllamaInstaller.start_daemon()

            # 4. Verifica
            import time
            daemon_ok = False
            for _ in range(6):  # até 6 tentativas (6 segundos)
                time.sleep(1)
                if OllamaInstaller.verify():
                    daemon_ok = True
                    break

            if not daemon_ok:
                self.install_complete.emit(
                    True,
                    "Ollama instalado! Pode ser necessário reiniciar o aplicativo.",
                )
                return

            # 5. Modelos recomendados pelo hardware (LLM leve por padrão;
            #    maior só se a GPU comportar) + embeddings do RAG. Sem isto,
            #    o runtime instala mas o assistente fica sem cérebro.
            if self._pull_recommended_models():
                self.install_complete.emit(
                    True, "Ollama instalado e modelos de IA baixados com sucesso!")
            else:
                self.install_complete.emit(
                    True,
                    "Ollama instalado! O download dos modelos de IA não terminou — "
                    "o app tentará novamente quando o assistente for usado.",
                )

        except Exception as exc:
            self.install_complete.emit(False, f"Erro durante a instalação: {exc}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _pull_recommended_models(self) -> bool:
        """Baixa o LLM recomendado pelo hardware + o modelo de embeddings."""
        from src.core.hardware_capability_service import HardwareCapabilityService

        hw = HardwareCapabilityService()
        models = [hw.get_recommended_llm_model(), HardwareCapabilityService.EMBED_MODEL]
        all_ok = True
        for model in models:
            if self.isInterruptionRequested():
                return False
            self.progress_updated.emit(0, f"Baixando modelo {model}…")
            ok = OllamaInstaller.pull_model(
                model,
                progress_cb=lambda pct, msg: self.progress_updated.emit(pct, msg),
            )
            all_ok = all_ok and ok
        return all_ok


class OllamaModelPullWorker(QThread):
    """Baixa os modelos recomendados quando o daemon já existe sem modelos.

    Cobre quem instalou o Ollama por fora (ou pulou o wizard): o app detecta
    a ausência de modelos no startup e puxa em background, com avisos na
    statusbar — sem terminal, sem download manual.
    """

    progress_updated = pyqtSignal(str)      # mensagem para a statusbar
    finished_pull = pyqtSignal(bool)        # True = todos os modelos baixados

    def __init__(self, models: list[str], parent=None):
        super().__init__(parent)
        self._models = models

    def run(self) -> None:
        all_ok = True
        for model in self._models:
            if self.isInterruptionRequested():
                self.finished_pull.emit(False)
                return
            self.progress_updated.emit(f"🤖 Baixando modelo de IA {model}…")
            ok = OllamaInstaller.pull_model(
                model,
                progress_cb=lambda pct, msg: self.progress_updated.emit(f"🤖 {msg}"),
            )
            all_ok = all_ok and ok
        self.finished_pull.emit(all_ok)
