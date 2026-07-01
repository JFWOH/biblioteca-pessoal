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
