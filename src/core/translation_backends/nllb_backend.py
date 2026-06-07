"""Backend de tradução usando NLLB-200 offline.

Responsável por carregar o modelo de forma lazy e traduzir textos curtos/seleções.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

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

    def _load_model_lazy(self):
        """Carrega o modelo apenas quando a primeira tradução for solicitada."""
        if self._is_loaded:
            return

        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import torch
            
            logger.info(f"Carregando tokenizer {self.model_id}...")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            
            logger.info(f"Carregando modelo {self.model_id}...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            
            self._model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_id, 
                dtype=torch.float32,
                low_cpu_mem_usage=True
            ).to(device)

            self._device = device
            self._is_loaded = True
            logger.info(f"NLLB-200 carregado com sucesso no device: {device}")
        except ImportError as e:
            logger.error("Bibliotecas transformers/torch ausentes para tradução offline.")
            raise RuntimeError("Dependências ausentes. Certifique-se de que 'transformers' e 'torch' estão instalados.") from e
        except Exception as e:
            logger.error(f"Falha ao carregar modelo NLLB: {e}")
            raise RuntimeError(f"Falha ao carregar modelo de tradução: {e}") from e

    def translate(self, text: str, src_lang: str = "en", tgt_lang: str = "pt") -> str:
        """
        Traduz um trecho de texto.
        :param text: Texto original a traduzir.
        :param src_lang: Código ISO simples de origem (ex: 'en').
        :param tgt_lang: Código ISO simples de destino (ex: 'pt').
        :return: Texto traduzido.
        """
        text = text.strip()
        if not text:
            return ""

        if len(text) > self.max_input_length:
            text = text[:self.max_input_length]
            logger.warning(f"Texto muito longo truncado para {self.max_input_length} caracteres.")

        self._load_model_lazy()

        src_nllb = self.LANG_MAP.get(src_lang, "eng_Latn")
        tgt_nllb = self.LANG_MAP.get(tgt_lang, "por_Latn")

        try:
            # O NLLB requer que mudemos a lingua fonte no tokenizer antes
            self._tokenizer.src_lang = src_nllb
            
            inputs = self._tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            inputs = {k: v.to(self._device) for k, v in inputs.items()}
            
            # Obtém o token ID de idioma destino corretamente para o NLLB
            forced_bos_token_id = self._tokenizer.convert_tokens_to_ids(tgt_nllb)
            
            outputs = self._model.generate(
                **inputs,
                forced_bos_token_id=forced_bos_token_id,
                max_length=512
            )
            
            translated_text = self._tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
            return translated_text
            
        except Exception as e:
            logger.error(f"Erro durante a inferência da tradução: {e}")
            raise RuntimeError(f"Erro na tradução: {e}") from e
