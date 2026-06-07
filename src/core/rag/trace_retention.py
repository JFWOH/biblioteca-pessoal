import os
import glob
from pathlib import Path

def cleanup_traces(traces_dir: str | Path, max_files: int = 100) -> dict:
    """
    Remove arquivos de trace antigos mantendo apenas os `max_files` mais recentes.
    Age estritamente sobre arquivos que começam com 'trace_' e terminam com '.jsonl'.
    
    Retorna um dicionário com estatísticas da operação:
    {'deleted': int, 'kept': int, 'errors': list[str]}
    """
    traces_dir = Path(traces_dir)
    stats = {'deleted': 0, 'kept': 0, 'errors': []}
    
    if not traces_dir.exists() or not traces_dir.is_dir():
        return stats
        
    pattern = str(traces_dir / "trace_*.jsonl")
    files = glob.glob(pattern)
    
    # Ordenar por tempo de modificação decrescente (mais novos primeiro)
    try:
        files.sort(key=os.path.getmtime, reverse=True)
    except Exception as e:
        stats['errors'].append(f"Erro ao ordenar arquivos: {e}")
        return stats
        
    stats['kept'] = min(len(files), max_files)
    
    if len(files) <= max_files:
        return stats
        
    files_to_delete = files[max_files:]
    
    for file_path in files_to_delete:
        try:
            os.remove(file_path)
            stats['deleted'] += 1
        except Exception as e:
            stats['errors'].append(f"Falha ao apagar {os.path.basename(file_path)}: {e}")
            stats['kept'] += 1
            
    return stats

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Housekeeping manual de traces RAG.")
    parser.add_argument("--dir", type=str, default="data/traces", help="Diretório alvo (padrão: data/traces)")
    parser.add_argument("--max", type=int, default=100, help="Quantidade de traces mais novos a reter (padrão: 100)")
    
    args = parser.parse_args()
    
    target_dir = Path(args.dir)
    if not target_dir.is_absolute():
        # Resolve em relação à raiz do projeto assumindo que rodamos do diretório principal
        base_dir = Path(__file__).resolve().parent.parent.parent.parent
        target_dir = base_dir / args.dir
        
    print(f"Executando housekeeping em: {target_dir}")
    print(f"Política: manter os {args.max} mais recentes.")
    
    result = cleanup_traces(target_dir, args.max)
    
    print(f"Resultado: {result['deleted']} apagados, {result['kept']} mantidos.")
    if result['errors']:
        print("Erros reportados:")
        for err in result['errors']:
            print(f" - {err}")
            
    sys.exit(0 if not result['errors'] else 1)
