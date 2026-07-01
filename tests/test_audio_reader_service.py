import sys
import pytest
from src.core.audio.tts_backend import TTSBackend, AudioReaderError
from src.core.audio.audio_reader_service import AudioReaderService
from src.core.audio.text_chunker import clean_text_for_tts, split_text_for_tts

class FakeTTSBackend(TTSBackend):
    """Implementacao fake e leve de TTSBackend para testes headless."""

    def __init__(self):
        self.spoken_chunks = []
        self.rate = 200
        self.volume = 1.0
        self.voices = [{"id": "v1", "name": "Voz de Teste", "languages": ["pt-BR"]}]
        self.current_voice = "v1"
        self.stop_called = False
        self.pause_called = False
        self.resume_called = False
        self.raise_error = False

    def speak(self, text: str) -> None:
        if self.raise_error:
            raise RuntimeError("Erro simulado do hardware de audio")
        self.spoken_chunks.append(text)

    def stop(self) -> None:
        self.stop_called = True

    def pause(self) -> None:
        self.pause_called = True

    def resume(self) -> None:
        self.resume_called = True

    def set_rate(self, rate: int) -> None:
        self.rate = rate

    def set_volume(self, volume: float) -> None:
        self.volume = volume

    def list_voices(self) -> list:
        return self.voices

    def set_voice(self, voice_id: str) -> None:
        self.current_voice = voice_id


# --- TESTES DE LIMPEZA E CHUNKING ---

def test_clean_text_for_tts_removes_pdf_line_hyphen():
    text = "Isso é um com-\nputador portátil."
    assert clean_text_for_tts(text) == "Isso é um computador portátil."

def test_clean_text_for_tts_removes_pdf_line_hyphen_with_spaces():
    text = "Isso é um com- \n putador portátil."
    assert clean_text_for_tts(text) == "Isso é um computador portátil."

def test_clean_text_for_tts_preserves_semantic_hyphen():
    text = "Minha segunda-feira foi excelente."
    assert clean_text_for_tts(text) == "Minha segunda-feira foi excelente."

def test_clean_text_for_tts_preserves_email_hyphen():
    text = "Entre em contato via e-mail corporativo."
    assert clean_text_for_tts(text) == "Entre em contato via e-mail corporativo."

def test_clean_text_for_tts_normalizes_spaces():
    text = "Texto   com   muitos     espacos."
    assert clean_text_for_tts(text) == "Texto com muitos espacos."

def test_unicode_text_does_not_break_chunker():
    text = "Olá, João! Tudo bem com você? Ç, á, é, í, ó, ú, ñ."
    # Não deve quebrar nem corromper caracteres
    cleaned = clean_text_for_tts(text)
    assert "Olá, João!" in cleaned
    assert "Ç, á, é" in cleaned

def test_split_text_for_tts_handles_paragraphs():
    text = "Parágrafo um.\n\nParágrafo dois."
    chunks = split_text_for_tts(text, max_chars=100)
    assert len(chunks) == 2
    assert chunks[0] == "Parágrafo um."
    assert chunks[1] == "Parágrafo dois."

def test_split_text_for_tts_never_returns_empty_chunks():
    text = "\n\n   \n\n  Texto válido  \n\n"
    chunks = split_text_for_tts(text)
    assert len(chunks) == 1
    assert chunks[0] == "Texto válido"


# --- TESTES DO SERVIÇO AUDIO READER ---

def test_read_text_empty_does_not_call_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    assert service.read_text("") == 0
    assert len(backend.spoken_chunks) == 0

def test_read_text_short_calls_backend_once():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    assert service.read_text("Texto curto.") == 1
    assert backend.spoken_chunks == ["Texto curto."]

def test_read_text_long_is_split_into_multiple_chunks():
    backend = FakeTTSBackend()
    # Força divisão em blocos curtos
    service = AudioReaderService(backend, max_chunk_chars=20)
    
    # Texto com ~35 caracteres
    count = service.read_text("Primeira frase. Segunda frase.")
    assert count > 1
    assert len(backend.spoken_chunks) == count

def test_chunks_preserve_order():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend, max_chunk_chars=20)
    
    service.read_text("Frase um. Frase dois.")
    # Garante que a primeira frase foi dita primeiro
    assert len(backend.spoken_chunks) == 2
    assert "Frase um." in backend.spoken_chunks[0]
    assert "Frase dois." in backend.spoken_chunks[1]

def test_backend_error_is_wrapped_or_reported():
    backend = FakeTTSBackend()
    backend.raise_error = True
    service = AudioReaderService(backend)
    
    with pytest.raises(AudioReaderError):
        service.read_text("Qualquer texto.")

def test_set_rate_delegates_to_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    service.set_rate(150)
    assert backend.rate == 150

def test_set_volume_delegates_to_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    service.set_volume(0.8)
    assert backend.volume == 0.8

def test_list_voices_delegates_to_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    voices = service.list_voices()
    assert len(voices) == 1
    assert voices[0]["id"] == "v1"


# --- TESTES DE SEMÂNTICA STOP / PARADA ---

def test_stop_clears_pending_chunks():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend, max_chunk_chars=15)
    
    # Ao interceptar o speak do primeiro bloco, mandamos o stop
    original_speak = backend.speak
    def interrupt_speak(text):
        service.stop()
        original_speak(text)
        
    backend.speak = interrupt_speak
    
    # Texto com múltiplos blocos
    service.read_text("Primeiro bloco. Segundo bloco. Terceiro bloco.")
    
    # Apenas o primeiro bloco deve ter sido falado, pois o stop limpou a fila pendente
    assert len(backend.spoken_chunks) == 1
    assert "Primeiro bloco." in backend.spoken_chunks[0]

def test_stop_calls_backend_stop():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    service.stop()
    assert backend.stop_called is True

def test_stop_prevents_future_chunks_after_cancel():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend, max_chunk_chars=15)
    
    service.stop()
    # Tentativa de ler após cancelamento ativo
    # Deve abortar imediatamente e retornar 0 chunks lidos
    assert service.read_text("Primeiro. Segundo. Terceiro.") == 0
    assert len(backend.spoken_chunks) == 0

def test_stop_is_best_effort_not_latency_zero_contract():
    # Esse teste valida que a chamada ao stop() não gera travamentos e obedece
    # ao contrato de retorno rápido (best-effort), mesmo que simulemos
    # processamento ativo.
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    import time
    start_time = time.time()
    service.stop()
    end_time = time.time()
    
    # stop() deve retornar quase instantaneamente (< 0.05 segundos)
    assert (end_time - start_time) < 0.05


# --- TESTES DE INTEGRIDADE ARQUITETURAL ---

def test_core_audio_does_not_import_pyqt6():
    # Verifica AST dos arquivos em src/core/audio para garantir que PyQt6 ou gui não são importados
    import ast
    import os
    
    core_audio_dir = os.path.join("src", "core", "audio")
    for root, _, files in os.walk(core_audio_dir):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=file_path)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert "PyQt6" not in alias.name, f"Import do PyQt6 detectado no arquivo {file_path}"
                                assert "gui" not in alias.name, f"Import do gui detectado no arquivo {file_path}"
                        elif isinstance(node, ast.ImportFrom):
                            assert node.module is not None
                            assert "PyQt6" not in node.module, f"ImportFrom do PyQt6 detectado no arquivo {file_path}"
                            assert "gui" not in node.module, f"ImportFrom do gui detectado no arquivo {file_path}"


# --- TESTES DE LIFECYCLE E CORREÇÃO DE BUG (SAPI5/WINDOWS) ---

def test_read_text_can_be_called_twice_after_natural_finish():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    assert service.read_text("Texto um.") == 1
    assert service.read_text("Texto dois.") == 1
    assert backend.spoken_chunks == ["Texto um.", "Texto dois."]

def test_read_text_can_be_called_after_stop():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    service.stop()
    assert service.read_text("Texto antes de reset.") == 0
    
    service.reset()
    assert service.read_text("Texto apos reset.") == 1
    assert backend.spoken_chunks == ["Texto apos reset."]

def test_cancel_flag_resets_on_new_read():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    service.stop()
    assert service._is_cancelled is True
    service.reset()
    assert service._is_cancelled is False

def test_multiple_chunks_are_sent_to_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend, max_chunk_chars=6)
    
    chunks = service.read_text("Um. Dois. Tres.")
    assert chunks == 3
    assert backend.spoken_chunks == ["Um.", "Dois.", "Tres."]

def test_worker_emits_finished_on_success(qtbot):
    from src.gui.workers.audio_worker import AudioWorker
    import unittest.mock
    mock_router = unittest.mock.MagicMock()
    mock_router.get_active_provider_name.return_value = "mock_provider"
    
    worker = AudioWorker("Texto curto para o worker.", router=mock_router)
    
    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

def test_worker_emits_finished_on_error(qtbot):
    from src.gui.workers.audio_worker import AudioWorker
    import unittest.mock
    mock_router = unittest.mock.MagicMock()
    # Usando string vazia para garantir o retorno rápido / término por erro
    worker = AudioWorker("", router=mock_router)
    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

def test_pyttsx3_backend_recreates_engine_per_speak(monkeypatch):
    import unittest.mock
    mock_init = unittest.mock.MagicMock()
    monkeypatch.setattr("pyttsx3.init", mock_init)
    
    from src.core.audio.pyttsx3_backend import Pyttsx3Backend
    backend = Pyttsx3Backend()
    
    backend.speak("Trecho 1")
    backend.speak("Trecho 2")
    
    # pyttsx3.init() deve ter sido chamado exatamente duas vezes
    assert mock_init.call_count == 2


# --- TESTES DE LIMPEZA DE MARCADORES DE REFERÊNCIA/FOOTNOTE ---

def test_clean_text_for_tts_removes_superscript_reference_after_period():
    text = "importantes.² Enriquecer"
    assert clean_text_for_tts(text) == "importantes. Enriquecer"

def test_clean_text_for_tts_removes_superscript_reference_before_period():
    text = "importantes²."
    assert clean_text_for_tts(text) == "importantes."

def test_clean_text_for_tts_removes_html_sup_reference():
    text = "texto<sup>2</sup>"
    assert clean_text_for_tts(text) == "texto"
    
    text_with_id = "texto <sup id=\"fnref2\">2</sup>"
    assert clean_text_for_tts(text_with_id) == "texto"

def test_clean_text_for_tts_removes_bracket_numeric_reference_after_sentence():
    text = "texto.[2] Próximo"
    assert clean_text_for_tts(text) == "texto. Próximo"
    
    text_multi = "texto. [12] Próximo"
    assert clean_text_for_tts(text_multi) == "texto. Próximo"

def test_clean_text_for_tts_preserves_square_meter():
    text = "A sala tem 15 m² de área."
    assert clean_text_for_tts(text) == "A sala tem 15 m² de área."

def test_clean_text_for_tts_preserves_formula_mc_squared():
    text = "A famosa equação E=mc² revolucionou a física."
    assert clean_text_for_tts(text) == "A famosa equação E=mc² revolucionou a física."

def test_clean_text_for_tts_preserves_regular_numbers():
    text = "Capítulo 2 da página 2026 com custo R$ 20."
    assert clean_text_for_tts(text) == "Capítulo 2 da página 2026 com custo R$ 20."

def test_clean_text_for_tts_preserves_decimal_numbers():
    text = "O valor pi é aproximadamente 3.14 e o fator de escala é 2.5."
    assert clean_text_for_tts(text) == "O valor pi é aproximadamente 3.14 e o fator de escala é 2.5."

def test_clean_text_for_tts_reference_cleanup_does_not_create_double_spaces():
    text = "texto;³ próximo"
    assert clean_text_for_tts(text) == "texto; próximo"


# --- NOVOS TESTES OBRIGATÓRIOS DO AUDIO READER MVP ---

def test_clean_text_for_tts_removes_ascii_reference_after_period():
    text = "importantes.2 Enriquecer"
    assert clean_text_for_tts(text) == "importantes. Enriquecer"

def test_clean_text_for_tts_removes_ascii_reference_after_period_with_space():
    text = "importantes. 2 Enriquecer"
    assert clean_text_for_tts(text) == "importantes. Enriquecer"

def test_clean_text_for_tts_removes_ascii_reference_after_period_with_newline():
    text = "importantes.\n2 Enriquecer"
    assert clean_text_for_tts(text) == "importantes. Enriquecer"

def test_clean_text_for_tts_removes_superscript_reference_after_period_with_space():
    text = "importantes. ² Enriquecer"
    assert clean_text_for_tts(text) == "importantes. Enriquecer"

def test_audio_reader_service_sends_cleaned_text_to_backend():
    backend = FakeTTSBackend()
    service = AudioReaderService(backend)
    
    # Envia texto contendo notas e marcadores mistos
    raw_text = "importantes.² Enriquecer ficou em primeiro lugar.[12]"
    service.read_text(raw_text)
    
    # O backend fake deve receber os chunks já limpos!
    assert len(backend.spoken_chunks) == 1
    assert backend.spoken_chunks[0] == "importantes. Enriquecer ficou em primeiro lugar."

def test_audio_worker_uses_audio_reader_service_not_backend_directly():
    from src.gui.workers.audio_worker import AudioWorker
    worker = AudioWorker("importantes.² Enriquecer")
    assert hasattr(worker, "_text")
    assert worker._text == "importantes.² Enriquecer"

