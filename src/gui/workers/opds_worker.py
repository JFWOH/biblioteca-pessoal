import uvicorn
import asyncio
from PyQt6.QtCore import QThread, pyqtSignal

class OPDSWorker(QThread):
    """QThread que executa o servidor FastAPI (OPDS) via Uvicorn."""
    
    server_started = pyqtSignal(str)  # Emite a URL do servidor
    server_stopped = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, host="0.0.0.0", port=8000, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.server = None
        
    def run(self):
        from src.core.opds_server import app
        
        # Configura o uvicorn para rodar silenciosamente ou de forma gerenciada
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)
        
        try:
            # Emite o sinal dizendo que iniciou (não exato, mas logo antes de dar o bloqueio)
            self.server_started.emit(f"http://{self.host}:{self.port}/opds")
            
            # Loop do asyncio para rodar o Uvicorn dentro da thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.server.serve())
            
            self.server_stopped.emit()
        except Exception as e:
            self.error_occurred.emit(f"Erro no Servidor OPDS: {e}")
            
    def stop(self):
        """Para o servidor se ele estiver rodando."""
        if self.server:
            self.server.should_exit = True
