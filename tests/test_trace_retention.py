import tempfile
import time
from pathlib import Path

from src.core.rag.trace_retention import cleanup_traces

def test_trace_retention_keeps_max_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        
        # Cria 5 arquivos trace_*.jsonl simulados
        for i in range(5):
            file_path = dir_path / f"trace_{i}.jsonl"
            with open(file_path, "w") as f:
                f.write('{"test": "data"}\n')
            # Força tempo diferente para garantir ordem
            time.sleep(0.01)
            
        # Adiciona um arquivo que não deveria ser tocado
        with open(dir_path / "outro_arquivo.txt", "w") as f:
            f.write("não deletar")
            
        # Executa retenção para reter apenas 2 traces
        result = cleanup_traces(dir_path, max_files=2)
        
        assert result['deleted'] == 3
        assert result['kept'] == 2
        assert len(result['errors']) == 0
        
        # Verifica o que sobrou
        remaining_traces = list(dir_path.glob("trace_*.jsonl"))
        assert len(remaining_traces) == 2
        
        # O arquivo mais recente deve ter sobrado.
        # Criamos o i=3 e i=4 por último (são os 2 mais recentes)
        remaining_names = [p.name for p in remaining_traces]
        assert "trace_3.jsonl" in remaining_names
        assert "trace_4.jsonl" in remaining_names
        
        # O outro arquivo intacto
        assert (dir_path / "outro_arquivo.txt").exists()

def test_trace_retention_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        result = cleanup_traces(tmpdir, max_files=5)
        assert result['deleted'] == 0
        assert result['kept'] == 0
        assert len(result['errors']) == 0

def test_trace_retention_less_than_max():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        for i in range(3):
            file_path = dir_path / f"trace_{i}.jsonl"
            with open(file_path, "w") as f:
                f.write('{}')
                
        result = cleanup_traces(tmpdir, max_files=10)
        assert result['deleted'] == 0
        assert result['kept'] == 3
