"""Cache em disco das miniaturas do sumário (Onda P — rodada UX ago/2026).

Antes desta onda, reabrir o mesmo livro pagava de novo a renderização das (até)
40 miniaturas de capítulo. Agora cada miniatura vira um PNG em
``data/cache/thumbs/`` e a reabertura é só leitura de arquivo.

Núcleo puro (ADR-006): nada de PyQt6 aqui — só ``hashlib``/``pathlib``. Quem
renderiza é o leitor (``src/readers/**``, PyMuPDF); quem converte para
``QPixmap`` é a GUI.

Chave: SHA-1 de ``caminho | tamanho | mtime_ns | página | largura``. Se o
arquivo for reeditado ou trocado por outra edição, tamanho/mtime mudam e a
chave muda junto — as miniaturas velhas deixam de ser encontradas e a poda as
recolhe depois. Não há invalidação explícita a fazer.

Poda: teto pelo NÚMERO de arquivos, descartando os mais antigos por mtime. É um
cache descartável (o pior caso de qualquer falha aqui é renderizar de novo),
então toda operação é best-effort e NUNCA levanta para o chamador (ADR-005).
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from src.utils.constants import CACHE_DIR

logger = logging.getLogger(__name__)

# Teto de arquivos no cache. 2000 miniaturas ≈ 40 capítulos de 50 livros, e a
# ~4KB cada dá poucos MB em disco — barato o bastante para não exigir política
# mais fina do que "descarta os mais antigos".
DEFAULT_MAX_FILES = 2000


class ThumbnailCache:
    """Cache de miniaturas PNG em disco, endereçado por conteúdo do arquivo."""

    def __init__(self, cache_dir: str | Path | None = None,
                 max_files: int = DEFAULT_MAX_FILES) -> None:
        self._dir = Path(cache_dir) if cache_dir else CACHE_DIR / "thumbs"
        self._max_files = max(1, int(max_files))

    @property
    def directory(self) -> Path:
        return self._dir

    # ── Chave ─────────────────────────────────────────────────────────

    @staticmethod
    def _stamp(filepath: str | Path) -> str | None:
        """Identidade do arquivo: caminho absoluto + tamanho + mtime_ns.

        ``None`` quando o arquivo não existe/não pode ser lido — sem stat não há
        como garantir que o cache ainda corresponde ao arquivo, então o chamador
        renderiza direto.
        """
        try:
            p = Path(filepath).resolve()
            st = p.stat()
        except OSError:
            return None
        return f"{p}|{st.st_size}|{st.st_mtime_ns}"

    def key(self, filepath: str | Path, page: int, width: int) -> str | None:
        """Chave (hex SHA-1) da miniatura, ou ``None`` se o arquivo sumiu."""
        stamp = self._stamp(filepath)
        if stamp is None:
            return None
        material = f"{stamp}|{int(page)}|{int(width)}".encode("utf-8")
        return hashlib.sha1(material).hexdigest()

    def _path_for(self, filepath: str | Path, page: int, width: int) -> Path | None:
        chave = self.key(filepath, page, width)
        return None if chave is None else self._dir / f"{chave}.png"

    # ── Leitura/escrita ───────────────────────────────────────────────

    def get(self, filepath: str | Path, page: int, width: int) -> bytes | None:
        """PNG da miniatura em cache, ou ``None`` (miss / erro de leitura)."""
        destino = self._path_for(filepath, page, width)
        if destino is None:
            return None
        try:
            dados = destino.read_bytes()
        except OSError:
            return None
        return dados or None

    def put(self, filepath: str | Path, page: int, width: int,
            png: bytes) -> bool:
        """Grava a miniatura. Devolve ``True`` se gravou.

        Escrita atômica (tmp + ``os.replace``): dois leitores abrindo o mesmo
        livro ao mesmo tempo nunca leem um PNG pela metade.
        """
        if not png:
            return False
        destino = self._path_for(filepath, page, width)
        if destino is None:
            return False
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            temporario = destino.with_suffix(f".{os.getpid()}.tmp")
            temporario.write_bytes(png)
            os.replace(temporario, destino)
            return True
        except OSError:
            logger.debug("Cache de miniaturas: falha ao gravar %s",
                         destino, exc_info=True)
            return False

    # ── Poda ──────────────────────────────────────────────────────────

    def prune(self) -> int:
        """Mantém no máximo ``max_files`` PNGs, descartando os mais antigos.

        Devolve quantos arquivos removeu. Chamada uma vez ao fim de cada lote
        (ver ``ThumbnailWorker``), não a cada gravação — listar o diretório é o
        custo aqui, e um lote inteiro justifica uma listagem só.
        """
        try:
            arquivos = [p for p in self._dir.glob("*.png") if p.is_file()]
        except OSError:
            return 0
        if len(arquivos) <= self._max_files:
            return 0

        def _mtime(p: Path) -> float:
            try:
                return p.stat().st_mtime
            except OSError:
                return 0.0

        arquivos.sort(key=_mtime)
        removidos = 0
        for antigo in arquivos[: len(arquivos) - self._max_files]:
            try:
                antigo.unlink()
                removidos += 1
            except OSError:
                pass
        return removidos
