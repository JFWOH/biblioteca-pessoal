"""Testes do ProactiveReaderService: conformidade ADR-006 e política skip-if-busy."""
import importlib

import pytest
from unittest.mock import patch


def test_service_moved_out_of_core():
    """ADR-006: o serviço (QObject + QThread) não pode mais viver em src/core."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("src.core.proactive_reader_service")
    # E deve existir na camada GUI:
    importlib.import_module("src.gui.proactive_reader_service")


def test_service_disabled_does_nothing(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Desligado"
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        svc.process_page_context("Texto " * 50, 5)
        MockWorker.assert_not_called()


def test_service_skips_when_worker_running(qtbot):
    """skip-if-busy: enquanto uma observação é gerada, não cria um segundo worker
    (substitui o antigo QThread.terminate() inseguro)."""
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = True
        with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
             patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
             patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
            svc.process_page_context("Texto longo " * 30, 10)
            assert MockWorker.call_count == 1  # primeiro disparo cria o worker

            svc.process_page_context("Outro texto " * 30, 12)
            assert MockWorker.call_count == 1  # worker ocupado → pulou, sem novo worker


def test_service_creates_worker_when_idle(qtbot):
    """Com worker ocioso e disparo válido, cria e inicia um novo worker."""
    from src.gui.proactive_reader_service import ProactiveReaderService

    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker:
        MockWorker.return_value.isRunning.return_value = False
        with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
             patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
             patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
            svc.process_page_context("Texto longo " * 30, 10)

        assert MockWorker.call_count == 1
        MockWorker.return_value.start.assert_called_once()


# ── Confiabilidade: resolução de modelo + erros visíveis ──────────────────────

def test_resolve_model_prefers_fast_e4b(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["gemma4:12b", "gemma4:e4b", "mistral:latest"]):
        # proativo favorece velocidade → e4b mesmo com o tier pedindo 12b
        assert svc._resolve_model("gemma4:12b") == "gemma4:e4b"


def test_resolve_model_falls_back_to_tier(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["gemma4:12b", "mistral:latest"]):
        # e4b não instalado → usa o gemma4 instalado (12b)
        assert svc._resolve_model("gemma4:12b") == "gemma4:12b"


def test_resolve_model_last_resort_any_installed(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=["phi3:latest"]):
        assert svc._resolve_model("gemma4:12b") == "phi3:latest"


def test_resolve_model_none_when_nothing_installed(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    with patch.object(svc, "_installed_models", return_value=[]):
        assert svc._resolve_model("gemma4:12b") is None


def test_process_emits_error_when_no_models(qtbot):
    """Antes a falha era silenciosa; agora o usuário recebe um aviso."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    errors = []
    svc.error_occurred.connect(errors.append)
    with patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:12b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=[]):
        svc.process_page_context("Texto longo " * 30, 5)
    assert len(errors) == 1
    assert "modelo" in errors[0].lower()


def test_process_uses_resolved_model(qtbot):
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker, \
         patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:12b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5)
        MockWorker.assert_called_once()
        assert MockWorker.call_args[0][0] == "gemma4:e4b"  # modelo resolvido (rápido)


def test_process_passes_search_fn_and_book_id(qtbot):
    """O cross-ref injetado e o book_id são repassados ao worker."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    def fn(text):
        return []

    svc.set_cross_reference(fn)
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker, \
         patch.object(svc.hardware_service, "get_proactive_model_name", return_value="gemma4:e4b"), \
         patch.object(svc.trigger_engine, "should_trigger", return_value=True), \
         patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        assert MockWorker.call_args.kwargs.get("book_id") == 7
        assert MockWorker.call_args.kwargs.get("search_fn") is fn


# ── Fase 5: continuidade (contrato proativo_continuidade §3) ───────────

def _svc_ready(svc):
    """Patches comuns: modelo disponível + trigger liberado."""
    return (
        patch("src.gui.proactive_reader_service.ProactiveWorker"),
        patch.object(svc.hardware_service, "get_proactive_model_name",
                     return_value="gemma4:e4b"),
        patch.object(svc.trigger_engine, "should_trigger", return_value=True),
        patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]),
    )


def test_page_already_observed_skips_worker(qtbot):
    """Página com observação viva não gera de novo (nem entre sessões)."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    svc.set_observations_provider(
        lambda book_id, page=None: [{"content": "já disse", "dismissed": 0}])
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_not_called()


def test_memory_block_reaches_worker(qtbot):
    """As observações recentes do livro entram no prompt via memory_block."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"

    def observations(book_id, page=None):
        if page is not None:
            return []  # página atual sem observação → não pula
        return [{"content": "O autor conecta entropia à seta do tempo.", "page": 3}]

    svc.set_observations_provider(observations)
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        memory = MockWorker.call_args.kwargs.get("memory_block", "")
        assert "entropia à seta do tempo" in memory
        assert "NÃO as repita" in memory


def test_broken_observations_provider_degrades_gracefully(qtbot):
    """Provider quebrado → dispara como antes, sem memória (ADR-005)."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    svc.set_observations_provider(
        lambda book_id, page=None: (_ for _ in ()).throw(RuntimeError("db off")))
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        assert MockWorker.call_args.kwargs.get("memory_block") == ""


def test_without_book_id_no_memory_lookup(qtbot):
    """Sem book_id (ex.: arquivo avulso) o provider nem é consultado."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    calls = []
    svc.set_observations_provider(
        lambda book_id, page=None: calls.append(book_id) or [])
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=None)
        MockWorker.assert_called_once()
        assert calls == []


# ── Fase 6: aprendizado com dispensas (contrato aprendizado_dispensas §3) ──

def test_preference_block_reaches_worker(qtbot):
    """Os tipos que o leitor dispensa entram no prompt via preference_block."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    history = [{"kind": "Contexto externo", "dismissed": 1} for _ in range(5)]
    history += [{"kind": "Observação do texto", "dismissed": 0} for _ in range(3)]
    svc.set_dismissal_history_provider(lambda: history)
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        preference = MockWorker.call_args.kwargs.get("preference_block", "")
        assert '"Contexto externo" (dispensou 5 de 5)' in preference
        assert "EVITE" in preference


def test_broken_dismissal_provider_degrades_gracefully(qtbot):
    """Provider quebrado → dispara como antes, sem preferência (ADR-005)."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    svc.set_dismissal_history_provider(
        lambda: (_ for _ in ()).throw(RuntimeError("db off")))
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo " * 30, 5, book_id=7)
        MockWorker.assert_called_once()
        assert MockWorker.call_args.kwargs.get("preference_block") == ""


# ── Onda Q: custo por página (memo de sessão + blocos memoizados) ─────────

def test_revisited_page_does_not_reprocess(qtbot):
    """(a) Voltar à mesma página não paga banco nem LLM de novo."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    obs_calls = []
    svc.set_observations_provider(
        lambda book_id, page=None: obs_calls.append(page) or [])
    text = "Texto longo " * 30
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context(text, 5, book_id=7)
        assert MockWorker.call_count == 1
        calls_after_first = len(obs_calls)

        svc.process_page_context(text, 5, book_id=7)  # leitor volta à página
        svc.process_page_context(text, 5, book_id=7)
        assert MockWorker.call_count == 1  # nenhuma chamada nova ao modelo
        assert len(obs_calls) == calls_after_first  # nem ao banco


def test_toggling_intensity_does_not_reanalyze_the_same_page(qtbot):
    """Ligar/desligar o proativo reseta a cadência — mas a página atual já foi
    analisada e não pode ser paga de novo (cadência real, sem patch no trigger)."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    text = "Palavra " * 200
    with patch("src.gui.proactive_reader_service.ProactiveWorker") as MockWorker, \
         patch.object(svc.hardware_service, "get_proactive_model_name",
                      return_value="gemma4:e4b"), \
         patch.object(svc, "_installed_models", return_value=["gemma4:e4b"]):
        MockWorker.return_value.isRunning.return_value = False
        svc.set_intensity("Moderado")
        svc.process_page_context(text, 12, book_id=7)
        assert MockWorker.call_count == 1

        svc.set_intensity("Desligado")
        svc.set_intensity("Moderado")  # reset da cadência
        svc.process_page_context(text, 12, book_id=7)
        assert MockWorker.call_count == 1  # mesma página: nada de segunda conta


def test_page_observed_in_db_is_memoized(qtbot):
    """Página pulada pela continuidade só consulta o banco uma vez na sessão."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    calls = []

    def observations(book_id, page=None):
        calls.append(page)
        return [{"content": "já disse", "dismissed": 0}]

    svc.set_observations_provider(observations)
    text = "Texto longo " * 30
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        svc.process_page_context(text, 5, book_id=7)
        svc.process_page_context(text, 5, book_id=7)
        MockWorker.assert_not_called()
        assert calls == [5]  # a 2ª visita nem chega ao banco


def test_failed_generation_frees_the_page_for_retry(qtbot):
    """Falha de rede não "queima" a página: uma nova visita tenta de novo."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    svc.error_occurred.connect(lambda _msg: None)
    text = "Texto longo " * 30
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context(text, 5, book_id=7)
        assert MockWorker.call_count == 1
        svc._on_worker_error("Ollama offline")

        svc.process_page_context(text, 5, book_id=7)
        assert MockWorker.call_count == 2


def test_prompt_blocks_are_not_rebuilt_every_page(qtbot):
    """(b) Blocos de prompt vêm do cache: 1 consulta por acervo, não por página."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    book_lookups = []
    history_lookups = []

    def observations(book_id, page=None):
        if page is None:
            book_lookups.append(book_id)
            return [{"content": "O autor conecta entropia à seta do tempo.", "page": 3}]
        return []

    def history():
        history_lookups.append(1)
        return [{"kind": "Contexto externo", "dismissed": 1} for _ in range(5)]

    svc.set_observations_provider(observations)
    svc.set_dismissal_history_provider(history)
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        for page in range(5, 10):
            svc.process_page_context(f"Texto longo {page} " * 30, page, book_id=7)

        assert MockWorker.call_count == 5
        assert len(book_lookups) == 1  # antes: 5 (uma por página)
        assert len(history_lookups) == 1  # antes: 5 × 200 linhas do SQLite
        # O conteúdo entregue ao worker continua o mesmo em todas as páginas.
        assert "entropia à seta do tempo" in MockWorker.call_args.kwargs["memory_block"]
        assert "Contexto externo" in MockWorker.call_args.kwargs["preference_block"]


def test_new_observation_invalidates_prompt_caches(qtbot):
    """Observação nova muda o acervo → os blocos são refeitos na próxima página."""
    from src.gui.proactive_reader_service import ProactiveReaderService
    svc = ProactiveReaderService()
    svc.intensity = "Estudo"
    book_lookups = []

    def observations(book_id, page=None):
        if page is None:
            book_lookups.append(book_id)
            return [{"content": "algo", "page": 3}]
        return []

    svc.set_observations_provider(observations)
    w, hw, trg, inst = _svc_ready(svc)
    with w as MockWorker, hw, trg, inst:
        MockWorker.return_value.isRunning.return_value = False
        svc.process_page_context("Texto longo A " * 30, 5, book_id=7)
        svc._on_worker_finished({"tipo": "x", "confianca": "Alta", "texto": "y"})
        svc.process_page_context("Texto longo B " * 30, 6, book_id=7)
        assert len(book_lookups) == 2
