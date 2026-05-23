"""QThread worker para pull (download) de modelos Ollama."""

from __future__ import annotations

import json
import urllib.request
from typing import Iterator

from PyQt6.QtCore import QThread, pyqtSignal


class ModelPullWorker(QThread):
    """Faz pull de um modelo Ollama em background com progresso em streaming.

    Signals:
        progress_updated(int, int, str):
            (bytes_completados, bytes_totais, status_message)
        pull_complete(bool, str): (sucesso, nome_do_modelo)
        error_occurred(str): Mensagem de erro.
    """

    progress_updated = pyqtSignal(int, int, str)  # completed, total, status
    pull_complete = pyqtSignal(bool, str)          # success, model_name
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        ollama_url: str,
        model_name: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._ollama_url = ollama_url.rstrip("/")
        self._model_name = model_name

    def run(self) -> None:
        try:
            payload = json.dumps({
                "name": self._model_name,
                "stream": True,
            }).encode()

            req = urllib.request.Request(
                f"{self._ollama_url}/api/pull",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=600) as resp:
                for line in resp:
                    if self.isInterruptionRequested():
                        self.pull_complete.emit(False, self._model_name)
                        return
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue

                    status = chunk.get("status", "")
                    completed = chunk.get("completed", 0)
                    total = chunk.get("total", 0)
                    self.progress_updated.emit(completed, total, status)

                    if status == "success":
                        self.pull_complete.emit(True, self._model_name)
                        return

            self.pull_complete.emit(True, self._model_name)

        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.pull_complete.emit(False, self._model_name)
