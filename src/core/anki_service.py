"""
Serviço Core para comunicação com o AnkiConnect.
"""
import json
import logging
import os
import urllib.request
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class AnkiService:
    def __init__(self, endpoint: str = "http://127.0.0.1:8765"):
        self.endpoint = endpoint
        self.fallback_file = os.path.join("data", "flashcards_fallback.jsonl")
        os.makedirs("data", exist_ok=True)

    def _invoke(self, action: str, **params) -> Dict[str, Any]:
        """Faz a requisição HTTP local para o AnkiConnect."""
        request_data = {"action": action, "version": 6}
        if params:
            request_data["params"] = params

        payload = json.dumps(request_data).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                response = json.loads(resp.read())
                
            if len(response) != 2:
                raise Exception("A resposta tem um número inesperado de campos")
            if "error" not in response:
                raise Exception("A resposta está sem o campo de erro")
            if "result" not in response:
                raise Exception("A resposta está sem o campo de resultado")
            if response["error"] is not None:
                raise Exception(response["error"])
                
            return response["result"]
            
        except urllib.error.URLError as e:
            raise ConnectionError(f"Não foi possível conectar ao AnkiConnect: {e}")
        except Exception as e:
            raise e

    def is_available(self) -> bool:
        """Verifica se o AnkiConnect está respondendo."""
        try:
            version = self._invoke("version")
            return version == 6
        except Exception:
            return False

    def get_deck_names(self) -> List[str]:
        """Obtém a lista de decks no Anki."""
        try:
            return self._invoke("deckNames")
        except Exception as e:
            logger.warning(f"Falha ao obter decks: {e}")
            return ["Default"]

    def add_basic_note(self, deck_name: str, front: str, back: str, tags: List[str] = None) -> Optional[int]:
        """
        Adiciona uma nota básica. Retorna o ID da nota se sucesso, ou salva no fallback se falhar.
        Levanta exceção apenas se for um erro crítico não relacionado à conectividade (ex: erro de modelo).
        """
        if not tags:
            tags = ["biblioteca-pessoal"]
            
        note = {
            "deckName": deck_name,
            "modelName": "Basic",
            "fields": {
                "Front": front,
                "Back": back
            },
            "tags": tags
        }

        try:
            note_id = self._invoke("addNote", note=note)
            logger.info(f"Nota adicionada com sucesso no Anki (ID: {note_id})")
            return note_id
        except ConnectionError:
            self._save_to_fallback(deck_name, front, back, tags)
            logger.info("AnkiConnect offline. Nota salva no fallback local.")
            return None
        except Exception as e:
            err_str = str(e)
            if "cannot create note because it is empty" in err_str:
                raise ValueError("A nota não pode estar vazia.")
            # Fallback for other non-critical issues might be needed, but we save to be safe
            self._save_to_fallback(deck_name, front, back, tags)
            logger.warning(f"Erro ao adicionar nota ({err_str}). Salva no fallback local.")
            return None

    def _save_to_fallback(self, deck_name: str, front: str, back: str, tags: List[str]):
        """Salva a nota em um arquivo local caso o Anki não esteja disponível."""
        fallback_data = {
            "timestamp": datetime.now().isoformat(),
            "deckName": deck_name,
            "modelName": "Basic",
            "front": front,
            "back": back,
            "tags": tags
        }
        with open(self.fallback_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(fallback_data, ensure_ascii=False) + "\n")
