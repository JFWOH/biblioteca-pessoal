from PyQt6.QtCore import QThread, pyqtSignal
from typing import Optional
from src.core.api_clients import MetadataFetcher

class MetadataWorker(QThread):
    """QThread para buscar metadados e capas na web sem travar a interface principal."""
    
    # Sinais emitidos pelo worker
    metadata_found = pyqtSignal(dict)           # Emite os metadados encontrados
    cover_downloaded = pyqtSignal(bytes)        # Emite os bytes da capa baixada
    error_occurred = pyqtSignal(str)            # Emite mensagem de erro, se houver
    finished_work = pyqtSignal()                # Emite quando concluir
    
    def __init__(self, title: str, author: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.title = title
        self.author = author
        
    def run(self):
        fetcher = MetadataFetcher()
        try:
            metadata = fetcher.search_book(self.title, self.author)
            
            if not metadata:
                self.error_occurred.emit("Nenhum metadado encontrado para este livro.")
                return
                
            self.metadata_found.emit(metadata)
            
            cover_url = metadata.get("cover_url")
            if cover_url:
                cover_bytes = fetcher.download_cover(cover_url)
                if cover_bytes:
                    self.cover_downloaded.emit(cover_bytes)
                    
        except Exception as e:
            self.error_occurred.emit(f"Erro durante a busca: {str(e)}")
        finally:
            fetcher.close()
            self.finished_work.emit()
