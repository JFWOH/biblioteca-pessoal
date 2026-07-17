"""Worker que transforma um insight em flashcard pergunta/resposta via Ollama.

Item 1 do backlog UX: o insight do proativo entrava como PERGUNTA do card com
o verso vazio. Este worker pede ao LLM um par pergunta/resposta destilado; se
o Ollama estiver indisponível ou a resposta for inválida, o chamador usa o
fallback (insight no verso, pergunta em branco) — ADR-005.
"""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.study_prompts import build_flashcard_qa_prompt, parse_flashcard_qa

logger = logging.getLogger(__name__)


class FlashcardQAWorker(QThread):
    generated = pyqtSignal(str, str)  # front (pergunta), back (resposta)
    failed = pyqtSignal(str)          # motivo (chamador aplica o fallback)

    def __init__(self, text: str, ollama_url: str = "http://localhost:11434",
                 model: str | None = None, timeout_s: int = 30, parent=None):
        super().__init__(parent)
        self._text = text
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            prompt = build_flashcard_qa_prompt(self._text)
            if not prompt:
                self.failed.emit("insight vazio")
                return

            model = self._model
            if not model:
                # Resolução na thread do worker (rede). Flashcard P/R é tarefa
                # rápida/estruturada (§1.3 da revisão de engenharia).
                from src.core.graph.concept_extractor import resolve_llm_model
                from src.core.hardware_capability_service import HardwareCapabilityService
                model = resolve_llm_model(
                    self._ollama_url,
                    preferred=HardwareCapabilityService().get_model_for_task("fast"))
            if not model:
                self.failed.emit("nenhum modelo do Ollama disponível")
                return

            from src.core import ollama_client
            # think=False: reformatar um insight em P/R não precisa de
            # raciocínio — benchmark 2026-07-06: 9,8s → 3,3s no e4b.
            content = ollama_client.chat_once(
                self._ollama_url, model, [{"role": "user", "content": prompt}],
                response_format="json", temperature=0.2, num_predict=512,
                timeout_s=self._timeout_s, think=False,
            )

            qa = parse_flashcard_qa(content)
            if self._cancelled:
                return
            if qa is None:
                self.failed.emit("resposta do modelo inválida")
                return
            self.generated.emit(qa[0], qa[1])
        except Exception as exc:  # ADR-005: falha vira fallback, nunca crash
            logger.warning("FlashcardQAWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))


class HighlightCardsWorker(QThread):
    """Gera flashcards P/R a partir dos DESTAQUES de um livro, em lote (3.3).

    Um card por destaque: destila pergunta/resposta via LLM com ``think=False``
    — tarefa rápida/estruturada, igual ao ``FlashcardQAWorker`` (mantém o
    padrão existente). ADR-005: destaque que falhar entra com a pergunta em
    branco e o próprio destaque no verso, para o usuário editar no preview
    (nada se perde). Cancelável; emite progresso a cada card.
    """

    progress = pyqtSignal(int, int)   # feitos, total
    cards_ready = pyqtSignal(list)    # [{"front","back","source"}, ...]
    failed = pyqtSignal(str)

    MAX_HIGHLIGHTS = 40  # teto de segurança p/ não disparar dezenas de chamadas

    def __init__(self, highlights: list[str], ollama_url: str = "http://localhost:11434",
                 model: str | None = None, timeout_s: int = 30, parent=None):
        super().__init__(parent)
        self._highlights = [h for h in (highlights or []) if (h or "").strip()][: self.MAX_HIGHLIGHTS]
        self._ollama_url = ollama_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            model = self._model
            if not model:
                from src.core.graph.concept_extractor import resolve_llm_model
                from src.core.hardware_capability_service import HardwareCapabilityService
                model = resolve_llm_model(
                    self._ollama_url,
                    preferred=HardwareCapabilityService().get_model_for_task("fast"))
            total = len(self._highlights)
            cards: list[dict] = []
            for i, text in enumerate(self._highlights):
                if self._cancelled:
                    return
                card = self._one_card(text, model)
                if card:
                    cards.append(card)
                self.progress.emit(i + 1, total)
            if self._cancelled:
                return
            self.cards_ready.emit(cards)
        except Exception as exc:  # ADR-005: falha do lote nunca derruba a UI
            logger.warning("HighlightCardsWorker falhou: %s", exc)
            if not self._cancelled:
                self.failed.emit(str(exc))

    def _one_card(self, text: str, model: str | None) -> dict | None:
        clean = (text or "").strip()
        if not clean:
            return None
        prompt = build_flashcard_qa_prompt(clean)
        if not prompt:
            return None
        qa = None
        if model:
            try:
                from src.core import ollama_client
                # think=False: destilar P/R de um destaque é tarefa rápida.
                content = ollama_client.chat_once(
                    self._ollama_url, model, [{"role": "user", "content": prompt}],
                    response_format="json", temperature=0.2, num_predict=512,
                    timeout_s=self._timeout_s, think=False,
                )
                qa = parse_flashcard_qa(content)
            except Exception as exc:
                logger.warning("HighlightCardsWorker: card falhou (%s)", exc)
                qa = None
        if qa is None:
            # Fallback (ADR-005): destaque no verso, pergunta em branco.
            return {"front": "", "back": clean[:500], "source": clean[:120]}
        return {"front": qa[0], "back": qa[1], "source": clean[:120]}
