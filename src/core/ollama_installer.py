"""Instalador automático do Ollama para múltiplas plataformas.

Usado pelo OllamaWizardDialog para baixar e instalar o Ollama silenciosamente,
sem que o usuário precise abrir um terminal.
"""

from __future__ import annotations

import logging
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# URLs de download por plataforma
DOWNLOAD_URLS: dict[str, str] = {
    "windows": "https://ollama.com/download/OllamaSetup.exe",
    "linux":   "https://ollama.com/install.sh",
    "darwin":  "https://ollama.com/download/Ollama-darwin.zip",
}

OLLAMA_URL = "http://localhost:11434"


class OllamaInstaller:
    """Gerencia o download e instalação do Ollama em diferentes plataformas."""

    @staticmethod
    def detect_platform() -> str:
        """Retorna 'windows', 'linux' ou 'darwin'."""
        p = sys.platform
        if p.startswith("win"):
            return "windows"
        if p.startswith("darwin"):
            return "darwin"
        return "linux"

    @classmethod
    def get_download_url(cls) -> str:
        """Retorna a URL de download para a plataforma atual."""
        plat = cls.detect_platform()
        return DOWNLOAD_URLS.get(plat, DOWNLOAD_URLS["linux"])

    @classmethod
    def download(
        cls,
        dest_path: Path,
        progress_cb: Callable[[int, str], None] | None = None,
    ) -> None:
        """Baixa o instalador do Ollama com relatório de progresso.

        Args:
            dest_path: Caminho onde salvar o arquivo baixado.
            progress_cb: Callback(percent: int, message: str) durante o download.
        """
        url = cls.get_download_url()
        if progress_cb:
            progress_cb(0, f"Iniciando download: {url}")

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "BibliotecaPessoal/1.0"},
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 65536  # 64 KB

            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_cb:
                        pct = int(downloaded / total * 100)
                        mb = downloaded / 1_048_576
                        total_mb = total / 1_048_576
                        progress_cb(pct, f"Baixando… {mb:.1f} / {total_mb:.1f} MB")

        if progress_cb:
            progress_cb(100, "Download concluído.")

    @classmethod
    def install(cls, installer_path: Path) -> bool:
        """Executa a instalação silenciosa do Ollama.

        Args:
            installer_path: Caminho para o arquivo baixado.

        Returns:
            True se a instalação foi iniciada com sucesso.
        """
        plat = cls.detect_platform()
        try:
            if plat == "windows":
                # OllamaSetup.exe suporta instalação silenciosa
                subprocess.run(
                    [str(installer_path), "/SILENT", "/NORESTART"],
                    check=True,
                    capture_output=True,
                    timeout=300,
                )
            elif plat == "linux":
                # Script shell — executa como bash
                subprocess.run(
                    ["bash", str(installer_path)],
                    check=True,
                    capture_output=True,
                    timeout=300,
                )
            elif plat == "darwin":
                # Extrai ZIP e move para Applications
                import zipfile
                app_dir = Path("/Applications")
                with zipfile.ZipFile(installer_path, "r") as z:
                    z.extractall(app_dir)
            return True
        except subprocess.CalledProcessError as exc:
            logger.error("Falha na instalação do Ollama: %s", exc)
            return False
        except Exception as exc:
            logger.error("Erro inesperado na instalação: %s", exc)
            return False

    @classmethod
    def verify(cls) -> bool:
        """Verifica se o Ollama está instalado e acessível."""
        # 1. Tenta via HTTP (daemon rodando)
        try:
            req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        # 2. Tenta via linha de comando
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
        except Exception:
            return False

    @classmethod
    def start_daemon(cls) -> bool:
        """Inicia o daemon 'ollama serve' em background."""
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if cls.detect_platform() == "windows"
                    else 0
                ),
            )
            return True
        except FileNotFoundError:
            logger.warning("Binário 'ollama' não encontrado no PATH.")
            return False
        except Exception as exc:
            logger.error("Erro ao iniciar daemon Ollama: %s", exc)
            return False
