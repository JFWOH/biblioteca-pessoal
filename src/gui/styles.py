"""Temas e estilos QSS para a aplicação."""

DARK_THEME = """
/* ── Reset e Base ─────────────────────────────────── */
QWidget {
    background-color: #0f1115;
    color: #e5e7eb;
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}

/* ── Janela Principal ─────────────────────────────── */
QMainWindow {
    background-color: #0f1115;
}

/* ── Menu ─────────────────────────────────────────── */
QMenuBar {
    background-color: #161920;
    border-bottom: 1px solid #2d333f;
    padding: 2px;
}
QMenuBar::item {
    padding: 6px 12px;
    border-radius: 4px;
}
QMenuBar::item:selected {
    background-color: #059669;
}
QMenu {
    background-color: #161920;
    border: 1px solid #2d333f;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #059669;
}

/* ── Barra de Ferramentas ─────────────────────────── */
QToolBar {
    background-color: #161920;
    border-bottom: 1px solid #2d333f;
    padding: 4px 8px;
    spacing: 4px;
}
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 8px 12px;
    color: #cbd5e1;
    font-size: 13px;
}
QToolButton:hover {
    background-color: #2d333f;
    color: #e5e7eb;
}
QToolButton:pressed {
    background-color: #20242d;
}

/* ── Barra Lateral ────────────────────────────────── */
#sidebar {
    background-color: #161920;
    border-right: 1px solid #2d333f;
}
#sidebar QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    color: #cbd5e1;
    font-size: 13px;
}
#sidebar QPushButton:hover {
    background-color: #2d333f;
    color: #e5e7eb;
}
#sidebar QPushButton:checked, #sidebar QPushButton[active="true"] {
    background-color: rgba(16, 185, 129, 0.15);
    color: #10b981;
    font-weight: 600;
}
#sidebar QLabel#sidebarSection {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    padding: 16px 16px 4px 16px;
    letter-spacing: 1px;
}

/* ── Cards de Livro ───────────────────────────────── */
#bookCard {
    background-color: #161920;
    border: 1px solid #2d333f;
    border-radius: 12px;
}
#bookCard:hover {
    border-color: #10b981;
    background-color: #20242d;
}
#bookCardTitle {
    font-size: 13px;
    font-weight: 600;
    color: #e5e7eb;
}
#bookCardAuthor {
    font-size: 11px;
    color: #94a3b8;
}

/* ── Busca ─────────────────────────────────────────── */
#searchContainer {
    background-color: #0f1115;
    border-bottom: 1px solid #2d333f;
}
#formatFilter {
    background-color: #18181b; border: 1px solid #27272a;
    border-radius: 8px; padding: 8px 12px; color: #e4e4e7;
}
#formatFilter:hover { border-color: #3f3f46; }
#formatFilter::drop-down { border: none; padding-right: 8px; }
#formatFilter QAbstractItemView {
    background-color: #18181b; border: 1px solid #27272a;
    selection-background-color: #10b981;
}

#searchBar {
    background-color: #161920;
    border: 1px solid #2d333f;
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #e5e7eb;
    font-size: 14px;
    min-height: 20px;
}
#searchBar:focus {
    border-color: #10b981;
    background-color: #20242d;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #059669;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #10b981;
}
QPushButton#primaryBtn:pressed {
    background-color: #047857;
}

QPushButton#secondaryBtn {
    background-color: #2d333f;
    color: #e5e7eb;
    border: 1px solid #20242d;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 500;
}
QPushButton#secondaryBtn:hover {
    background-color: #20242d;
}

/* ── ScrollBar ─────────────────────────────────────── */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2d333f;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #475569;
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
    background: #2d333f;
    border-radius: 4px;
    min-width: 30px;
}

/* ── Splitter ──────────────────────────────────────── */
QSplitter::handle {
    background-color: #2d333f;
}
QSplitter::handle:hover {
    background-color: #10b981;
}

/* ── Tab Widget ────────────────────────────────────── */
QTabWidget::pane {
    border: 1px solid #2d333f;
    border-radius: 8px;
    background-color: #0f1115;
}
QTabBar::tab {
    background-color: #161920;
    border: 1px solid #2d333f;
    border-bottom: none;
    padding: 8px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #94a3b8;
}
QTabBar::tab:selected {
    background-color: #0f1115;
    color: #e5e7eb;
    border-bottom: 2px solid #10b981;
}

/* ── Status Bar ────────────────────────────────────── */
QStatusBar {
    background-color: #161920;
    border-top: 1px solid #2d333f;
    color: #94a3b8;
    font-size: 12px;
}

/* ── Progress Bar ──────────────────────────────────── */
QProgressBar {
    background-color: #2d333f;
    border-radius: 4px;
    text-align: center;
    color: #e5e7eb;
    font-size: 11px;
    max-height: 8px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #059669, stop:1 #34d399);
    border-radius: 4px;
}

/* ── Tooltip ───────────────────────────────────────── */
QToolTip {
    background-color: #20242d;
    border: 1px solid #2d333f;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e5e7eb;
    font-size: 12px;
}

/* ── Labels de Estatísticas ─────────────────────────── */
#statValue {
    font-size: 28px;
    font-weight: 700;
    color: #10b981;
}
#statLabel {
    font-size: 11px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ── Badges ────────────────────────────────────────── */
#badge {
    background-color: #059669;
    color: white;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}
#badgeWarning {
    background-color: #f59e0b;
    color: #0f1115;
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
    background-color: #059669;
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
    background-color: rgba(16, 185, 129, 0.1);
    color: #059669;
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
    border-color: #059669;
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
#searchContainer {
    background-color: #f4f4f5;
    border-bottom: 1px solid #e4e4e7;
}
#formatFilter {
    background-color: #ffffff; border: 1px solid #d4d4d8;
    border-radius: 8px; padding: 8px 12px; color: #1A1A1A;
}
#formatFilter:hover { border-color: #a1a1aa; }
#formatFilter::drop-down { border: none; padding-right: 8px; }
#formatFilter QAbstractItemView {
    background-color: #ffffff; border: 1px solid #d4d4d8;
    selection-background-color: #059669;
}

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
    border-color: #059669;
    background-color: #ffffff;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #059669;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #10b981;
}
QPushButton#primaryBtn:pressed {
    background-color: #047857;
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
    background-color: #059669;
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
    border-bottom: 2px solid #059669;
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
        stop:0 #059669, stop:1 #34d399);
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
    color: #059669;
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
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
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
    background-color: #059669;
    color: white;
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
    background-color: #059669;
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
    background-color: rgba(16, 185, 129, 0.1);
    color: #059669;
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
    border-color: #059669;
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
#searchContainer {
    background-color: #EADFCA;
    border-bottom: 1px solid #d4cbb8;
}
#formatFilter {
    background-color: #F4ECD8; border: 1px solid #d4cbb8;
    border-radius: 8px; padding: 8px 12px; color: #433422;
}
#formatFilter:hover { border-color: #059669; }
#formatFilter::drop-down { border: none; padding-right: 8px; }
#formatFilter QAbstractItemView {
    background-color: #F4ECD8; border: 1px solid #d4cbb8;
    selection-background-color: #059669;
}

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
    border-color: #059669;
    background-color: #EADFCA;
}

/* ── Botões Principais ─────────────────────────────── */
QPushButton#primaryBtn {
    background-color: #059669;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
}
QPushButton#primaryBtn:hover {
    background-color: #10b981;
}
QPushButton#primaryBtn:pressed {
    background-color: #047857;
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
    background-color: #059669;
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
    border-bottom: 2px solid #059669;
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
        stop:0 #059669, stop:1 #34d399);
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
    color: #059669;
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
    background-color: #10b981;
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
    background-color: #0f1115;
    color: #e5e7eb;
    font-family: 'Georgia', 'Palatino', serif;
    font-size: 16px;
    line-height: 1.8;
    max-width: 720px;
    margin: 0 auto;
    padding: 40px 60px;
}
h1, h2, h3 { color: #a7f3d0; font-family: 'Segoe UI', sans-serif; }
h1 { font-size: 28px; border-bottom: 1px solid #2d333f; padding-bottom: 12px; }
h2 { font-size: 22px; }
a { color: #10b981; }
pre, code { background: #161920; padding: 2px 6px; border-radius: 4px; font-size: 14px; }
blockquote { border-left: 3px solid #059669; padding-left: 16px; color: #94a3b8; }
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
a { color: #059669; }
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
