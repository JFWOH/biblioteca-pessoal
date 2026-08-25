"""Monta o pacote portátil da Biblioteca Pessoal (rodada E4 do plano).

Produz o layout ZIP zero-fricção decidido em
``docs/agents/packaging_plan_2026-07.md``: Python 3.11 embutido + deps com
torch CPU, código do app, Kokoro pré-copiado (TTS offline de cara), manual em
PDF na raiz, lançador sem console e marcador ``portable.flag`` (ativa o
HF_HOME interno — ver ``src/main.py::_apply_portable_env``).

Uso na máquina de build (precisa de rede nos estágios runtime/deps):

    venv\\Scripts\\python.exe -m src.tools.build_package --out build\\BibliotecaPessoal
    venv\\Scripts\\python.exe -m src.tools.build_package --stages app,manual,leiame

Estágios (``--stages all`` é o padrão): runtime → deps → app → manual →
kokoro → compile → leiame → zip. Cada estágio é idempotente; rode de novo só
o que falhou.
"""

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from src.utils.constants import PROJECT_ROOT

EMBED_PY_URL = ("https://www.python.org/ftp/python/3.11.9/"
                "python-3.11.9-embed-amd64.zip")
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
TORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"

# O que do repositório ENTRA no pacote (o resto fica de fora por padrão).
APP_TREES = ("src", "resources")
# Dentro das árvores copiadas: nunca levar caches nem dados de desenvolvimento.
IGNORE_PATTERNS = ("__pycache__", "*.pyc", ".pytest_cache")
# Diretórios de 1º nível DENTRO de src/ que são dados de dev, não código.
SRC_DATA_DIRS = ("data",)

LAUNCHER_NAME = "Biblioteca Pessoal.bat"
DIAG_NAME = "Diagnostico.bat"

LEIAME = """Biblioteca Pessoal — versão de testes
=====================================

1. Extraia esta pasta inteira para qualquer lugar (ex.: Documentos).
2. Dê dois cliques em "Biblioteca Pessoal".

É só isso — o resto o aplicativo explica: o manual completo já está na
estante (e em "Manual - Biblioteca Pessoal.pdf", nesta pasta). Se o Windows
mostrar um aviso de aplicativo não reconhecido, clique em "Mais informações"
e depois em "Executar assim mesmo".

Problemas? Abra "Diagnostico.bat", tire um print da janela e envie junto com
a descrição do que aconteceu.
"""

LAUNCHER = """@echo off
rem Biblioteca Pessoal — lancador sem console (pacote portatil, rodada E4)
set "ROOT=%~dp0"
cd /d "%ROOT%"
start "Biblioteca Pessoal" "%ROOT%runtime\\pythonw.exe" -m src.main
"""

DIAG = """@echo off
rem Diagnostico: roda o app com console visivel para capturar erros.
set "ROOT=%~dp0"
cd /d "%ROOT%"
"%ROOT%runtime\\python.exe" -X faulthandler -m src.main
echo.
echo (fim da execucao — copie qualquer erro acima ao reportar)
pause
"""


def patch_embed_pth(text: str) -> str:
    """Ajusta o ``python311._pth`` do Python embutido para o layout do pacote.

    - habilita ``import site`` (necessário para o pip funcionar);
    - adiciona ``..`` (raiz do pacote → ``import src`` resolve);
    - adiciona ``Lib/site-packages`` (onde o pip instala as dependências).
    Função pura para ser testável sem baixar o runtime.
    """
    lines = [ln for ln in text.splitlines()]
    out = []
    for ln in lines:
        out.append("import site" if ln.strip() == "#import site" else ln)
    for extra in ("..", "Lib\\site-packages"):
        if extra not in out:
            out.append(extra)
    if "import site" not in out:
        out.append("import site")
    return "\n".join(out) + "\n"


def copy_app_tree(project_root: Path, out_root: Path) -> list[str]:
    """Copia ``src/`` e ``resources/`` para o pacote, sem caches nem dados dev.

    Devolve a lista (relativa) do que foi copiado no 1º nível — para log e
    testes. ``src/data`` (traces de desenvolvimento) fica de fora; o app cria
    o que precisa em runtime.
    """
    copied: list[str] = []
    ignore = shutil.ignore_patterns(*IGNORE_PATTERNS)
    for tree in APP_TREES:
        src_dir = project_root / tree
        if not src_dir.is_dir():
            continue
        dst = out_root / tree
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src_dir, dst, ignore=ignore)
        copied.append(tree)
    for data_dir in SRC_DATA_DIRS:
        candidate = out_root / "src" / data_dir
        if candidate.exists():
            shutil.rmtree(candidate)
    return copied


def write_root_files(out_root: Path) -> None:
    """LEIA-ME, lançadores e o marcador do modo portátil."""
    (out_root / "LEIA-ME.txt").write_text(LEIAME, encoding="utf-8")
    (out_root / LAUNCHER_NAME).write_text(LAUNCHER, encoding="utf-8")
    (out_root / DIAG_NAME).write_text(DIAG, encoding="utf-8")
    (out_root / "portable.flag").write_text(
        "Marcador do pacote portatil — ver src/main.py::_apply_portable_env\n",
        encoding="utf-8")
    (out_root / "data").mkdir(exist_ok=True)


def seed_kokoro(out_root: Path, hf_hub_dir: Path | None = None) -> bool:
    """Pré-copia o Kokoro-82M do cache HF da máquina de build para o pacote.

    Decisão do usuário: TTS funciona offline de cara (+~316 MB no ZIP). O
    destino segue o layout que ``_apply_portable_env`` ativa
    (``data/hf_cache/hub/...``). Sem o modelo no cache local (máquina que
    nunca narrou), avisa e segue — o download no 1º uso continua existindo.
    """
    if hf_hub_dir is None:
        hf_hub_dir = Path.home() / ".cache" / "huggingface" / "hub"
    src_model = hf_hub_dir / "models--hexgrad--Kokoro-82M"
    if not src_model.is_dir():
        print(f"[kokoro] AVISO: {src_model} não existe — pacote sai SEM o "
              "pré-seed (1ª narração fará o download).")
        return False
    dst = out_root / "data" / "hf_cache" / "hub" / src_model.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src_model, dst)
    print(f"[kokoro] pré-seed copiado para {dst}")
    return True


PIPER_VOICE_ID = "pt_BR-faber-medium"
PIPER_VOICE_BASE_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                        "pt/pt_BR/faber/medium/")


def seed_piper(out_root: Path, cache_dir: Path | None = None) -> bool:
    """Pré-seed da voz de RESERVA do TTS (Onda S.4/T.2, decisão R.4).

    O caso real de 2026-08-10 era exatamente "Kokoro lento SEM reserva
    instalada". Copia a voz pt-BR default do Piper para o layout portátil que
    o ``PiperProvider`` passou a varrer (``data/piper/models``): usa o cache
    local da máquina de build quando existir, senão baixa do repositório
    oficial (rhasspy/piper-voices, MIT, ~63MB). Os DOIS arquivos são
    obrigatórios (``.onnx`` órfão deixa o health_check True e a síntese
    falha), então falha parcial limpa o destino e o pacote sai SEM a reserva
    — com aviso honesto, como o seed do Kokoro.
    """
    files = (f"{PIPER_VOICE_ID}.onnx", f"{PIPER_VOICE_ID}.onnx.json")
    fontes = [p for p in (
        cache_dir,
        Path.home() / ".local" / "share" / "piper-tts" / "models",
        Path.home() / "piper-models",
    ) if p is not None]
    dst_dir = out_root / "data" / "piper" / "models"
    dst_dir.mkdir(parents=True, exist_ok=True)
    try:
        for nome in files:
            local = next((d / nome for d in fontes if (d / nome).is_file()), None)
            if local is not None:
                shutil.copy2(local, dst_dir / nome)
                print(f"[piper] {nome} copiado do cache local ({local.parent})")
            else:
                _download(PIPER_VOICE_BASE_URL + nome, dst_dir / nome)
    except Exception as exc:
        for nome in files:
            (dst_dir / nome).unlink(missing_ok=True)
        print(f"[piper] AVISO: pré-seed falhou ({exc}) — pacote sai SEM a voz "
              "de reserva (a cadeia de fallback fica só com o Kokoro).")
        return False
    print(f"[piper] voz de reserva pré-seedada em {dst_dir}")
    return True


def _download(url: str, dest: Path) -> None:
    print(f"[download] {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — URLs fixas oficiais


def stage_runtime(out_root: Path) -> None:
    """Python 3.11 embutido + pip, pronto para receber as dependências."""
    runtime = out_root / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    embed_zip = out_root / "_python-embed.zip"
    if not embed_zip.exists():
        _download(EMBED_PY_URL, embed_zip)
    with zipfile.ZipFile(embed_zip) as zf:
        zf.extractall(runtime)
    pth = runtime / "python311._pth"
    pth.write_text(patch_embed_pth(pth.read_text(encoding="utf-8")),
                   encoding="utf-8")
    get_pip = out_root / "_get-pip.py"
    if not get_pip.exists():
        _download(GET_PIP_URL, get_pip)
    subprocess.run([str(runtime / "python.exe"), str(get_pip),
                    "--no-warn-script-location"], check=True)


def stage_deps(out_root: Path, project_root: Path) -> None:
    """torch CPU primeiro (índice próprio), depois requirements.txt."""
    py = str(out_root / "runtime" / "python.exe")
    subprocess.run([py, "-m", "pip", "install", "torch",
                    "--index-url", TORCH_CPU_INDEX,
                    "--no-warn-script-location"], check=True)
    subprocess.run([py, "-m", "pip", "install", "-r",
                    str(project_root / "requirements.txt"),
                    "--no-warn-script-location"], check=True)


def stage_manual(out_root: Path) -> None:
    from src.tools.manual_pdf import generate_manual_pdf
    generate_manual_pdf(out_path=out_root / "Manual - Biblioteca Pessoal.pdf")


def stage_compile(out_root: Path) -> None:
    """Bytecode pré-compilado: menos I/O de import frio no 1º launch (P2)."""
    py = out_root / "runtime" / "python.exe"
    interpreter = str(py) if py.exists() else sys.executable
    subprocess.run([interpreter, "-m", "compileall", "-q",
                    str(out_root / "src")], check=True)


def stage_zip(out_root: Path) -> Path:
    print("[zip] compactando (pode demorar)…")
    archive = shutil.make_archive(str(out_root), "zip",
                                  root_dir=out_root.parent,
                                  base_dir=out_root.name)
    print(f"[zip] {archive}")
    return Path(archive)


ALL_STAGES = ("runtime", "deps", "app", "manual", "kokoro", "piper", "compile",
              "leiame", "zip")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(PROJECT_ROOT / "build" / "BibliotecaPessoal"))
    parser.add_argument("--stages", default="all",
                        help=f"CSV dentre: {','.join(ALL_STAGES)} (ou 'all')")
    args = parser.parse_args(argv)

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)
    stages = (list(ALL_STAGES) if args.stages == "all"
              else [s.strip() for s in args.stages.split(",") if s.strip()])
    unknown = [s for s in stages if s not in ALL_STAGES]
    if unknown:
        parser.error(f"estágios desconhecidos: {unknown}")

    for stage in stages:
        print(f"\n=== estágio: {stage} ===")
        if stage == "runtime":
            stage_runtime(out_root)
        elif stage == "deps":
            stage_deps(out_root, PROJECT_ROOT)
        elif stage == "app":
            copied = copy_app_tree(PROJECT_ROOT, out_root)
            print(f"[app] copiado: {copied}")
        elif stage == "manual":
            stage_manual(out_root)
        elif stage == "kokoro":
            seed_kokoro(out_root)
        elif stage == "piper":
            seed_piper(out_root)
        elif stage == "compile":
            stage_compile(out_root)
        elif stage == "leiame":
            write_root_files(out_root)
        elif stage == "zip":
            stage_zip(out_root)
    print("\nPacote pronto em:", out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
