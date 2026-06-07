"""Serviço de Ingestão e Indexação de Documentos para RAG.

Responsável por extrair texto, aplicar OCR (se aplicável), gerar chunks
e persistir os embeddings no ChromaDB, atualizando o estado no SQLite.
"""

import logging
import time
from pathlib import Path

from src.core.database import LibraryDB
# Importa apenas para type hinting
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.core.rag_engine import RAGEngine

logger = logging.getLogger(__name__)

def _chunk_text(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    """Divide texto em chunks com sobreposição."""
    if text is None or not str(text).strip():
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

class DocumentIndexerService:
    def __init__(self, db: LibraryDB, rag_engine: 'RAGEngine'):
        self._db = db
        self._rag_engine = rag_engine

    @property
    def _cancelled(self):
        return getattr(self._rag_engine, "_cancelled", False)

    def cancel(self):
        if hasattr(self._rag_engine, "cancel"):
            self._rag_engine.cancel()
        else:
            self._rag_engine._cancelled = True

    def _extract_book_text(self, book_id: int) -> tuple[dict, list[dict]]:
        """Extrai todo o texto relevante de um livro e suas anotações com mapeamento de páginas."""
        book_meta = self._db.get_book(book_id)
        if not book_meta:
            return {}, []

        chunks: list[dict] = []
        
        # Texto principal (metadados): título + autor + descrição
        main_text = " ".join(filter(None, [
            book_meta.get("title", ""),
            book_meta.get("author", ""),
            book_meta.get("description", ""),
        ]))
        if main_text.strip():
            for c in _chunk_text(main_text, self._rag_engine._chunk_size, self._rag_engine._chunk_overlap):
                chunks.append({
                    "text": c,
                    "page_number": 0,
                    "chunk_type": "metadata"
                })

        # Anotações do livro
        ann_rows = self._db.get_annotations(book_id)
        for ann in ann_rows:
            content = ann.get("content", "").strip()
            if content:
                pg = ann.get("page_number") or 0
                for c in _chunk_text(content, self._rag_engine._chunk_size, self._rag_engine._chunk_overlap):
                    chunks.append({
                        "text": c,
                        "page_number": pg,
                        "chunk_type": "note"
                    })

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
                            is_pdf = p.suffix.lower() == ".pdf"
                            is_scanned = False
                            ocr_service = None
                            
                            if is_pdf:
                                from src.core.ocr_service import OCRService
                                ocr_service = OCRService()
                                is_scanned = ocr_service.is_scanned_pdf(p)
                                if is_scanned:
                                    print(f"[Indexer] PDF detectado como escaneado: {p.name}. Verificando OCR...", flush=True)

                            for i in range(reader.total_pages):
                                if self._cancelled:
                                    break
                                text = reader.get_page_text(i)
                                
                                # Fallback para OCR se for escaneado e texto nativo estiver vazio
                                if (not text or len(text.strip()) < 50) and is_scanned and ocr_service:
                                    if ocr_service.is_available():
                                        # Tenta recuperar cache do banco
                                        row = self._db.get_ocr_page(book_id, i)
                                        if row and row.get("content", "").strip():
                                            text = row["content"]
                                        else:
                                            print(f"   [OCR] Processando página {i+1}/{reader.total_pages}...", flush=True)
                                            text = ocr_service.extract_text_from_page(p, i)
                                            if text and text.strip():
                                                self._db.save_ocr_page(book_id, i, text)
                                    else:
                                        print("[Indexer] WARNING: PDF escaneado detectado, mas pytesseract indisponível.", flush=True)

                                if text and text.strip():
                                    for c in _chunk_text(text, self._rag_engine._chunk_size, self._rag_engine._chunk_overlap):
                                        chunks.append({
                                            "text": c,
                                            "page_number": i,
                                            "chunk_type": "content"
                                        })
                        elif hasattr(reader, "get_chapter_text"):
                            for i in range(reader.total_pages):
                                if self._cancelled:
                                    break
                                text = reader.get_chapter_text(i)
                                if text and text.strip():
                                    for c in _chunk_text(text, self._rag_engine._chunk_size, self._rag_engine._chunk_overlap):
                                        chunks.append({
                                            "text": c,
                                            "page_number": i,
                                            "chunk_type": "content"
                                        })
                        elif hasattr(reader, "get_page"):
                            from bs4 import BeautifulSoup
                            for i in range(reader.total_pages):
                                if self._cancelled:
                                    break
                                page = reader.get_page(i)
                                if page.content_type == "html" and isinstance(page.content, str):
                                    soup = BeautifulSoup(page.content, "html.parser")
                                    text = soup.get_text(separator=" ")
                                    if text and text.strip():
                                        for c in _chunk_text(text, self._rag_engine._chunk_size, self._rag_engine._chunk_overlap):
                                            chunks.append({
                                                "text": c,
                                                "page_number": i,
                                                "chunk_type": "content"
                                            })
                    finally:
                        reader.close()
                except Exception as e:
                    logger.warning("Falha ao extrair texto do arquivo %s: %s", file_path, e)
                    print(f"[Indexer] Falha ao extrair texto de {file_path}: {e}")

        return book_meta, chunks

    def _delete_book_chunks(self, book_id: int) -> None:
        """Remove todos os chunks de um livro do ChromaDB."""
        if not self._rag_engine._collection:
            return
        try:
            existing = self._rag_engine._collection.get(where={"book_id": book_id})
            if existing and existing.get("ids"):
                self._rag_engine._collection.delete(ids=existing["ids"])
        except Exception as exc:
            logger.warning("Não foi possível remover chunks de book_id=%d: %s", book_id, exc)

    def delete_book_index(self, book_id: int) -> None:
        """Remove um livro do índice vetorial e do SQLite tracking."""
        self._delete_book_chunks(book_id)
        # SQLite CASCADE deletes the indexing_state automatically via delete_book in database.py,
        # so we don't strictly need to clear it here. But if called independently:
        try:
            self._db.conn.execute("DELETE FROM indexing_state WHERE book_id = ?", (book_id,))
            self._db.conn.commit()
        except Exception:
            pass

    def has_book_indexed(self, book_id: int) -> bool:
        """Verifica se o livro já possui chunks no banco vetorial."""
        if not self._rag_engine._collection:
            return False
        try:
            existing = self._rag_engine._collection.get(
                where={"book_id": book_id},
                limit=1
            )
            return bool(existing and existing.get("ids"))
        except Exception:
            return False

    def index_book(self, book_id: int, force: bool = False) -> int:
        """Indexa um livro no ChromaDB e mantém o estado transacional no SQLite."""
        # Se force for False, ignora livros já indexados com sucesso no SQLite e que possuam chunks
        if not force:
            status_row = self._db.get_indexing_status(book_id)
            if status_row and status_row["status"] == "indexed_ok" and self.has_book_indexed(book_id):
                print(f"[Indexer] Livro {book_id} já indexado corretamente. Pulando...", flush=True)
                return 0

        if not self._rag_engine.is_ollama_available():
            self._db.set_indexing_status(book_id, "failed", 0, "Ollama indisponível")
            raise RuntimeError("Ollama não está disponível. Certifique-se de que o daemon está rodando.")

        # Validação do modelo de embeddings
        if not self._rag_engine.is_model_available(self._rag_engine._embed_model):
            print(f"[Indexer] Modelo '{self._rag_engine._embed_model}' ausente — iniciando pull…", flush=True)
            for status in self._rag_engine.pull_model(self._rag_engine._embed_model):
                pass
            if not self._rag_engine.is_model_available(self._rag_engine._embed_model):
                self._db.set_indexing_status(book_id, "failed", 0, "Falha ao baixar modelo de embeddings")
                raise RuntimeError(f"Modelo de embedding '{self._rag_engine._embed_model}' não disponível após download.")

        # Verifica se o livro existe antes de violar a Foreign Key do indexing_state
        book_meta = self._db.get_book(book_id)
        if not book_meta:
            raise ValueError(f"Livro com id={book_id} não encontrado no banco.")

        # Início transacional
        self._db.set_indexing_status(book_id, "pending")
        
        try:
            print("1. Extraindo texto do livro...", flush=True)
            _, chunks = self._extract_book_text(book_id)
            
            book_title = book_meta.get("title", "Sem título")
            print(f"[Indexer] Livro: {book_title} | Chunks extraídos: {len(chunks)}", flush=True)

            if not chunks:
                logger.warning("Nenhum texto extraível para book_id=%d", book_id)
                self._db.set_indexing_status(book_id, "indexed_ok", 0)
                return 0

            # Limpa o ChromaDB antes de reindexar
            self._delete_book_chunks(book_id)

            ids: list[str] = []
            embeddings: list[list[float]] = []
            documents: list[str] = []
            metadatas: list[dict] = []

            print("2. Gerando embeddings em lote...", flush=True)
            BATCH_SIZE = 50
            batch_texts = []
            batch_indices = []
            
            def _process_batch(current_texts, current_indices):
                try:
                    batch_embs = self._rag_engine._get_embeddings_batch(current_texts)
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
                    # Fallback single embedding
                    for idx, text_chunk in zip(current_indices, current_texts):
                        emb = self._rag_engine._get_embedding(text_chunk)
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
                        print(f"ERRO CRÍTICO NA INDEXAÇÃO NO LOTE: {str(e)}", flush=True)
                        raise
                    
                    elapsed = time.time() - start_time
                    chunks_processed = i + 1
                    chunks_per_sec = chunks_processed / elapsed if elapsed > 0 else 0
                    chunks_remaining = len(chunks) - chunks_processed
                    eta_secs = chunks_remaining / chunks_per_sec if chunks_per_sec > 0 else 0
                    print(f"   [{chunks_processed}/{len(chunks)}] embeddings gerados... (Faltam ~{int(eta_secs // 60)}m {int(eta_secs % 60)}s)", flush=True)
                    
                    batch_texts.clear()
                    batch_indices.clear()
                    
            if batch_texts and not self._cancelled:
                try:
                    _process_batch(batch_texts, batch_indices)
                    print(f"   [{len(chunks)}/{len(chunks)}] embeddings gerados...", flush=True)
                except Exception as e:
                    print(f"ERRO CRÍTICO NA INDEXAÇÃO NO LOTE FINAL: {str(e)}", flush=True)
                    raise

            if self._cancelled:
                self._db.set_indexing_status(book_id, "failed", len(ids), "Cancelado pelo usuário")
                return len(ids)

            if ids:
                print("3. Salvando no ChromaDB...", flush=True)
                self._rag_engine._collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas,
                )
                logger.info("Indexados %d chunks para book_id=%d", len(ids), book_id)
                self._db.set_indexing_status(book_id, "indexed_ok", len(ids))
                print(f"OK: Concluído: {len(ids)} chunks indexados para {book_title}", flush=True)
            else:
                self._db.set_indexing_status(book_id, "indexed_ok", 0)

            return len(ids)

        except Exception as e:
            self._db.set_indexing_status(book_id, "failed", 0, str(e))
            raise e

    def index_all_books(self) -> dict[int, int]:
        """Re-indexa (apenas os necessários) todos os livros da biblioteca."""
        rows = self._db.get_all_books()
        book_ids = [r["id"] for r in rows]

        results: dict[int, int] = {}
        for book_id in book_ids:
            if self._cancelled:
                break
            try:
                n = self.index_book(book_id, force=False)
                results[book_id] = n
            except Exception as exc:
                logger.error("Erro ao indexar book_id=%d: %s", book_id, exc)
                results[book_id] = -1
        return results
