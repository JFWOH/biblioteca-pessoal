"""Worker que registra e inicializa os provedores TTS FORA da thread da GUI.

Achado B0 (perf de startup): construir o ``KokoroProvider`` dispara o
``import kokoro`` (que puxa torch/transformers) — medido em ~5,6 s. Feito
sincronamente no ``MainWindow.__init__``, esse import CONGELAVA a GUI antes de a
janela aparecer ("Não está respondendo") e era a origem dos warnings do torch
(rnn.py/weight_norm) no console do launch.

Mover ``auto_register_providers()`` + ``initialize()`` para uma ``QThread``
mantém a GUI responsiva no startup. O ``TTSRouter`` é o MESMO objeto (mutado
in-place): o ``ReaderView``, que recebe a referência no ``__init__`` da
MainWindow, enxerga os provedores assim que a thread termina — muito antes de o
usuário abrir um livro e clicar em Ouvir (a primeira narração exige abrir um
livro, o que leva bem mais do que os ~5,6 s do import).

ADR-006: o threading vive na camada GUI; o núcleo (``TTSRouter``) permanece
puro. ADR-005: falha ao inicializar o TTS degrada graciosamente (a narração
simplesmente fica indisponível), nunca derruba o app.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TTSInitWorker(QThread):
    """Registra e inicializa os provedores TTS em background (1 vez, no start)."""

    ready = pyqtSignal()  # emitido ao fim (sucesso OU falha graciosa)

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self._router = router

    def run(self):
        try:
            self._router.auto_register_providers()
            self._router.initialize()
        except Exception as exc:  # ADR-005: TTS indisponível não derruba o app
            logger.warning(
                "TTSInitWorker: falha ao inicializar provedores TTS (ignorado): %s",
                exc,
            )
        self.ready.emit()
