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
            for _ in range(6):  # até 6 tentativas (6 segundos)
                time.sleep(1)
                if OllamaInstaller.verify():
                    self.install_complete.emit(True, "Ollama instalado e iniciado com sucesso!")
                    return

            self.install_complete.emit(
                True,
                "Ollama instalado! Pode ser necessário reiniciar o aplicativo.",
            )

        except Exception as exc:
            self.install_complete.emit(False, f"Erro durante a instalação: {exc}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
