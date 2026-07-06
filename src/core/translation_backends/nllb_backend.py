"""Backend de tradução usando NLLB-200 offline.

Responsável por carregar o modelo de forma lazy e traduzir textos curtos/seleções.
"""
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Fim de sentença (. ! ? … ) seguido de espaço, ou quebra de linha — heurística
# simples e suficiente para não depender de bibliotecas de NLP.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|\n+")

class NLLBBackend:
    """Wrapper para inferência local com NLLB-200."""

    # Mapeamento simplificado de ISO para FLORES-200 (usado pelo NLLB)
    LANG_MAP = {
        "en": "eng_Latn",
        "pt": "por_Latn",
        "es": "spa_Latn",
    }

    def __init__(self, model_id: str = "facebook/nllb-200-distilled-600M"):
        self.model_id = model_id
        self._model = None
        self._tokenizer = None
        self._is_loaded = False
        
        # O NLLB traduz bem até 512 tokens. Vamos travar num limite de caracteres seguro.
        self.max_input_length = 2000 

    def is_loaded(self) -> bool:
        return self._is_loaded

    @staticmethod
    def _select_device(torch) -> str:
        """Escolhe 'cuda' apenas se a GPU for suportada por esta build do torch.

        GPUs novas (ex.: Blackwell/sm_120) são detectadas por
        torch.cuda.is_available(), mas não têm kernels compilados nesta build,
        o que quebra a inferência em runtime. Nesse caso caímos para CPU
        (degradação graciosa, ADR-005).
        """
        if not torch.cuda.is_available():
            return "cpu"
        try:
            major, minor = torch.cuda.get_device_capability()
            sm = f"sm_{major}{minor}"
            if sm not in torch.cuda.get_arch_list():
                logger.warning(
                    f"GPU {sm} não suportada por esta build do torch; usando CPU."
                )
                return "cpu"
        except Exception:
            return "cpu"
        return "cuda"

    def _load_model_lazy(self):
        """Carrega o modelo apenas quando a primeira tradução for solicitada."""
        if self._is_loaded:
            return

        import os
        # O provedor Kokoro força HF_HUB_OFFLINE=1 no processo inteiro (para evitar
        # travas de rede no load dele), o que bloqueava o download do NLLB na primeira
        # vez — quebrando a tradução. Liberamos a rede apenas ao redor deste load e
        # restauramos o valor anterior em seguida (não vaza o modo online).
        prev_offline = os.environ.get("HF_HUB_OFFLINE")
        os.environ["HF_HUB_OFFLINE"] = "0"
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import torch

            logger.info(f"Carregando tokenizer {self.model_id}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)

            logger.info(f"Carregando modelo {self.model_id}...")
            device = self._select_device(torch)

            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id).to(device)

            self._device = device
            self._is_loaded = True
            logger.info(f"NLLB-200 carregado com sucesso no device: {device}")
        except ImportError as e:
            logger.error("Bibliotecas transformers/torch ausentes para tradução offline.")
            raise RuntimeError("Dependências ausentes. Certifique-se de que 'transformers' e 'torch' estão instalados.") from e
        except Exception as e:
            logger.error(f"Falha ao carregar modelo NLLB: {e}")
            raise RuntimeError(f"Falha ao carregar modelo de tradução: {e}") from e
        finally:
            if prev_offline is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = prev_offline

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Quebra o texto em sentenças (heurística: pontuação final + quebra de linha).

        Sem isso, textos longos (uma página inteira) vão numa única chamada ao
        modelo com truncation=True/max_length=512 — o texto trunca e o NLLB
        degenera em repetição (bug relatado: tradução de página inteira virava
        loop de texto repetido).
        """
        parts = _SENTENCE_SPLIT_RE.split(text.strip())
        return [p.strip() for p in parts if p and p.strip()]

    @staticmethod
    def _batch_sentences(sentences: list[str], max_chars: int = 1400) -> list[str]:
        """Empacota sentenças em lotes sob um orçamento de caracteres.

        Guloso: acumula sentenças num lote até estourar o orçamento, então
        fecha o lote e começa outro. Uma sentença sozinha maior que o
        orçamento vira seu próprio lote (nunca quebra no meio da sentença —
        isso reintroduziria o problema de truncamento no meio da frase).
        """
        batches: list[str] = []
        current: list[str] = []
        current_len = 0
        for sent in sentences:
            sent_len = len(sent)
            if current and current_len + 1 + sent_len > max_chars:
                batches.append(" ".join(current))
                current, current_len = [], 0
            current.append(sent)
            current_len += sent_len + (1 if len(current) > 1 else 0)
        if current:
            batches.append(" ".join(current))
        return batches

    def _translate_one_batch(self, batch: str, src_nllb: str, tgt_nllb: str) -> str:
        """Traduz UM lote (já dentro do orçamento de caracteres) via NLLB.

        max_length=512 permanece como rede de segurança (defesa em
        profundidade) — o chunking por sentenças evita estourá-lo na prática.
        """
        self._tokenizer.src_lang = src_nllb
        inputs = self._tokenizer(batch, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(tgt_nllb)
        outputs = self._model.generate(
            **inputs,
            forced_bos_token_id=forced_bos_token_id,
            max_length=512,
        )
        return self._tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]

    def translate(self, text: str, src_lang: str = "en", tgt_lang: str = "pt") -> str:
        """
        Traduz um trecho de texto, fatiado por sentenças em lotes menores.

        :param text: Texto original a traduzir (pode ser uma página inteira).
        :param src_lang: Código ISO simples de origem (ex: 'en').
        :param tgt_lang: Código ISO simples de destino (ex: 'pt').
        :return: Texto traduzido (lotes reunidos na ordem original).
        """
        # Limpa artefatos de extração de PDF (capitulares "W ELCOME", títulos
        # "C H A P T E R", hifenização de quebra) — o NLLB "traduz" o ruído e
        # produz lacunas/trechos em inglês. Inofensivo em texto já limpo.
        from src.core.translation_backends.text_cleanup import clean_source_text
        text = clean_source_text(text)
        if not text:
            return ""

        if len(text) > self.max_input_length:
            text = text[:self.max_input_length]
            logger.warning(f"Texto muito longo truncado para {self.max_input_length} caracteres.")

        self._load_model_lazy()

        src_nllb = self.LANG_MAP.get(src_lang, "eng_Latn")
        tgt_nllb = self.LANG_MAP.get(tgt_lang, "por_Latn")

        sentences = self._split_sentences(text)
        if not sentences:
            return ""
        batches = self._batch_sentences(sentences)

        try:
            translated_batches = [
                self._translate_one_batch(batch, src_nllb, tgt_nllb) for batch in batches
            ]
            return " ".join(translated_batches)
        except Exception as e:
            logger.error(f"Erro durante a inferência da tradução: {e}")
            raise RuntimeError(f"Erro na tradução: {e}") from e
