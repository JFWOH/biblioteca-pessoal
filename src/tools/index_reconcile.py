"""Utilitário de reconciliação entre SQLite e ChromaDB para o projeto Biblioteca Pessoal.

Modos de uso:
--check: Apenas detecta e lista inconsistências.
--repair: Reindexa explicitamente os itens inconsistentes.
"""

import argparse
import sys
from pathlib import Path

from src.core.database import LibraryDB
from src.core.rag_engine import RAGEngine
from src.core.document_indexer_service import DocumentIndexerService

def main():
    parser = argparse.ArgumentParser(description="Reconciliador do Índice Vetorial (SQLite vs ChromaDB)")
    parser.add_argument("--check", action="store_true", help="Lista inconsistências sem modificar nada.")
    parser.add_argument("--repair", action="store_true", help="Aciona a reindexação dos itens inconsistentes/falhos.")
    parser.add_argument("--db-path", type=str, default="data/library.db", help="Caminho do banco SQLite")
    parser.add_argument("--chroma-path", type=str, default="data/chroma", help="Caminho do ChromaDB")
    
    args = parser.parse_args()
    
    if not args.check and not args.repair:
        print("Erro: Forneça --check ou --repair.")
        sys.exit(1)
        
    db_path = Path(args.db_path)
    if not db_path.exists():
        print(f"Erro: Banco de dados não encontrado em {db_path}")
        sys.exit(1)

    print(f"[{'REPAIR' if args.repair else 'CHECK'}] Iniciando reconciliação...")
    
    db = LibraryDB(str(db_path))
    engine = RAGEngine(db_path=str(db_path), chroma_path=str(args.chroma_path))
    indexer = DocumentIndexerService(db, engine)
    
    all_books = db.get_all_books()
    inconsistent_ids = []
    
    print("\n--- Analisando estado de indexação ---")
    for book in all_books:
        book_id = book["id"]
        title = book["title"]
        status_row = db.get_indexing_status(book_id)
        
        has_chunks = indexer.has_book_indexed(book_id)
        
        if not status_row:
            # Nunca tentou indexar
            print(f"[!] Livro {book_id} ('{title}') não possui registro de indexação no SQLite.")
            inconsistent_ids.append(book_id)
            continue
            
        status = status_row["status"]
        if status == "indexed_ok" and not has_chunks:
            print(f"[!] Livro {book_id} ('{title}') marcado como 'indexed_ok' mas NÃO possui chunks no ChromaDB.")
            inconsistent_ids.append(book_id)
        elif status in ["pending", "failed"]:
            print(f"[!] Livro {book_id} ('{title}') está com status '{status}'. Erro: {status_row.get('error_message', '')}")
            inconsistent_ids.append(book_id)
        elif status == "indexed_ok" and has_chunks:
            # OK
            pass
            
    print(f"\nResumo: {len(inconsistent_ids)} livros com inconsistência ou falha de indexação de um total de {len(all_books)} livros.")
    
    if args.repair:
        if not inconsistent_ids:
            print("Nada para reparar.")
            sys.exit(0)
            
        print("\n--- Iniciando REPAIR (Reindexação) ---")
        for idx, book_id in enumerate(inconsistent_ids):
            print(f"\nReparando {idx+1}/{len(inconsistent_ids)} (Book ID: {book_id})...")
            try:
                n = indexer.index_book(book_id, force=True)
                print(f"Sucesso: {n} chunks indexados.")
            except Exception as e:
                print(f"Falha ao reparar book_id {book_id}: {e}")

if __name__ == "__main__":
    main()
