"""Wizard de onboarding para instalação automática do Ollama.

Aparece automaticamente se o daemon Ollama não for detectado na porta 11434.
Guia o usuário pelo processo de instalação em 3 páginas, sem abrir terminal.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QDesktopServices
from PyQt6.QtCore import QUrl
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QStackedWidget, QFrame, QWidget,
)

from src.gui.workers.install_worker import OllamaInstallWorker


class OllamaWizardDialog(QDialog):
    """Wizard de 3 páginas para instalação automática do Ollama.

    Página 1: Explicação + escolha de ação
    Página 2: Download + progresso da instalação
    Página 3: Resultado (sucesso ou erro com instrução manual)
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configurar Assistente de IA")
        self.setFixedSize(520, 420)
        self.setModal(True)
        self._worker: OllamaInstallWorker | None = None
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header gradient ──────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1a1a2e, stop:1 #16213e);
            border-bottom: 1px solid #27272a;
        """)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)

        icon_lbl = QLabel("🤖")
        icon_lbl.setFont(QFont("Segoe UI Emoji", 28))
        h_layout.addWidget(icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Assistente de Biblioteca — Configuração")
        title.setStyleSheet("color: #e4e4e7; font-size: 14px; font-weight: 700;")
        sub = QLabel("Ollama não detectado na porta 11434")
        sub.setStyleSheet("color: #f59e0b; font-size: 11px;")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        h_layout.addLayout(title_col, stretch=1)

        root.addWidget(header)

        # ── Stack de páginas ─────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_welcome_page())
        self._stack.addWidget(self._build_progress_page())
        self._stack.addWidget(self._build_done_page())
        root.addWidget(self._stack, stretch=1)

    def _build_welcome_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0f0f17;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        desc = QLabel(
            "O <b>Assistente de Biblioteca</b> usa o <b>Ollama</b> para processar "
            "perguntas sobre seus livros 100% localmente, sem enviar dados à internet.\n\n"
            "O Ollama não foi detectado neste computador. Escolha uma opção:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #a1a1aa; font-size: 13px; line-height: 1.6;")
        layout.addWidget(desc)

        # Info box
        info = QFrame()
        info.setStyleSheet("""
            QFrame { background: #1a1a2e; border: 1px solid #2d2d4e;
                     border-radius: 8px; padding: 4px; }
        """)
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(16, 12, 16, 12)
        for txt in [
            "📦  ~600 MB de espaço em disco",
            "🔒  100% local — nenhum dado sai do seu computador",
            "🪟  Compatível com Windows, Linux e macOS",
        ]:
            lbl = QLabel(txt)
            lbl.setStyleSheet("color: #818cf8; font-size: 12px;")
            info_layout.addWidget(lbl)
        layout.addWidget(info)

        layout.addStretch()

        # Botões
        btn_install = QPushButton("⬇️  Instalar Ollama Automaticamente")
        btn_install.setFixedHeight(44)
        btn_install.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6366f1, stop:1 #818cf8);
                color: white; border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton:hover { background: #818cf8; }
        """)
        btn_install.clicked.connect(self._start_installation)
        layout.addWidget(btn_install)

        btn_manual = QPushButton("🔗  Já tenho o Ollama / Instalar manualmente")
        btn_manual.setFixedHeight(36)
        btn_manual.setStyleSheet("""
            QPushButton { background: transparent; color: #52525b;
                border: 1px solid #3f3f46; border-radius: 8px; font-size: 12px; }
            QPushButton:hover { color: #a1a1aa; border-color: #52525b; }
        """)
        btn_manual.clicked.connect(self._open_manual_page)
        layout.addWidget(btn_manual)

        btn_skip = QPushButton("Continuar sem o Assistente de IA")
        btn_skip.setFlat(True)
        btn_skip.setStyleSheet("color: #3f3f46; font-size: 11px;")
        btn_skip.clicked.connect(self.reject)
        layout.addWidget(btn_skip, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0f0f17;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(20)
        layout.addStretch()

        self._prog_icon = QLabel("⬇️")
        self._prog_icon.setFont(QFont("Segoe UI Emoji", 36))
        self._prog_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._prog_icon)

        self._prog_title = QLabel("Baixando Ollama…")
        self._prog_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_title.setStyleSheet("color: #e4e4e7; font-size: 15px; font-weight: 700;")
        layout.addWidget(self._prog_title)

        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setFixedHeight(8)
        self._prog_bar.setTextVisible(False)
        self._prog_bar.setStyleSheet("""
            QProgressBar { background: #27272a; border-radius: 4px; }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6366f1, stop:1 #a78bfa);
                border-radius: 4px;
            }
        """)
        layout.addWidget(self._prog_bar)

        self._prog_msg = QLabel("Iniciando…")
        self._prog_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_msg.setStyleSheet("color: #52525b; font-size: 11px;")
        layout.addWidget(self._prog_msg)

        layout.addStretch()

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet("""
            QPushButton { background: transparent; color: #52525b;
                border: 1px solid #3f3f46; border-radius: 6px;
                padding: 6px 20px; font-size: 11px; }
            QPushButton:hover { color: #f87171; border-color: #7f1d1d; }
        """)
        btn_cancel.clicked.connect(self._cancel_install)
        layout.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background-color: #0f0f17;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)
        layout.addStretch()

        self._done_icon = QLabel("✅")
        self._done_icon.setFont(QFont("Segoe UI Emoji", 48))
        self._done_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._done_icon)

        self._done_title = QLabel("Ollama instalado com sucesso!")
        self._done_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_title.setStyleSheet("color: #4ade80; font-size: 16px; font-weight: 700;")
        layout.addWidget(self._done_title)

        self._done_msg = QLabel("")
        self._done_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._done_msg.setWordWrap(True)
        self._done_msg.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(self._done_msg)

        layout.addStretch()

        self._done_btn = QPushButton("✨ Abrir Assistente de Biblioteca")
        self._done_btn.setFixedHeight(44)
        self._done_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #6366f1, stop:1 #818cf8);
                color: white; border: none; border-radius: 8px;
                font-size: 13px; font-weight: 700;
            }
            QPushButton:hover { background: #818cf8; }
        """)
        self._done_btn.clicked.connect(self.accept)
        layout.addWidget(self._done_btn)

        self._manual_btn = QPushButton("🔗 Instruções de instalação manual")
        self._manual_btn.setFlat(True)
        self._manual_btn.setStyleSheet("color: #52525b; font-size: 11px;")
        self._manual_btn.hide()
        self._manual_btn.clicked.connect(self._open_manual_page)
        layout.addWidget(self._manual_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        return page

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QDialog { background-color: #0f0f17; }
        """)

    # ── Ações ──────────────────────────────────────────────────────────────────

    def _start_installation(self) -> None:
        self._stack.setCurrentIndex(1)
        self._worker = OllamaInstallWorker()
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.install_complete.connect(self._on_install_complete)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self._prog_bar.setValue(pct)
        self._prog_msg.setText(msg)
        if pct >= 100:
            self._prog_title.setText("Instalando Ollama…")
            self._prog_icon.setText("⚙️")

    def _on_install_complete(self, success: bool, message: str) -> None:
        self._stack.setCurrentIndex(2)
        if success:
            self._done_icon.setText("✅")
            self._done_title.setText("Ollama instalado com sucesso!")
            self._done_title.setStyleSheet(
                "color: #4ade80; font-size: 16px; font-weight: 700;"
            )
            self._done_msg.setText(message)
            self._done_btn.show()
            self._manual_btn.hide()
        else:
            self._done_icon.setText("❌")
            self._done_title.setText("Não foi possível instalar automaticamente")
            self._done_title.setStyleSheet(
                "color: #f87171; font-size: 16px; font-weight: 700;"
            )
            self._done_msg.setText(message)
            self._done_btn.hide()
            self._manual_btn.show()

    def _cancel_install(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(3000)
        self.reject()

    def _open_manual_page(self) -> None:
        QDesktopServices.openUrl(QUrl("https://ollama.com/download"))

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(2000)
        super().closeEvent(event)
