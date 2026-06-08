"""
Worker assíncrono para buscar observações proativas via API do Ollama.
"""
import json
import logging
import urllib.request
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class ProactiveWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, model: str, page_text: str, ollama_url: str = "http://localhost:11434"):
        super().__init__()
        self.model = model
        self.page_text = page_text
        self.ollama_url = ollama_url

    def run(self):
        if not self.model:
            self.error.emit("Nenhum modelo suportado pelo hardware.")
            return

        prompt = (
            "Você é um Assistente Proativo de Leitura discreto e útil. "
            "Sua tarefa é analisar o trecho fornecido e gerar UMA ÚNICA observação curta (1 a 4 frases). "
            "A observação DEVE ser útil, como dar contexto externo, levantar uma hipótese interpretativa ou notar algo interessante. "
            "REGRA CRÍTICA: NÃO dê spoiler ou preveja o futuro. Comente apenas sobre o que está no texto agora. "
            "Responda APENAS com um objeto JSON estrito com as seguintes chaves:\n"
            '- "tipo": (deve ser exatamente "Observação do texto", "Contexto externo" ou "Hipótese interpretativa")\n'
            '- "confianca": (deve ser "Alta", "Média" ou "Baixa")\n'
            '- "texto": (A observação em si, 1 a 4 frases)\n\n'
            f"Trecho para análise:\n{self.page_text}"
        )

        messages = [{"role": "user", "content": prompt}]
        
        payload_dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 4096}
        }

        payload = json.dumps(payload_dict).encode("utf-8")
        endpoint = f"{self.ollama_url.rstrip('/')}/api/chat"
        
        try:
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw_resp = resp.read()
                data = json.loads(raw_resp)
            
            content = data.get("message", {}).get("content", "").strip()
            
            # DEBUG
            if not content:
                logger.error(f"Ollama Raw Response: {raw_resp.decode('utf-8', errors='ignore')}")
            
            # Limpa formatação markdown se o modelo ignorou a restrição
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            if not content:
                raise ValueError("Resposta vazia da IA (conteúdo em branco)")
            
            import re
            # Se ainda houver lixo antes/depois, tenta achar o primeiro '{' e último '}'
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx+1]
                
            obs = json.loads(content)
            
            if "tipo" not in obs or "confianca" not in obs or "texto" not in obs:
                raise ValueError("JSON incompleto")
                
            self.finished.emit(obs)
            
        except Exception as exc:
            logger.error(f"Erro no ProactiveWorker: {exc}")
            self.error.emit(str(exc))
