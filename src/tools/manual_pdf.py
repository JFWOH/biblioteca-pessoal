"""Gera o PDF do manual do usuário a partir de ``docs/manual_usuario.md``.

Usa o próprio Qt do ambiente (markdown → HTML → QTextDocument → QPrinter em
modo PDF): zero dependência nova de build. Chamado pelo script do pacote
(rodada E4) e utilizável avulso:

    venv\\Scripts\\python.exe -m src.tools.manual_pdf [saida.pdf]
"""

import os
import sys
from pathlib import Path

from src.utils.constants import PROJECT_ROOT

MANUAL_MD = PROJECT_ROOT / "docs" / "manual_usuario.md"
DEFAULT_OUT = PROJECT_ROOT / "Manual - Biblioteca Pessoal.pdf"

# Estilo do PDF: legível em qualquer leitor, sem depender de fontes exóticas.
_HTML_TEMPLATE = (
    "<html><head><style>"
    "body {{ font-family: 'Segoe UI', sans-serif; font-size: 11pt; }}"
    "h1 {{ font-size: 20pt; }} h2 {{ font-size: 15pt; margin-top: 18px; }}"
    "table {{ border-collapse: collapse; }}"
    "td, th {{ border: 1px solid #999; padding: 4px 8px; }}"
    "code {{ font-family: Consolas, monospace; }}"
    "blockquote {{ color: #444; margin-left: 12px; }}"
    "</style></head><body>{body}</body></html>"
)


def generate_manual_pdf(md_path: Path = MANUAL_MD,
                        out_path: Path = DEFAULT_OUT) -> Path:
    """Converte o manual (Markdown) em PDF e devolve o caminho gerado."""
    # Headless por padrão (build/CI); numa sessão com display, não interfere.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import markdown
    from PyQt6.QtGui import QTextDocument
    from PyQt6.QtPrintSupport import QPrinter
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    body = markdown.markdown(
        Path(md_path).read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code"],
    )
    document = QTextDocument()
    document.setHtml(_HTML_TEMPLATE.format(body=body))

    printer = QPrinter()
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(out_path))
    document.print(printer)

    out = Path(out_path)
    if not out.exists() or out.stat().st_size == 0:
        raise RuntimeError(f"PDF do manual não foi gerado em {out}")
    return out


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    path = generate_manual_pdf(out_path=out)
    print(f"Manual gerado: {path} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
