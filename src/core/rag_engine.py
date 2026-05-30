"""Motor de busca vetorial e pipeline RAG 100% local.

Usa ChromaDB como vector store e Ollama como provedor de LLM/embeddings.
O SQLite existente NÃO é modificado — é lido apenas para extração de conteúdo.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Generator, Iterator

logger = logging.getLogger(__name__)

# ── Constantes de configuração ─────────────────────────────────────────────────
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_LLM_MODEL = "gemma4:e4b"
DEFAULT_CHROMA_PATH = "data/chroma_db"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_N_CONTEXT = 5

_COLLECTION_NAME = "biblioteca_pessoal"

# ── Prompt template ────────────────────────────────────────────────────────────
_FIXED_SYSTEM_PROMPT = """Você é o Assistente Avançado da Biblioteca. A sua prioridade absoluta é responder usando os livros indexados (ferramentas vector_search, keyword_search e cross_reference).
No entanto, caso a informação seja de conhecimento geral recente ou não esteja presente na biblioteca, você tem permissão explícita para usar a ferramenta search_web para buscar dados complementares no DuckDuckGo.
Sempre que usar dados da web, cite explicitamente que a informação veio de uma busca externa.

Você também possui ferramentas visuais para alterar a interface do usuário:
- highlight_book_text: Use para destacar visualmente um trecho importante na página aberta do livro. Escolha a cor apropriada baseado no tipo de conteúdo: "yellow" para geral ou resumos, "green" para conceitos ou definições, e "red" para pontos complexos ou alertas. Ao usar, informe ao usuário que você destacou o texto.
- create_ai_bookmark: Use para criar marcadores de página inteligentes com resumos. Ao usar, informe ao usuário que o marcador foi criado.

IMPORTANTE: Para as informações retiradas dos livros, você DEVE citar a fonte usando o formato exato: [Título do Livro, p. X] (por exemplo, [Dom Casmurro, p. 12]). Use o título e a página fornecidos no cabeçalho de cada trecho do contexto ou retornados pelas ferramentas."""

_TOOLS_DEF = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Busca informações atualizadas e externas na web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca na web."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": "Busca semântica nos livros indexados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Consulta semântica."
                    },
                    "book_id": {
                        "type": "integer",
                        "description": "Opcional. ID do livro. Nulo = busca global."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "keyword_search",
            "description": "Busca textual exata por palavras-chave nos livros.",
            "parameters": {
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "Termo exato a buscar."
                    },
                    "book_id": {
                        "type": "integer",
                        "description": "Opcional. ID do livro. Nulo = busca global."
                    }
                },
                "required": ["term"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cross_reference",
            "description": "Busca um tópico em todos os outros livros, exceto no atual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Tópico a buscar em outros livros."
                    },
                    "current_book_id": {
                        "type": "integer",
                        "description": "ID do livro atual a excluir."
                    }
                },
                "required": ["topic", "current_book_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "highlight_book_text",
            "description": "Destaca visualmente um texto exato na página atual do livro.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text_to_find": {
                        "type": "string",
                        "description": "Texto exato a destacar na página atual."
                    },
                    "color": {
                        "type": "string",
                        "description": "Cor: yellow (geral), green (conceito), red (complexo/alerta). Default: yellow."
                    }
                },
                "required": ["text_to_find"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_ai_bookmark",
            "description": "Cria um marcador com nota na página atual.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {
                        "type": "string",
                        "description": "Resumo ou anotação para o marcador."
                    }
                },
                "required": ["note"]
            }
        }
    }
]



def _chunk_text(text: str, size: int = DEFAULT_CHUNK_SIZE,
                overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Divide texto em chunks com sobreposição."""
    if not text or not text.strip():
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start += size - overlap
    return chunks


class RAGEngine:
    """Motor de Retrieval-Augmented Generation 100% local.

    Attributes:
        db_path: Caminho para o banco SQLite da biblioteca.
        chroma_path: Diretório de persistência do ChromaDB.
        ollama_url: URL base do daemon Ollama.
        embed_model: Nome do modelo de embeddings no Ollama.
        llm_model: Nome do modelo LLM para geração de texto.
        chunk_size: Tamanho máximo de cada chunk de texto (chars).
        chunk_overlap: Sobreposição entre chunks consecutivos.
        n_context: Número de chunks recuperados por consulta.
    """

    def __init__(
        self,
        db_path: str | Path,
        chroma_path: str | Path = DEFAULT_CHROMA_PATH,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        embed_model: str = DEFAULT_EMBED_MODEL,
        llm_model: str = DEFAULT_LLM_MODEL,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
        n_context: int = DEFAULT_N_CONTEXT,
    ) -> None:
        self._db_path = Path(db_path)
        self._chroma_path = Path(chroma_path)
        self._ollama_url = ollama_url.rstrip("/")
        self._embed_model = embed_model
        self._llm_model = llm_model
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._n_context = n_context

        self._chroma_path.mkdir(parents=True, exist_ok=True)
        self._chroma_client = None
        self._collection = None
        self._cancelled = False

        self._init_chroma()

    # ── Inicialização ──────────────────────────────────────────────────────────

    def _init_chroma(self) -> None:
        """Inicializa o cliente ChromaDB persistente."""
        import os
        import logging
        os.environ["ANONYMIZED_TELEMETRY"] = "False"
        os.environ["CHROMA_TELEMETRY"] = "False"
        
        # Suprime os erros de telemetria internos causados pelo bug do PostHog/Chroma
        logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)
        try:
            import chromadb
            from chromadb.config import Settings
            self._chroma_client = chromadb.PersistentClient(
                path=str(self._chroma_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name=_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB inicializado em: %s", self._chroma_path)
        except Exception as exc:
            logger.error("Erro ao inicializar ChromaDB: %s", exc)
            raise RuntimeError(f"Falha ao inicializar ChromaDB: {exc}") from exc

    # ── Health-checks ──────────────────────────────────────────────────────────

    def is_ollama_available(self) -> bool:
        """Verifica se o daemon Ollama está rodando e acessível."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self._ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def is_model_available(self, model_name: str) -> bool:
        """Verifica se um modelo específico está disponível no Ollama."""
        try:
            import json
            import urllib.request
            req = urllib.request.Request(f"{self._ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
            models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            return model_name.split(":")[0] in models
        except Exception:
            return False

    def get_exact_model_name(self, model_name: str) -> str | None:
        """Retorna o nome exato do modelo instalado (com a tag correta) se existir."""
        try:
            import json
            import urllib.request
            req = urllib.request.Request(f"{self._ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
            base_name = model_name.split(":")[0]
            for m in data.get("models", []):
                installed_name = m.get("name", "")
                if installed_name.split(":")[0] == base_name:
                    return installed_name
            return None
        except Exception:
            return None

    def get_indexed_count(self) -> int:
        """Retorna o número de chunks indexados no ChromaDB."""
        if self._collection is None:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    # ── Extração de texto ──────────────────────────────────────────────────────

    def _open_db(self) -> sqlite3.Connection:
        """Abre conexão SQLite somente-leitura."""
        conn = sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _extract_book_text(self, book_id: int) -> tuple[dict, list[dict]]:
        """Extrai todo o texto relevante de um livro e suas anotações com mapeamento de páginas.

        Returns:
            (book_meta, list_of_chunk_dicts)
            onde cada chunk_dict é: {"text": str, "page_number": int, "chunk_type": str}
        """
        conn = self._open_db()
        try:
            row = conn.execute(
                "SELECT id, title, author, description, isbn, publisher, year, file_path "
                "FROM books WHERE id = ?", (book_id,)
            ).fetchone()
            if not row:
                return {}, []

            book_meta = dict(row)
            chunks: list[dict] = []

            # Texto principal (metadados): título + autor + descrição
            main_text = " ".join(filter(None, [
                book_meta.get("title", ""),
                book_meta.get("author", ""),
                book_meta.get("description", ""),
            ]))
            if main_text.strip():
                for c in _chunk_text(main_text, self._chunk_size, self._chunk_overlap):
                    chunks.append({
                        "text": c,
                        "page_number": 0,
                        "chunk_type": "metadata"
                    })

            # Anotações do livro
            ann_rows = conn.execute(
                "SELECT page_number, content FROM annotations WHERE book_id = ? AND content != ''",
                (book_id,)
            ).fetchall()
            for ann in ann_rows:
                content = ann["content"].strip()
                if content:
                    pg = ann["page_number"] if ann["page_number"] is not None else 0
                    for c in _chunk_text(content, self._chunk_size, self._chunk_overlap):
                        chunks.append({
                            "text": c,
                            "page_number": pg,
                            "chunk_type": "note"
                        })

        finally:
            conn.close()

        # Extração do conteúdo literal do arquivo do livro
        file_path = book_meta.get("file_path", "")
        if file_path:
            p = Path(file_path)
            if p.exists():
                try:
                    from src.readers.reader_factory import create_reader
                    reader = create_reader(p)
                    reader.open()
                    try:
                        if hasattr(reader, "get_page_text"):
                            for i in range(reader.total_pages):
                                text = reader.get_page_text(i)
                                if text and text.strip():
                                    for c in _chunk_text(text, self._chunk_size, self._chunk_overlap):
                                        chunks.append({
                                            "text": c,
                                            "page_number": i,
                                            "chunk_type": "content"
                                        })
                        elif hasattr(reader, "get_chapter_text"):
                            for i in range(reader.total_pages):
                                text = reader.get_chapter_text(i)
                                if text and text.strip():
                                    for c in _chunk_text(text, self._chunk_size, self._chunk_overlap):
                                        chunks.append({
                                            "text": c,
                                            "page_number": i,
                                            "chunk_type": "content"
                                        })
                        elif hasattr(reader, "get_page"):
                            from bs4 import BeautifulSoup
                            for i in range(reader.total_pages):
                                page = reader.get_page(i)
                                if page.content_type == "html" and isinstance(page.content, str):
                                    soup = BeautifulSoup(page.content, "html.parser")
                                    text = soup.get_text(separator=" ")
                                    if text and text.strip():
                                        for c in _chunk_text(text, self._chunk_size, self._chunk_overlap):
                                            chunks.append({
                                                "text": c,
                                                "page_number": i,
                                                "chunk_type": "content"
                                            })
                    finally:
                        reader.close()
                except Exception as e:
                    logger.warning("Falha ao extrair texto do arquivo %s: %s", file_path, e)
                    print(f"[RAGEngine] Falha ao extrair texto de {file_path}: {e}")

        return book_meta, chunks

    # ── Embeddings via Ollama ──────────────────────────────────────────────────

    def _get_embedding(self, text: str) -> list[float]:
        """Gera embedding via Ollama REST API (sem dependência do SDK).

        Usa o endpoint /api/embed (novo, estável desde Ollama v0.1.26+).
        O endpoint legado /api/embeddings foi depreciado e retorna null em
        versões recentes, causando falha silenciosa na indexação.
        """
        import json
        import urllib.request
        import urllib.error
        import socket

        # Garante a resolução exata da tag do modelo de embedding antes da requisição
        # Garante a resolução exata da tag do modelo de embedding antes da requisição
        if ":" not in self._embed_model:
            exact_embed = self.get_exact_model_name(self._embed_model)
            if exact_embed:
                self._embed_model = exact_embed

        # Tenta o endpoint novo: /api/embed
        payload = json.dumps({
            "model": self._embed_model,
            "input": text,
        }).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
            embeddings = data.get("embeddings")
            if embeddings and embeddings[0]:
                return embeddings[0]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Fallback para o endpoint antigo /api/embeddings
                payload_legacy = json.dumps({
                    "model": self._embed_model,
                    "prompt": text,
                }).encode()
                req_legacy = urllib.request.Request(
                    f"{self._ollama_url}/api/embeddings",
                    data=payload_legacy,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req_legacy, timeout=15) as resp:
                        data = json.loads(resp.read())
                    embedding = data.get("embedding")
                    if embedding:
                        return embedding
                except urllib.error.HTTPError as e2:
                    error_body = e2.read().decode('utf-8')
                    logger.error("HTTPError %s no Fallback de Embedding: %s", e2.code, error_body)
                    raise RuntimeError(f"Ollama retornou erro HTTP {e2.code} ao gerar embeddings: {error_body}") from e2
            else:
                error_body = e.read().decode('utf-8')
                logger.error("HTTPError %s em Embedding: %s", e.code, error_body)
                raise RuntimeError(f"Ollama retornou erro HTTP {e.code} ao gerar embeddings: {error_body}") from e
        except (TimeoutError, urllib.error.URLError, socket.timeout, ConnectionError) as e:
            raise TimeoutError(f"Ollama não respondeu em 15s ao gerar embeddings. {str(e)}")

        raise ValueError(
            f"Ollama não retornou embedding para o texto: {text[:60]}… "
            f"(modelo: {self._embed_model})"
        )

    def _get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Gera múltiplos embeddings em uma única requisição."""
        import json
        import urllib.request
        import urllib.error
        import socket

        if ":" not in self._embed_model:
            exact_embed = self.get_exact_model_name(self._embed_model)
            if exact_embed:
                self._embed_model = exact_embed

        payload = json.dumps({
            "model": self._embed_model,
            "input": texts,
        }).encode()
        
        req = urllib.request.Request(
            f"{self._ollama_url}/api/embed",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        try:
            # Tempo limite maior para lotes (e.g. 50 chunks)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            embeddings = data.get("embeddings")
            if embeddings and len(embeddings) == len(texts):
                return embeddings
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # O Ollama antigo não tem /api/embed, apenas /api/embeddings que não aceita lotes de forma trivial.
                raise NotImplementedError("Batching não é suportado nesta versão do Ollama (requer endpoint /api/embed).")
            else:
                error_body = e.read().decode('utf-8')
                raise RuntimeError(f"Ollama retornou erro HTTP {e.code} ao gerar lote de embeddings: {error_body}") from e
        except (TimeoutError, urllib.error.URLError, socket.timeout, ConnectionError) as e:
            raise TimeoutError(f"Ollama não respondeu em 120s ao gerar lote de embeddings. {str(e)}")

        raise ValueError("Ollama não retornou embeddings para o lote inteiro.")

    # ── Indexação ──────────────────────────────────────────────────────────────

    def index_book(self, book_id: int) -> int:
        """Indexa um livro e suas anotações no ChromaDB.

        Args:
            book_id: ID do livro no SQLite.

        Returns:
            Número de chunks indexados.

        Raises:
            RuntimeError: Se o Ollama não estiver disponível ou o modelo de
                          embedding não puder ser obtido.
            ValueError: Se o livro não for encontrado.
        """
        # --- Idempotência: Pula se já estiver indexado ---
        if self.has_book_indexed(book_id):
            print(f"[RAGEngine] Livro {book_id} já está indexado no ChromaDB. Pulando...", flush=True)
            return 0

        if not self.is_ollama_available():
            raise RuntimeError(
                "Ollama não está disponível. Certifique-se de que o daemon "
                "está rodando (execute 'ollama serve' no terminal)."
            )

        # ── Validação do modelo de embeddings (Fix #2) ────────────────────────
        if not self.is_model_available(self._embed_model):
            logger.info(
                "Modelo de embedding '%s' não encontrado localmente. Baixando…",
                self._embed_model,
            )
            print(
                f"[RAGEngine] Modelo '{self._embed_model}' ausente — iniciando pull…",
                flush=True,
            )
            for status in self.pull_model(self._embed_model):
                logger.debug("Pull embed model: %s", status.get("status", ""))
            if not self.is_model_available(self._embed_model):
                raise RuntimeError(
                    f"Modelo de embedding '{self._embed_model}' não disponível após download. "
                    "Verifique sua conexão e tente novamente."
                )
            logger.info("Modelo '%s' baixado com sucesso.", self._embed_model)
        # ─────────────────────────────────────────────────────────────────────

        print("1. Extraindo texto do livro...", flush=True)
        book_meta, chunks = self._extract_book_text(book_id)
        if not book_meta:
            raise ValueError(f"Livro com id={book_id} não encontrado no banco.")
        
        book_title = book_meta.get("title", "Sem título")
        print(f"[RAGEngine] Livro: {book_title} | Chunks extraídos pelo Reader: {len(chunks)}", flush=True)

        if not chunks:
            logger.warning("Nenhum texto extraível para book_id=%d", book_id)
            return 0

        # Remove chunks anteriores deste livro (re-indexação limpa)
        self._delete_book_chunks(book_id)

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        print("2. Gerando chunks... concluído. Iniciando geração de embeddings", flush=True)
        print("3. Solicitando embeddings ao Ollama (tentando em lote)...", flush=True)
        
        BATCH_SIZE = 50
        batch_texts = []
        batch_indices = []
        
        def _process_batch(current_texts, current_indices):
            try:
                # Tenta gerar em lote
                batch_embs = self._get_embeddings_batch(current_texts)
                for i_idx, emb in zip(current_indices, batch_embs):
                    ids.append(f"book_{book_id}_chunk_{i_idx}")
                    embeddings.append(emb)
                    documents.append(current_texts[current_indices.index(i_idx)])
                    chunk_data = chunks[i_idx]
                    metadatas.append({
                        "book_id": book_id,
                        "title": book_meta.get("title", ""),
                        "author": book_meta.get("author", ""),
                        "chunk_index": i_idx,
                        "page_number": chunk_data.get("page_number", 0),
                        "chunk_type": chunk_data.get("chunk_type", "content")
                    })
            except NotImplementedError:
                # Fallback: se o Ollama não suporta batch, faz um por um
                for idx, text_chunk in zip(current_indices, current_texts):
                    emb = self._get_embedding(text_chunk)
                    ids.append(f"book_{book_id}_chunk_{idx}")
                    embeddings.append(emb)
                    documents.append(text_chunk)
                    chunk_data = chunks[idx]
                    metadatas.append({
                        "book_id": book_id,
                        "title": book_meta.get("title", ""),
                        "author": book_meta.get("author", ""),
                        "chunk_index": idx,
                        "page_number": chunk_data.get("page_number", 0),
                        "chunk_type": chunk_data.get("chunk_type", "content")
                    })

        import time
        start_time = time.time()
        
        for i, chunk_data in enumerate(chunks):
            if self._cancelled:
                break
            batch_texts.append(chunk_data["text"])
            batch_indices.append(i)
            
            if len(batch_texts) >= BATCH_SIZE:
                try:
                    _process_batch(batch_texts, batch_indices)
                except Exception as e:
                    print(f"ERRO CRÍTICO NA INDEXAÇÃO NO LOTE (Chunks {batch_indices[0]} até {batch_indices[-1]}): {str(e)}", flush=True)
                    raise
                
                # Cálculo de ETA
                elapsed = time.time() - start_time
                chunks_processed = i + 1
                chunks_per_sec = chunks_processed / elapsed if elapsed > 0 else 0
                chunks_remaining = len(chunks) - chunks_processed
                eta_secs = chunks_remaining / chunks_per_sec if chunks_per_sec > 0 else 0
                eta_mins = int(eta_secs // 60)
                eta_remainder_secs = int(eta_secs % 60)
                eta_str = f"Faltam ~{eta_mins}m {eta_remainder_secs}s"
                
                print(f"   [{chunks_processed}/{len(chunks)}] embeddings gerados... ({eta_str})", flush=True)
                
                batch_texts.clear()
                batch_indices.clear()
                
        # Processa chunks restantes
        if batch_texts and not self._cancelled:
            try:
                _process_batch(batch_texts, batch_indices)
                print(f"   [{len(chunks)}/{len(chunks)}] embeddings gerados...", flush=True)
            except Exception as e:
                print(f"ERRO CRÍTICO NA INDEXAÇÃO NO LOTE FINAL: {str(e)}", flush=True)
                raise

        if ids:
            print("4. Salvando no ChromaDB...", flush=True)
            self._collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
            logger.info("Indexados %d chunks para book_id=%d", len(ids), book_id)
            try:
                print(f"OK: Concluído: {len(ids)} chunks indexados para {book_title}", flush=True)
            except UnicodeEncodeError:
                safe_title = book_title.encode('ascii', 'ignore').decode('ascii')
                print(f"OK: Concluido: {len(ids)} chunks indexados para {safe_title}", flush=True)

        return len(ids)

    def index_all_books(self) -> dict[int, int]:
        """Re-indexa todos os livros da biblioteca.

        Returns:
            Dict {book_id: n_chunks_indexed}
        """
        conn = self._open_db()
        try:
            rows = conn.execute("SELECT id FROM books").fetchall()
            book_ids = [r["id"] for r in rows]
        finally:
            conn.close()

        results: dict[int, int] = {}
        self._cancelled = False
        for book_id in book_ids:
            if self._cancelled:
                break
            try:
                n = self.index_book(book_id)
                results[book_id] = n
            except Exception as exc:
                logger.error("Erro ao indexar book_id=%d: %s", book_id, exc)
                results[book_id] = -1
        return results

    def _delete_book_chunks(self, book_id: int) -> None:
        """Remove todos os chunks de um livro do ChromaDB."""
        try:
            existing = self._collection.get(
                where={"book_id": book_id}
            )
            if existing and existing.get("ids"):
                self._collection.delete(ids=existing["ids"])
        except Exception as exc:
            logger.warning("Não foi possível remover chunks de book_id=%d: %s", book_id, exc)

    def delete_book_index(self, book_id: int) -> None:
        """Remove um livro do índice vetorial (chamado ao excluir da biblioteca)."""
        self._delete_book_chunks(book_id)

    def has_book_indexed(self, book_id: int) -> bool:
        """Verifica se o livro já possui chunks no banco vetorial."""
        if not self._collection:
            return False
        try:
            existing = self._collection.get(
                where={"book_id": book_id},
                limit=1
            )
            return bool(existing and existing.get("ids"))
        except Exception:
            return False

    # ── Busca Vetorial ─────────────────────────────────────────────────────────

    def search_similar(self, query: str, n_results: int = 5, book_id: int | None = None) -> list[dict]:
        """Busca semântica pura: retorna chunks mais similares à query.

        Args:
            query: Pergunta ou texto de busca.
            n_results: Número máximo de resultados.
            book_id: Filtro de ID do livro para busca restrita.

        Returns:
            Lista de dicts com keys: document, metadata, distance.
        """
        if not self.is_ollama_available():
            raise RuntimeError("Ollama não está disponível para gerar embeddings.")

        if self._collection.count() == 0:
            return []

        n = min(n_results, self._collection.count())
        query_emb = self._get_embedding(query)
        
        where_filter = {"book_id": book_id} if book_id is not None else None
        
        results = self._collection.query(
            query_embeddings=[query_emb],
            n_results=n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output: list[dict] = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "document": doc,
                "metadata": meta,
                "distance": dist,
            })
        return output

    def keyword_search_db(
        self,
        term: str,
        book_id: int | None = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Busca textual exata por palavra-chave nos chunks do ChromaDB e nas anotações do SQLite.

        Args:
            term: Termo ou frase a buscar.
            book_id: Filtro opcional de livro.
            max_results: Número máximo de resultados.

        Returns:
            Lista de dicts com keys: source, text, title, author, book_id, page.
        """
        results: list[dict] = []

        # 1. ChromaDB: busca por substring nos documentos indexados
        if self._collection is not None:
            try:
                where_filter = {"book_id": book_id} if book_id else None
                chroma_res = self._collection.get(
                    where=where_filter,
                    where_document={"$contains": term},
                    limit=max_results,
                    include=["documents", "metadatas"],
                )
                docs = chroma_res.get("documents") or []
                metas = chroma_res.get("metadatas") or []
                for doc, meta in zip(docs, metas):
                    results.append({
                        "source": "indexed_text",
                        "text": doc,
                        "title": meta.get("title", ""),
                        "author": meta.get("author", ""),
                        "book_id": meta.get("book_id"),
                        "page": (meta.get("page_number") or 0) + 1,
                    })
            except Exception as exc:
                logger.warning("keyword_search ChromaDB falhou: %s", exc)

        # 2. SQLite: busca nas anotações
        try:
            conn = self._open_db()
            try:
                if book_id:
                    rows = conn.execute(
                        """
                        SELECT a.content, a.page_number, b.title, b.author, a.book_id
                        FROM annotations a
                        JOIN books b ON a.book_id = b.id
                        WHERE a.book_id = ? AND a.content LIKE ?
                        LIMIT ?
                        """,
                        (book_id, f"%{term}%", max_results),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT a.content, a.page_number, b.title, b.author, a.book_id
                        FROM annotations a
                        JOIN books b ON a.book_id = b.id
                        WHERE a.content LIKE ?
                        LIMIT ?
                        """,
                        (f"%{term}%", max_results),
                    ).fetchall()
                for row in rows:
                    results.append({
                        "source": "annotation",
                        "text": row[0],
                        "page": (row[1] or 0) + 1,
                        "title": row[2],
                        "author": row[3],
                        "book_id": row[4],
                    })
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("keyword_search SQLite falhou: %s", exc)

        return results[:max_results]

    def query_rag(
        self,
        question: str,
        n_context: int | None = None,
        book_id: int | None = None,
        ui_mutation_callback: callable = None,
    ) -> Generator[str, None, None]:
        """Pipeline RAG com streaming.
        
        .. deprecated::
            Esta implementação delega ao Orchestrator (ADR-003 compliance).
            Usar Orchestrator.query_rag() diretamente quando possível.
        """
        from src.core.rag.orchestrator import Orchestrator
        orchestrator = Orchestrator(self)
        yield from orchestrator.query_rag(
            question, n_context=n_context,
            book_id=book_id, ui_mutation_callback=ui_mutation_callback,
        )


    def get_sources(self, question: str, n_context: int | None = None, book_id: int | None = None) -> list[dict]:
        """Retorna as fontes que seriam usadas para responder à pergunta."""
        n = n_context or self._n_context
        try:
            return self.search_similar(question, n_results=n, book_id=book_id)
        except Exception:
            return []

    # ── Gestão de Modelos ──────────────────────────────────────────────────────

    def list_local_models(self) -> list[dict]:
        """Lista os modelos instalados no Ollama local.

        Returns:
            Lista de dicts com keys: name, size, modified_at.
            Retorna [] se Ollama não estiver disponível.
        """
        import json
        import urllib.request
        try:
            req = urllib.request.Request(f"{self._ollama_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            return [
                {
                    "name": m.get("name", ""),
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                }
                for m in data.get("models", [])
            ]
        except Exception:
            return []

    def pull_model(self, model_name: str) -> Iterator[dict]:
        """Faz pull de um modelo via /api/pull com streaming.

        Yields:
            Dicts com keys: status, completed, total.

        Raises:
            RuntimeError: Se Ollama não estiver disponível.
        """
        import json
        import urllib.request

        if not self.is_ollama_available():
            raise RuntimeError(
                "Ollama não está disponível para pull de modelos."
            )

        payload = json.dumps({"name": model_name, "stream": True}).encode()
        req = urllib.request.Request(
            f"{self._ollama_url}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=600) as resp:
            for line in resp:
                if self._cancelled:
                    break
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    yield {
                        "status": chunk.get("status", ""),
                        "completed": chunk.get("completed", 0),
                        "total": chunk.get("total", 0),
                    }
                    if chunk.get("status") == "success":
                        break
                except json.JSONDecodeError:
                    continue

    def set_llm_model(self, model: str) -> None:
        """Atualiza o modelo LLM em uso para geração de texto.

        Args:
            model: Nome do modelo Ollama (ex: 'gemma3:4b', 'llama3').
        """
        self._llm_model = model
        logger.info("Modelo LLM atualizado para: %s", model)

    def cancel(self) -> None:
        """Sinaliza cancelamento da operação em andamento."""
        self._cancelled = True

