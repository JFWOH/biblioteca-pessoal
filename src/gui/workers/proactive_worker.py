"""
Worker assíncrono para buscar observações proativas via API do Ollama.
"""
import json
import logging
from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

class ProactiveWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, model: str, page_text: str, ollama_url: str = "http://localhost:11434",
                 parent=None, search_fn=None, book_id=None, memory_block: str = "",
                 preference_block: str = ""):
        super().__init__(parent)
        self.model = model
        self.page_text = page_text
        self.ollama_url = ollama_url
        # Cross-reference proativo: busca o conceito em outros livros (injetada).
        self.search_fn = search_fn
        self.book_id = book_id
        # Continuidade (Fase 5): bloco com o que o agente já disse neste livro.
        self.memory_block = memory_block
        # Aprendizado (Fase 6): tipos de observação que o leitor costuma dispensar.
        self.preference_block = preference_block
        self._is_cancelled = False

    def cancel(self):
        """Cancelamento cooperativo: o resultado em andamento será descartado.

        Não interrompe a requisição HTTP em curso (que termina por conta própria
        ou por timeout), mas garante que nenhum sinal seja emitido após o
        cancelamento — evitando o uso inseguro de QThread.terminate().
        """
        self._is_cancelled = True

    def _build_prompt(self) -> str:
        """Monta o prompt único enviado ao modelo."""
        from src.core.proactive_continuity import trim_page_excerpt

        # Continuidade (Fase 5) e aprendizado (Fase 6) entram entre as regras
        # e o trecho — sem os blocos, o prompt é idêntico ao anterior.
        preference = f"{self.preference_block}\n\n" if self.preference_block else ""
        memory = f"{self.memory_block}\n\n" if self.memory_block else ""
        return (
            "Você é um Assistente Proativo de Leitura discreto e útil. "
            "Sua tarefa é analisar o trecho fornecido e gerar UMA ÚNICA observação curta (1 a 4 frases). "
            "A observação DEVE ser útil, como dar contexto externo, levantar uma hipótese interpretativa ou notar algo interessante. "
            "REGRA CRÍTICA: NÃO dê spoiler ou preveja o futuro. Comente apenas sobre o que está no texto agora. "
            "Responda APENAS com um objeto JSON estrito com as seguintes chaves:\n"
            '- "tipo": (deve ser exatamente "Observação do texto", "Contexto externo" ou "Hipótese interpretativa")\n'
            '- "confianca": (deve ser "Alta", "Média" ou "Baixa")\n'
            '- "texto": (A observação em si, 1 a 4 frases)\n\n'
            f"{preference}"
            f"{memory}"
            f"Trecho para análise:\n{trim_page_excerpt(self.page_text)}"
        )

    def _chat_kwargs(self) -> dict:
        """Parâmetros da chamada — fonte única do payload E da requisição.

        Antes o worker montava o dict de ``/api/chat`` à mão e depois repassava
        pedaços dele para ``chat_once``: os dois podiam divergir (``keep_alive``
        já era montado e descartado). Agora ambos saem daqui.
        """
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": self._build_prompt()}],
            # Structured output do Ollama: garante JSON válido na resposta,
            # tornando o parsing robusto sem depender de limpeza de markdown.
            "response_format": "json",
            "temperature": 0.2,
            # num_predict é um TETO, não uma reserva: o modelo para em done=stop ao
            # terminar (gera só o necessário). Modelos de raciocínio (ex.: gemma4:e4b)
            # consomem tokens "pensando" ANTES do content; um teto baixo (256)
            # estourava no meio do raciocínio e devolvia content vazio ("Resposta
            # vazia da IA"). Mantemos o raciocínio (qualidade) com teto folgado.
            "num_predict": 4096,
            # NUNCA passar think=False aqui: o proativo é tarefa profunda e
            # mantém o raciocínio por decisão de qualidade (lição do commit
            # a1cc513, reafirmada na Onda Q). Omitir = default do modelo.
        }

    def _build_payload(self) -> dict:
        """Payload real de ``/api/chat`` (mesma função pública que chat_once usa)."""
        from src.core.ollama_client import build_chat_payload
        kwargs = self._chat_kwargs()
        return build_chat_payload(
            kwargs["model"], kwargs["messages"], stream=False,
            response_format=kwargs["response_format"],
            temperature=kwargs["temperature"],
            num_predict=kwargs["num_predict"],
        )

    def run(self):
        if not self.model:
            self.error.emit("Nenhum modelo suportado pelo hardware.")
            return

        try:
            from src.core import ollama_client
            kwargs = self._chat_kwargs()
            content = ollama_client.chat_once(
                self.ollama_url, kwargs["model"], kwargs["messages"],
                response_format=kwargs["response_format"],
                temperature=kwargs["temperature"],
                num_predict=kwargs["num_predict"],
                timeout_s=45,
            )

            if not content:
                logger.error("Ollama respondeu com content vazio para o proativo.")

            # Rede de segurança: limpa formatação markdown caso o modelo a inclua
            # mesmo com format=json.
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            if not content:
                raise ValueError("Resposta vazia da IA (conteúdo em branco)")

            # Se ainda houver lixo antes/depois, tenta achar o primeiro '{' e último '}'
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx + 1]

            obs = json.loads(content)

            if "tipo" not in obs or "confianca" not in obs or "texto" not in obs:
                raise ValueError("JSON incompleto")

            # Enriquecimento: conexão com outros livros da biblioteca (cross-reference).
            if self.search_fn is not None:
                try:
                    from src.core.proactive_cross_reference import format_cross_reference
                    hits = self.search_fn(self.page_text)
                    note = format_cross_reference(hits, self.book_id)
                    if note:
                        obs["texto"] = (obs.get("texto", "") + "\n\n" + note).strip()
                except Exception as exc:
                    logger.warning(f"Cross-reference proativo falhou (ignorado): {exc}")

            if self._is_cancelled:
                return  # usuário avançou de página/cancelou: descarta o resultado

            self.finished.emit(obs)

        except Exception as exc:
            logger.error(f"Erro no ProactiveWorker: {exc}")
            if self._is_cancelled:
                return
            self.error.emit(str(exc))
