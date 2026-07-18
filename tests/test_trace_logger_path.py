"""Regressão: o default do TraceLogger deve ser ABSOLUTO (DATA_DIR/traces).

O app lançado por atalho roda com CWD=system32. Com o default RELATIVO antigo
("data/traces") os traces iam parar num diretório resolvido contra o CWD e se
perdiam silenciosamente — foi o que aconteceu na sessão real do usuário. O
default agora ancora em DATA_DIR (src/utils/constants), então independe do CWD.

Os testes patcham ``DATA_DIR`` para um tmp_path — isso evita poluir o
``data/traces`` do repositório e, de quebra, prova que o alvo segue o DATA_DIR
configurado, não o diretório de trabalho.
"""
import os

import src.core.rag.trace_logger as tl_mod
from src.core.rag.trace_logger import TraceLogger


def test_default_traces_dir_is_absolute_ignoring_cwd(tmp_path, monkeypatch):
    fake_data = tmp_path / "appdata"
    monkeypatch.setattr(tl_mod, "DATA_DIR", fake_data)

    # Simula o atalho: processo rodando de um CWD totalmente diferente.
    cwd_dir = tmp_path / "system32-like"
    cwd_dir.mkdir()
    original_cwd = os.getcwd()
    os.chdir(cwd_dir)
    try:
        logger = TraceLogger("sess-abs")
        logger.emit("query_started", step=0, query="oi")
    finally:
        os.chdir(original_cwd)  # restaura SEMPRE, mesmo se algo falhar

    expected = fake_data / "traces" / "trace_sess-abs.jsonl"
    assert expected.is_file(), "trace deveria estar sob DATA_DIR/traces"
    # E nada foi escrito relativo ao CWD trocado.
    assert not (cwd_dir / "data").exists()


def test_explicit_traces_dir_still_overrides(tmp_path):
    """Compatibilidade: passar traces_dir explícito continua mandando."""
    target = tmp_path / "custom" / "traces"
    logger = TraceLogger("sess-explicit", traces_dir=str(target))
    logger.emit("query_started", step=0)
    assert (target / "trace_sess-explicit.jsonl").is_file()
