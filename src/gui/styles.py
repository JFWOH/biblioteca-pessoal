"""Temas e estilos QSS para a aplicação."""

DARK_THEME = """
/* ── Reset e Base ─────────────────────────────────── */
QWidget {
    background-color: #0f0f17;
    color: #e4e4e7;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

/* ── Janela Principal ─────────────────────────────── */
QMainWindow {
    background-color: #0f0f17;
}

/* ── Menu ─────────────────────────────────────────── */
QMenuBar {
    background-color: #18181b;
    border-bottom: 1px solid #27272a;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #6366f1;
}
QMenu {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #6366f1;
}

/* ── Barra de Ferramentas ─────────────────────────── */
QToolBar {
    background-color: #18181b;
    border-bottom: 1px solid #27272a;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: #a1a1aa;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #27272a;
    color: #e4e4e7;
}
QToolButton:pressed {
    background-color: #3f3f46;
}

/* ── Barra Lateral ────────────────────────────────── */
#sidebar {
    background-color: #18181b;
    border-right: 1px solid #27272a;
}
#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    color: #a1a1aa;
    font-size: 13px;
}
#sidebar QPushButton:hover {
    background-color: #27272a;
    color: #e4e4e7;
}
#sidebar QPushButton:checked, #sidebar QPushButton[active="true"] {
    background-color: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    font-weight: 600;
}
#sidebar QLabel#sidebarSection {
    color: #52525b;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 16px 16px 4px 16px;
    letter-spacing: 1px;
}

/* ── Cards de Livro ───────────────────────────────── */
#bookCard {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 12px;
}
#bookCard:hover {
    border-color: #6366f1;
    background-color: #1e1e24;
}
#bookCardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #e4e4e7;
}
#bookCardAuthor {
    font-size: 11px;
    color: #71717a;
}

/* ── Busca ─────────────────────────────────────────── */
#searchBar {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #e4e4e7;
    font-size: 14px;
    min-height: 20px;
}
#searchBar:focus {
    border-color: #6366f1;
    background-color: #1c1c24;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #6366f1;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #818cf8;
}
QPushButton#primaryBtn:pressed {
    background-color: #4f46e5;
}

QPushButton#secondaryBtn {
    background-color: #27272a;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover {
    background-color: #3f3f46;
}

/* ── ScrollBar ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #3f3f46;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #52525b;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #3f3f46;
    border-radius: 4px;
    min-width: 30px;
}

/* ── Splitter ──────────────────────────────────────── */
QSplitter::handle {
    background-color: #27272a;
}
QSplitter::handle:hover {
    background-color: #6366f1;
}

/* ── Tab Widget ────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #27272a;
    border-radius: 8px;
    background-color: #0f0f17;
}
QTabBar::tab {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-bottom: none;
    padding: 8px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #71717a;
}
QTabBar::tab:selected {
    background-color: #0f0f17;
    color: #e4e4e7;
    border-bottom: 2px solid #6366f1;
}

/* ── Status Bar ────────────────────────────────────── */
QStatusBar {
    background-color: #18181b;
    border-top: 1px solid #27272a;
    color: #71717a;
    font-size: 12px;
}

/* ── Progress Bar ──────────────────────────────────── */
QProgressBar {
    background-color: #27272a;
    border-radius: 4px;
    text-align: center;
    color: #e4e4e7;
    font-size: 11px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #a78bfa);
    border-radius: 4px;
}

/* ── Tooltip ───────────────────────────────────────── */
QToolTip {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e4e4e7;
    font-size: 12px;
}

/* ── Labels de Estatísticas ─────────────────────────── */
#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #818cf8;
}
#statLabel {
    font-size: 11px;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Badges ────────────────────────────────────────── */
#badge {
    background-color: #6366f1;
    color: white;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#badgeWarning {
    background-color: #f59e0b;
    color: #18181b;
}
#badgeSuccess {
    background-color: #10b981;
    color: white;
}
"""

LIGHT_THEME = """
/* ── Reset e Base ─────────────────────────────────── */
QWidget {
    background-color: #FFFFFF;
    color: #1A1A1A;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

/* ── Janela Principal ─────────────────────────────── */
QMainWindow {
    background-color: #FFFFFF;
}

/* ── Menu ─────────────────────────────────────────── */
QMenuBar {
    background-color: #f4f4f5;
    border-bottom: 1px solid #e4e4e7;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #e4e4e7;
}
QMenu {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #6366f1;
    color: white;
}

/* ── Barra de Ferramentas ─────────────────────────── */
QToolBar {
    background-color: #f4f4f5;
    border-bottom: 1px solid #e4e4e7;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: #555555;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #e4e4e7;
    color: #1A1A1A;
}
QToolButton:pressed {
    background-color: #d4d4d8;
}

/* ── Barra Lateral ────────────────────────────────── */
#sidebar {
    background-color: #f4f4f5;
    border-right: 1px solid #e4e4e7;
}
#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    color: #555555;
    font-size: 13px;
}
#sidebar QPushButton:hover {
    background-color: #e4e4e7;
    color: #1A1A1A;
}
#sidebar QPushButton:checked, #sidebar QPushButton[active="true"] {
    background-color: rgba(99, 102, 241, 0.1);
    color: #6366f1;
    font-weight: 600;
}
#sidebar QLabel#sidebarSection {
    color: #555555;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 16px 16px 4px 16px;
    letter-spacing: 1px;
}

/* ── Cards de Livro ───────────────────────────────── */
#bookCard {
    background-color: #ffffff;
    border: 1px solid #e4e4e7;
    border-radius: 12px;
}
#bookCard:hover {
    border-color: #6366f1;
    background-color: #f4f4f5;
}
#bookCardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #1A1A1A;
}
#bookCardAuthor {
    font-size: 11px;
    color: #555555;
}

/* ── Busca ─────────────────────────────────────────── */
#searchBar {
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #1A1A1A;
    font-size: 14px;
    min-height: 20px;
}
#searchBar:focus {
    border-color: #6366f1;
    background-color: #ffffff;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #6366f1;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #4f46e5;
}
QPushButton#primaryBtn:pressed {
    background-color: #4338ca;
}

QPushButton#secondaryBtn {
    background-color: #ffffff;
    color: #1A1A1A;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover {
    background-color: #f4f4f5;
}

/* ── ScrollBar ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #d4d4d8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #a1a1aa;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #d4d4d8;
    border-radius: 4px;
    min-width: 30px;
}

/* ── Splitter ──────────────────────────────────────── */
QSplitter::handle {
    background-color: #e4e4e7;
}
QSplitter::handle:hover {
    background-color: #6366f1;
}

/* ── Tab Widget ────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    background-color: #ffffff;
}
QTabBar::tab {
    background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-bottom: none;
    padding: 8px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #555555;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #1A1A1A;
    border-bottom: 2px solid #6366f1;
}

/* ── Status Bar ────────────────────────────────────── */
QStatusBar {
    background-color: #f4f4f5;
    border-top: 1px solid #e4e4e7;
    color: #555555;
    font-size: 12px;
}

/* ── Progress Bar ──────────────────────────────────── */
QProgressBar {
    background-color: #e4e4e7;
    border-radius: 4px;
    text-align: center;
    color: #1A1A1A;
    font-size: 11px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #a78bfa);
    border-radius: 4px;
}

/* ── Tooltip ───────────────────────────────────────── */
QToolTip {
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1A1A1A;
    font-size: 12px;
}

/* ── Labels de Estatísticas ─────────────────────────── */
#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #6366f1;
}
#statLabel {
    font-size: 11px;
    color: #555555;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Badges ────────────────────────────────────────── */
#badge {
    background-color: #e4e4e7;
    color: #1A1A1A;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#badgeWarning {
    background-color: #f59e0b;
    color: white;
}
#badgeSuccess {
    background-color: #10b981;
    color: white;
}
"""

SEPIA_THEME = """
/* ── Reset e Base ─────────────────────────────────── */
QWidget {
    background-color: #F4ECD8;
    color: #433422;
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 14px;
}

/* ── Janela Principal ─────────────────────────────── */
QMainWindow {
    background-color: #F4ECD8;
}

/* ── Menu ─────────────────────────────────────────── */
QMenuBar {
    background-color: #EADFCA;
    border-bottom: 1px solid #d4cbb8;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #dfd8c8;
}
QMenu {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #8b6c42;
    color: white;
}

/* ── Barra de Ferramentas ─────────────────────────── */
QToolBar {
    background-color: #EADFCA;
    border-bottom: 1px solid #d4cbb8;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: #705E4B;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #dfd8c8;
    color: #433422;
}
QToolButton:pressed {
    background-color: #d4cbb8;
}

/* ── Barra Lateral ────────────────────────────────── */
#sidebar {
    background-color: #EADFCA;
    border-right: 1px solid #d4cbb8;
}
#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    color: #705E4B;
    font-size: 13px;
}
#sidebar QPushButton:hover {
    background-color: #dfd8c8;
    color: #433422;
}
#sidebar QPushButton:checked, #sidebar QPushButton[active="true"] {
    background-color: rgba(139, 108, 66, 0.15);
    color: #8b6c42;
    font-weight: 600;
}
#sidebar QLabel#sidebarSection {
    color: #705E4B;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 16px 16px 4px 16px;
    letter-spacing: 1px;
}

/* ── Cards de Livro ───────────────────────────────── */
#bookCard {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 12px;
}
#bookCard:hover {
    border-color: #8b6c42;
    background-color: #dfd8c8;
}
#bookCardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #433422;
}
#bookCardAuthor {
    font-size: 11px;
    color: #705E4B;
}

/* ── Busca ─────────────────────────────────────────── */
#searchBar {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #433422;
    font-size: 14px;
    min-height: 20px;
}
#searchBar:focus {
    border-color: #8b6c42;
    background-color: #EADFCA;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #8b6c42;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #705633;
}
QPushButton#primaryBtn:pressed {
    background-color: #5c4426;
}

QPushButton#secondaryBtn {
    background-color: #EADFCA;
    color: #433422;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover {
    background-color: #dfd8c8;
}

/* ── ScrollBar ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #d4cbb8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #b8a890;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #d4cbb8;
    border-radius: 4px;
    min-width: 30px;
}

/* ── Splitter ──────────────────────────────────────── */
QSplitter::handle {
    background-color: #d4cbb8;
}
QSplitter::handle:hover {
    background-color: #8b6c42;
}

/* ── Tab Widget ────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    background-color: #EADFCA;
}
QTabBar::tab {
    background-color: #ebe5d9;
    border: 1px solid #d4cbb8;
    border-bottom: none;
    padding: 8px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #705E4B;
}
QTabBar::tab:selected {
    background-color: #EADFCA;
    color: #433422;
    border-bottom: 2px solid #8b6c42;
}

/* ── Status Bar ────────────────────────────────────── */
QStatusBar {
    background-color: #ebe5d9;
    border-top: 1px solid #d4cbb8;
    color: #705E4B;
    font-size: 12px;
}

/* ── Progress Bar ──────────────────────────────────── */
QProgressBar {
    background-color: #d4cbb8;
    border-radius: 4px;
    text-align: center;
    color: #433422;
    font-size: 11px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #8b6c42, stop:1 #b89c72);
    border-radius: 4px;
}

/* ── Tooltip ───────────────────────────────────────── */
QToolTip {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #433422;
    font-size: 12px;
}

/* ── Labels de Estatísticas ─────────────────────────── */
#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #8b6c42;
}
#statLabel {
    font-size: 11px;
    color: #705E4B;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Badges ────────────────────────────────────────── */
#badge {
    background-color: #d4cbb8;
    color: #433422;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#badgeWarning {
    background-color: #d97706;
    color: white;
}
#badgeSuccess {
    background-color: #059669;
    color: white;
}
"""

THEMES = {
    "dark": DARK_THEME,
    "light": LIGHT_THEME,
    "sepia": SEPIA_THEME,
}


def get_theme(name: str) -> str:
    """Retorna a stylesheet QSS para o tema especificado."""
    return THEMES.get(name, DARK_THEME)


# ── CSS para o leitor HTML (EPUB, TXT, DOCX) ──────────────────────────

READER_CSS_DARK = """
body {
    background-color: #0f0f17;
    color: #e4e4e7;
    font-family: 'Georgia', 'Palatino', serif;
    font-size: 16px;
    line-height: 1.8;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 60px;
}
h1, h2, h3 { color: #c7d2fe; font-family: 'Segoe UI', sans-serif; }
h1 { font-size: 28px; border-bottom: 1px solid #27272a; padding-bottom: 12px; }
h2 { font-size: 22px; }
a { color: #818cf8; }
pre, code { background: #18181b; padding: 2px 6px; border-radius: 4px; font-size: 14px; }
blockquote { border-left: 3px solid #6366f1; padding-left: 16px; color: #a1a1aa; }
img { max-width: 100%; border-radius: 8px; }
"""

READER_CSS_LIGHT = """
body {
    background-color: #ffffff;
    color: #1a1a1a;
    font-family: 'Georgia', 'Palatino', serif;
    font-size: 16px;
    line-height: 1.8;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 60px;
}
h1, h2, h3 { color: #1a1a1a; }
a { color: #6366f1; }
"""

READER_CSS_SEPIA = """
body {
    background-color: #f5f0e8;
    color: #3e2f1c;
    font-family: 'Georgia', 'Palatino', serif;
    font-size: 16px;
    line-height: 1.8;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 60px;
}
h1, h2, h3 { color: #5c4426; }
a { color: #8b6c42; }
"""

READER_THEMES = {"dark": READER_CSS_DARK, "light": READER_CSS_LIGHT, "sepia": READER_CSS_SEPIA}


def get_reader_css(theme: str) -> str:
    return READER_THEMES.get(theme, READER_CSS_DARK)
