"""Gerenciamento de configurações da aplicação."""

import json
import copy
from pathlib import Path

from src.utils.constants import (
    DATA_DIR,
    THEME_DARK,
    DEFAULT_FONT_SIZE,
    DEFAULT_FONT_FAMILY,
    DEFAULT_LINE_HEIGHT,
)


DEFAULT_CONFIG = {
    "theme": THEME_DARK,
    "reader": {
        "font_family": DEFAULT_FONT_FAMILY,
        "font_size": DEFAULT_FONT_SIZE,
        "line_height": DEFAULT_LINE_HEIGHT,
        "margin_horizontal": 60,
        "margin_vertical": 40,
        "side_panel_visible": True,  # painel Sumário/Marcadores recolhível (Tarefa 1.3)
    },
    "library": {
        "view_mode": "grid",  # grid | list
        "sort_by": "date_added",  # title | author | date_added | rating
        "sort_order": "desc",
        "show_read_status": True,
        "show_progress": True,
    },
    # Estatísticas vivas (Tarefa 5.2): meta anual opcional exibida no painel.
    "stats": {
        "annual_goal_books": 0,  # nº de livros a ler no ano; 0 = meta desativada
    },
    "import": {
        "copy_to_library": False,
        "auto_extract_metadata": True,
        "detect_duplicates": True,
    },
    "watched_directories": [],
    "recent_files": [],
    "window": {
        "width": 1280,
        "height": 800,
        "maximized": False,
        "sidebar_width": 250,
    },
    "tts": {
        "book_narrator": {
            "role": "book_narrator",
            "preferred_provider": "kokoro",
            "voice_id": None,
            "rate": 1.0,
            "volume": 1.0,
            "style": "serene",
            "language": "pt-BR",
        },
        "assistant": {
            "role": "assistant",
            "preferred_provider": "kokoro",
            "voice_id": None,
            "rate": 1.05,
            "volume": 1.0,
            "style": "didactic",
            "language": "pt-BR",
        },
        "auto_fallback": True,
        "continuous_reading": False,  # narração vira páginas automaticamente
        "continuous_translate_reading": False,  # leitura contínua com tradução automática (consumidor futuro)
    },
    # Tradução offline (NLLB + revisão pelo LLM local).
    "translation": {
        "model": "facebook/nllb-200-distilled-600M",
        "default_src": "en",
        "default_tgt": "pt",
        "revise_with_llm": True,   # gemma4 revisa o rascunho do NLLB (fallback: rascunho)
    },
    # Auto-indexação RAG: indexa livros pendentes em ocioso (1 por vez).
    "auto_index": {
        "enabled": True,
        "idle_interval_s": 120,        # frequência de verificação
        "idle_min_inactivity_s": 120,  # só roda sem leitura ativa há N segundos
        # Carência de startup (achado B0): a indexação NÃO começa nos primeiros
        # N segundos após o launch, mesmo que o app pareça ocioso. Sem isso, o
        # "ocioso" era só "sem LEITURA ativa" — navegar na grade não conta como
        # atividade —, então ~2 min após abrir o app o indexador disparava e
        # competia por CPU/IO com a sessão interativa e com o TTS (TTFB do
        # Kokoro estourando o SLO). A carência dá uma janela interativa inicial.
        "startup_grace_s": 300,
    },
    # Grafo de conceitos (Fase 2): ingestão dirigida pela leitura + ocioso.
    "graph": {
        "enabled": True,
        "use_llm_pages": False,        # páginas = heurística (evita colidir com o proativo)
        "use_llm_annotations": True,   # anotações = LLM (raras/curtas), fallback heurístico
        "use_llm_idle": False,
        "llm_model": None,             # None → resolve entre os modelos instalados
        "llm_timeout_s": 20,
        "max_concepts_per_page": 8,
        "max_concepts_per_annotation": 5,
        "idle_enabled": True,
        "idle_interval_s": 60,
        "idle_min_inactivity_s": 90,
        "idle_batch_pages": 25,
        "edge_min_shared": 2,
        "edge_df_cap": 0.5,
    },
    # Painel do Assistente (RAG standalone): preferência de UI persistida.
    "rag": {
        "sidebar_collapsed": True,  # sidebar (fontes/modelo/indexação) recolhida por padrão
        # Janela de contexto (tokens) enviada ao Ollama nas gerações do RAG.
        # O default do Ollama (4096) trunca em silêncio o início do prompt do
        # RAG (system + esquema de ferramentas + contexto + histórico), fazendo
        # o modelo ignorar o contexto e responder vago/errado. 8192 acomoda o
        # prompt típico; custa mais VRAM e um prefill um pouco mais lento
        # (trade-off aceito). Ver Orchestrator.__init__ e _stream_chat.
        "num_ctx": 8192,
    },
    # Servidor MCP local (src/mcp/server.py). Escrita DESLIGADA por padrão:
    # as ferramentas de escrita (anotações/tags/coleções/status) devolvem erro
    # claro até o usuário ativar aqui (rodada M2 do plano jul/2026-D).
    "mcp": {
        "allow_writes": False,
    },
    # Backend HTTP fino para o cliente mobile Flutter (rodada M0,
    # src/api/main.py). Auth por bearer token estático — "token" vazio
    # aqui significa "não configurado" (a API então recusa requisições
    # autenticadas com 503, nunca abre sem token). Preferir a env var
    # BIBLIOTECA_API_TOKEN em produção; este campo é o fallback persistido.
    "api": {
        "host": "0.0.0.0",
        "port": 8765,
        "token": "",
    },
}



class ConfigManager:
    """Gerencia as configurações persistentes da aplicação."""

    def __init__(self, config_path: str | Path | None = None):
        self._path = Path(config_path) if config_path else DATA_DIR / "config.json"
        self._config: dict = {}
        self.load()

    def load(self) -> None:
        """Carrega configurações do disco ou cria padrões."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._config = {}

        # Merge com defaults (mantém valores existentes)
        self._config = self._deep_merge(copy.deepcopy(DEFAULT_CONFIG), self._config)

    def save(self) -> None:
        """Salva configurações no disco."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        """Obtém um valor de configuração (suporta notação com ponto: 'reader.font_size')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value) -> None:
        """Define um valor de configuração (suporta notação com ponto)."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save()

    @property
    def theme(self) -> str:
        return self.get("theme", THEME_DARK)

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("theme", value)

    @property
    def reader_config(self) -> dict:
        return self.get("reader", DEFAULT_CONFIG["reader"])

    @property
    def library_config(self) -> dict:
        return self.get("library", DEFAULT_CONFIG["library"])

    @property
    def tts_config(self) -> dict:
        return self.get("tts", DEFAULT_CONFIG["tts"])


    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Merge profundo de dois dicionários."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def add_recent_file(self, filepath: str, max_recent: int = 20) -> None:
        """Adiciona um arquivo à lista de recentes."""
        recent = self.get("recent_files", [])
        if filepath in recent:
            recent.remove(filepath)
        recent.insert(0, filepath)
        self.set("recent_files", recent[:max_recent])
