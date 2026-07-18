"""Temas e estilos QSS para a aplicação."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap

from src.utils.constants import (
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    DEFAULT_LINE_HEIGHT,
)

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
#bookCard[selected="true"] {
    border: 2px solid #6366f1;
    border-radius: 12px;
    background-color: rgba(99, 102, 241, 0.12);
}
#bookCoverImage {
    border-radius: 8px;
    background-color: #27272a;
}
#bookCoverPlaceholder {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #312e81, stop:1 #1e1b4b);
    font-size: 48px;
    color: #818cf8;
}
#bookCoverBroken {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #451a03, stop:1 #78350f);
    font-size: 48px;
    color: #f59e0b;
    border: 2px solid #f59e0b;
}
#bookCardBrokenBadge {
    color: #f59e0b;
    font-size: 8px;
    font-weight: 700;
}
QProgressBar#bookCardProgress {
    background-color: #2d333f; border: none; border-radius: 2px;
}
QProgressBar#bookCardProgress::chunk {
    background-color: #10b981; border-radius: 2px;
}
QMenu#bookCardContextMenu {
    background-color: #161920; border: 1px solid #2d333f;
    border-radius: 8px; padding: 4px;
}
QMenu#bookCardContextMenu::item {
    padding: 8px 24px; border-radius: 4px; color: #e5e7eb;
}
QMenu#bookCardContextMenu::item:selected { background-color: #10b981; color: #06281e; }
QMenu#bookCardContextMenu::separator { height: 1px; background: #2d333f; margin: 4px 8px; }

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

/* ── Busca no conteúdo (Tarefa 5.1) ─────────────────── */
QCheckBox#contentToggle { color: #cbd5e1; spacing: 6px; padding: 4px 6px; }
QCheckBox#contentToggle::indicator {
    width: 16px; height: 16px; border: 1px solid #2d333f;
    border-radius: 4px; background-color: #161920;
}
QCheckBox#contentToggle::indicator:checked {
    background-color: #10b981; border-color: #10b981;
}
#contentSearchResults { background-color: #0f1115; }
#contentSearchTitle { font-size: 16px; font-weight: 600; color: #e5e7eb; }
#contentSearchCount { color: #94a3b8; font-size: 12px; }
QPushButton#contentSearchBack {
    background-color: #2d333f; color: #e5e7eb; border: 1px solid #20242d;
    border-radius: 8px; padding: 6px 14px; font-weight: 600;
}
QPushButton#contentSearchBack:hover { background-color: #3a424f; }
#contentResultRow {
    background-color: #161920; border: 1px solid #2d333f; border-radius: 10px;
}
#contentResultRow:hover { border-color: #10b981; background-color: #1b2029; }
#contentResultBook { color: #e5e7eb; font-weight: 600; font-size: 13px; }
#contentResultSnippet { color: #cbd5e1; font-size: 12px; }
#contentSearchEmpty { color: #94a3b8; font-size: 14px; padding: 40px; }
#contentSearchFooter { color: #94a3b8; font-size: 12px; padding-top: 4px; }

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

/* ── Estatísticas vivas (Tarefa 5.2) ─────────────────── */
#statsSectionTitle {
    color: #e4e4e7;
    font-size: 13px;
    font-weight: 600;
}
#statsEmptyHint {
    color: #71717a;
    font-size: 12px;
    font-style: italic;
}
#statsGoalCaption {
    color: #a1a1aa;
    font-size: 12px;
}
#weeklyBarTrack {
    background-color: #2d333f;
    border-radius: 4px;
}
#weeklyBarFill {
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
        stop:0 #059669, stop:1 #34d399);
    border-radius: 4px;
}
#weeklyBarLabel {
    color: #71717a;
    font-size: 10px;
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

/* ── Painel de Detalhes do Livro ──────────────────── */
#bookDetailsCover {
    border-radius: 8px;
    background: #18181b;
}
#bookDetailsCoverPlaceholder {
    border-radius: 8px;
    background: #18181b;
    font-size: 64px;
}
#bookDetailsTitle {
    color: #e4e4e7;
}
#bookDetailsAuthor {
    color: #818cf8;
    font-size: 13px;
}
#bookDetailsMeta {
    color: #71717a;
    font-size: 12px;
    line-height: 1.5;
}
#bookDetailsMutedText {
    color: #a1a1aa;
    font-size: 12px;
}
#bookDetailsSectionHeader {
    color: #71717a;
    font-size: 11px;
    font-weight: 600;
}
QScrollArea#bookDetailsScroll {
    border: none;
    background: transparent;
}
#bookDetailsScrollContent {
    background: transparent;
}
#bookDetailsActionBar {
    background: transparent;
    border-top: 1px solid #2d333f;
}
QPushButton#dangerBtn {
    background: transparent;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 10px;
    color: #ef4444;
}
QPushButton#dangerBtn:hover {
    background: rgba(239, 68, 68, 0.1);
    border-color: #ef4444;
}
QPushButton#bookDetailsRelatedBtn {
    background: transparent;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px;
    color: #a5b4fc;
    font-size: 11px;
    text-align: left;
}
QPushButton#bookDetailsRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Diálogo de Coleções ───────────────────────────── */
#collectionDialogTitle {
    color: #e4e4e7;
}
#collectionDialogSubtitle {
    color: #71717a;
    font-size: 12px;
}
#collectionCreateFrame {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 8px;
}
#collectionNewNameInput {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #e4e4e7;
    font-size: 13px;
}
#collectionNewNameInput:focus {
    border-color: #6366f1;
}
QPushButton#collectionCreateBtn {
    background: #6366f1;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: white;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#collectionCreateBtn:hover {
    background: #818cf8;
}
#collectionList {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 8px;
    color: #e4e4e7;
    font-size: 13px;
}
#collectionList::item {
    padding: 10px 14px;
    border-bottom: 1px solid #1e1e24;
}
#collectionList::item:selected {
    background: rgba(99, 102, 241, 0.15);
}
#collectionList::item:hover {
    background: #18181b;
}
#addToCollectionList {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 8px;
    color: #e4e4e7;
    font-size: 13px;
}
#addToCollectionList::item {
    padding: 8px 12px;
}
QPushButton#dangerBtnSmall {
    background: transparent;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 8px 16px;
    color: #ef4444;
    font-size: 12px;
}
QPushButton#dangerBtnSmall:hover {
    background: rgba(239, 68, 68, 0.1);
    border-color: #ef4444;
}

/* ── Diálogo de Importação ─────────────────────────── */
#importDialogTitle {
    color: #e4e4e7;
}
#importDialogSubtitle {
    color: #71717a;
    font-size: 13px;
}
QGroupBox#importFilesGroup {
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
    color: #a1a1aa;
    font-size: 12px;
}
QGroupBox#importFilesGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
#importFileList {
    background: #0f0f17;
    border: none;
    border-radius: 6px;
    color: #e4e4e7;
    font-size: 12px;
}
#importFileList::item {
    padding: 6px 10px;
    border-bottom: 1px solid #1e1e24;
}
#importFileList::item:selected {
    background: rgba(99, 102, 241, 0.15);
}
#importFilesCount {
    color: #52525b;
    font-size: 11px;
}
#importOptionCheckbox {
    color: #a1a1aa;
    font-size: 12px;
}
#importProgressLabel {
    color: #71717a;
    font-size: 12px;
}
#importLog {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 8px;
    color: #71717a;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}

/* ── Diálogo de Exportação Anki ────────────────────── */
#ankiDeckLabel {
    font-weight: bold;
}
#ankiFrontLabel {
    font-weight: bold;
    color: #059669;
}
#ankiBackLabel {
    font-weight: bold;
    color: #2563eb;
}
#ankiStatusChecking {
    color: #64748b;
    font-size: 11px;
}
#ankiStatusConnected {
    color: #059669;
    font-size: 11px;
}
#ankiStatusOffline {
    color: #d97706;
    font-size: 11px;
}
QPushButton#ankiSaveBtn {
    background-color: #10b981;
    color: white;
    font-weight: bold;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}
QPushButton#ankiSaveBtn:hover {
    background-color: #059669;
}
QPushButton#ankiSaveBtn:disabled {
    background-color: #94a3b8;
}

/* ── Diálogo do Dossiê do Livro ─────────────────────── */
QDialog#bookDossierDialog {
    background-color: #0f1115;
}
QScrollArea#dossierScroll {
    border: none;
    background: transparent;
}
#dossierContent {
    background: transparent;
}
#dossierSectionHeader {
    color: #71717a;
    font-size: 11px;
    font-weight: 600;
}
#dossierBody {
    color: #cbd5e1;
    font-size: 12px;
}
QFrame#dossierCard {
    background-color: #20242d;
    border: 1px solid #2d333f;
    border-radius: 8px;
}
#dossierCover {
    background: #18181b;
    border-radius: 6px;
    font-size: 28px;
}
#dossierBookTitle {
    color: #e5e7eb;
    font-size: 16px;
    font-weight: 700;
}
#dossierBookAuthor {
    color: #818cf8;
    font-size: 12px;
}
#dossierProgress {
    color: #71717a;
    font-size: 11px;
}
QPushButton#dossierRelatedBtn {
    background: transparent;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 8px;
    color: #a5b4fc;
    font-size: 12px;
    text-align: left;
}
QPushButton#dossierRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Gerenciador de Tags ───────────────────────────── */
#tagManagerHeader {
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#tagAddBtn {
    background: rgba(99, 102, 241, 0.15);
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
    color: #818cf8;
    font-size: 11px;
    font-weight: 600;
}
#tagManagerEmptyLabel {
    color: #52525b;
    font-size: 11px;
}
#addTagDialogTitle {
    color: #e4e4e7;
}
#addTagList {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #e4e4e7;
    font-size: 12px;
}
#addTagNameInput {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e4e4e7;
    font-size: 12px;
}

/* ── Diálogo de Configurações ──────────────────────── */
#settingsDialogTitle {
    color: #e4e4e7;
}
QGroupBox#settingsGroup {
    border: 1px solid #27272a;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    padding-top: 24px;
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox#settingsGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QGroupBox#settingsGroup QLabel {
    color: #a1a1aa;
    font-size: 12px;
}
QGroupBox#settingsGroup QCheckBox {
    color: #a1a1aa;
    font-size: 12px;
}
#settingsNumericInput {
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 4px 8px;
    color: #e4e4e7;
}
#settingsWatchList {
    background: #0f0f17;
    border: 1px solid #27272a;
    border-radius: 6px;
    color: #e4e4e7;
    font-size: 12px;
}
#settingsAdvancedWarning {
    color: #d97706;
    font-size: 11px;
    font-style: italic;
}

/* ── Diálogo de Atalhos de Teclado ──────────────────── */
QGroupBox#settingsGroup QLabel#shortcutKeyBadge {
    background: #18181b;
    border: 1px solid #27272a;
    border-radius: 4px;
    padding: 2px 8px;
    color: #e4e4e7;
    font-family: 'Consolas', 'Courier New', monospace;
    font-weight: 600;
    font-size: 11px;
}

/* ── Diálogo de Flashcards ─────────────────────────── */
QFrame#flashcardItem {
    background-color: #20242d;
    border: 1px solid #2d333f;
    border-radius: 8px;
}
#flashcardBadgeNew {
    color: #10b981;
    font-size: 10px;
    font-weight: 600;
}
#flashcardBadgeDue {
    color: #94a3b8;
    font-size: 10px;
}
#flashcardOrigin {
    color: #818cf8;
    font-size: 10px;
}
QPushButton#flashcardDeleteBtn {
    background: transparent;
    border: none;
    color: #52525b;
    font-size: 12px;
}
QPushButton#flashcardDeleteBtn:hover {
    color: #ef4444;
}
#flashcardFront {
    color: #e5e7eb;
    font-size: 13px;
    font-weight: 600;
}
#flashcardBack {
    color: #cbd5e1;
    font-size: 12px;
}
QDialog#flashcardsDialog {
    background-color: #0f1115;
}
#flashcardsTitle {
    color: #e5e7eb;
    font-size: 16px;
    font-weight: 700;
}
QComboBox#flashcardsBookFilter {
    background: #161920;
    border: 1px solid #2d333f;
    border-radius: 6px;
    padding: 5px 8px;
    color: #e4e4e7;
    font-size: 12px;
}
QComboBox#flashcardsBookFilter QAbstractItemView {
    background: #161920;
    color: #e4e4e7;
    selection-background-color: #2d333f;
}
QPushButton#flashcardsStudyBtn {
    background: #10b981;
    color: #06281e;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsStudyBtn:hover {
    background: #34d399;
}
QPushButton#flashcardsStudyBtn:disabled {
    background: #1f2937;
    color: #4b5563;
}
#flashcardsEmptyLabel {
    color: #6b7280;
    font-size: 13px;
}
#flashcardsCountLabel {
    color: #52525b;
    font-size: 11px;
}
#flashcardsProgressLabel {
    color: #94a3b8;
    font-size: 12px;
}
QFrame#flashcardsStudyCard {
    background: #161920;
    border: 1px solid #2d333f;
    border-radius: 10px;
}
#flashcardsStudyFront {
    color: #e5e7eb;
    font-size: 15px;
    font-weight: 600;
}
QFrame#flashcardsStudySep {
    background: #2d333f;
}
#flashcardsStudyBack {
    color: #cbd5e1;
    font-size: 14px;
}
QPushButton#flashcardsRevealBtn {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#flashcardsRevealBtn:hover {
    background: #1d4ed8;
}
QPushButton#flashcardsGradeAgain {
    background: transparent;
    color: #ef4444;
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeAgain:hover {
    background: #ef4444;
    color: #0f1115;
}
QPushButton#flashcardsGradeHard {
    background: transparent;
    color: #f59e0b;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeHard:hover {
    background: #f59e0b;
    color: #0f1115;
}
QPushButton#flashcardsGradeGood {
    background: transparent;
    color: #10b981;
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeGood:hover {
    background: #10b981;
    color: #0f1115;
}
QPushButton#flashcardsGradeEasy {
    background: transparent;
    color: #3b82f6;
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeEasy:hover {
    background: #3b82f6;
    color: #0f1115;
}
QPushButton#flashcardsBackBtn {
    background: transparent;
    color: #94a3b8;
    border: none;
    font-size: 12px;
}
QPushButton#flashcardsBackBtn:hover {
    color: #e5e7eb;
}

/* ── Wizard de Instalação do Ollama ────────────────── */
QDialog#wizardDialog {
    background-color: #0f0f17;
}
#wizardHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a1a2e, stop:1 #16213e);
    border-bottom: 1px solid #27272a;
}
#wizardHeaderTitle {
    color: #e4e4e7;
    font-size: 14px;
    font-weight: 700;
}
#wizardHeaderSub {
    color: #f59e0b;
    font-size: 11px;
}
#wizardPage {
    background-color: #0f0f17;
}
#wizardDesc {
    color: #a1a1aa;
    font-size: 13px;
    line-height: 1.6;
}
QFrame#wizardInfoBox {
    background: #1a1a2e;
    border: 1px solid #2d2d4e;
    border-radius: 8px;
    padding: 4px;
}
#wizardInfoItem {
    color: #818cf8;
    font-size: 12px;
}
QPushButton#wizardInstallBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #818cf8);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#wizardInstallBtn:hover {
    background: #818cf8;
}
QPushButton#wizardManualBtn {
    background: transparent;
    color: #52525b;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    font-size: 12px;
}
QPushButton#wizardManualBtn:hover {
    color: #a1a1aa;
    border-color: #52525b;
}
QPushButton#wizardSkipBtn {
    color: #3f3f46;
    font-size: 11px;
}
#wizardProgTitle {
    color: #e4e4e7;
    font-size: 15px;
    font-weight: 700;
}
QProgressBar#wizardProgBar {
    background: #27272a;
    border-radius: 4px;
}
QProgressBar#wizardProgBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #a78bfa);
    border-radius: 4px;
}
#wizardProgMsg {
    color: #52525b;
    font-size: 11px;
}
QPushButton#wizardCancelBtn {
    background: transparent;
    color: #52525b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 11px;
}
QPushButton#wizardCancelBtn:hover {
    color: #f87171;
    border-color: #7f1d1d;
}
#wizardDoneTitleSuccess {
    color: #4ade80;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneTitleError {
    color: #f87171;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneMsg {
    color: #71717a;
    font-size: 12px;
}
QPushButton#wizardManualLinkBtn {
    color: #52525b;
    font-size: 11px;
}

/* ── Popover de Tipografia do Leitor (botão "Aa") ──── */
QDialog#readerTypographyPopover {
    background-color: #1e2227;
    border: 1px solid #3f3f46;
    border-radius: 10px;
}
#readerTypographyPopover QLabel {
    color: #94a3b8;
    font-size: 12px;
    background: transparent;
}
#readerTypographyTitle {
    color: #e4e4e7;
    font-size: 13px;
    font-weight: 700;
}
#readerTypographyPopover QSpinBox,
#readerTypographyPopover QFontComboBox {
    background: #161920;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 3px 6px;
    color: #e4e4e7;
}
#readerTypographyPopover QSlider::groove:horizontal {
    height: 4px; background: #3f3f46; border-radius: 2px;
}
#readerTypographyPopover QSlider::handle:horizontal {
    background: #10b981; width: 14px; margin: -6px 0; border-radius: 7px;
}
QPushButton#readerThemeButton {
    background: #161920;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    color: #e4e4e7;
    font-size: 12px;
}
QPushButton#readerThemeButton:hover { background: #2d333f; }
QPushButton#readerThemeButton:checked {
    background: rgba(16,185,129,0.18);
    border-color: #10b981;
    color: #10b981;
}
QPushButton#readerTypographyClose {
    background: transparent; border: none; color: #94a3b8; font-size: 15px;
}
QPushButton#readerTypographyClose:hover { color: #10b981; }

/* ── Painel de Marcadores (aba do TOC) ─────────────── */
#readerSidePanelTabs::pane { border: none; background: #161920; }
#bookmarksPanel { background: #161920; }
#bookmarksHeader {
    color: #94a3b8; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; padding: 8px 8px 4px 8px;
}
#bookmarksEmpty { color: #64748b; font-size: 12px; padding: 12px; }
QListWidget#bookmarksList {
    background: #161920; border: none; color: #e5e7eb; font-size: 13px;
}
QListWidget#bookmarksList::item { padding: 0px; border-radius: 4px; }
QListWidget#bookmarksList::item:hover { background: #20242d; }
QPushButton#bookmarkGotoBtn {
    background: transparent; border: none; color: #e5e7eb;
    text-align: left; padding: 6px 8px; font-size: 12px;
}
QPushButton#bookmarkGotoBtn:hover { color: #10b981; }
QPushButton#bookmarkRemoveBtn {
    background: transparent; border: none; color: #94a3b8; font-size: 13px;
}
QPushButton#bookmarkRemoveBtn:hover { color: #ef4444; }

/* ── X-Ray da página (aba do painel lateral — Tarefa 3.2) ─────────── */
QLabel#xrayTitle {
    color: #10b981; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; padding: 4px 4px 2px 4px;
}
QLabel#xrayEmpty {
    color: #64748b; font-size: 12px; padding: 12px; line-height: 1.5;
}
QTreeWidget#xrayTree {
    background: #161920; border: none; color: #e5e7eb; font-size: 12px;
    outline: 0;
}
QTreeWidget#xrayTree::item { padding: 5px 4px; border-radius: 4px; }
QTreeWidget#xrayTree::item:hover { background: #20242d; color: #10b981; }
QTreeWidget#xrayTree::item:selected { background: rgba(16,185,129,0.15); color: #10b981; }

/* ── Prateleira "Continuar lendo" + card compacto (Onda 2) ───────── */
#continueShelf { background: transparent; }
#continueShelfTitle {
    color: #e5e7eb; font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
}
QScrollArea#continueShelfScroll { background: transparent; border: none; }
#continueCard {
    background-color: #161920; border: 1px solid #2d333f; border-radius: 10px;
}
#continueCard:hover { border-color: #10b981; }
#continueCardTitle { font-size: 12px; font-weight: 600; color: #e5e7eb; }
#continueCardMeta { font-size: 11px; color: #94a3b8; }
#continueCardCoverPlaceholder {
    border-radius: 6px; font-size: 34px; color: #a7f3d0;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #312e81, stop:1 #1e1b4b);
}
QProgressBar#continueProgress {
    background-color: #2d333f; border: none; border-radius: 3px;
}
QProgressBar#continueProgress::chunk {
    background-color: #10b981; border-radius: 3px;
}

/* ── Ordenação do header da biblioteca (Tarefa 2.3) ───────────────── */
QComboBox#librarySortCombo {
    background: #161920; border: 1px solid #2d333f; border-radius: 6px;
    padding: 4px 8px; color: #e4e4e7; font-size: 12px;
}
QComboBox#librarySortCombo:hover { border-color: #10b981; }
QComboBox#librarySortCombo QAbstractItemView {
    background: #161920; color: #e4e4e7; selection-background-color: #10b981;
    selection-color: #06281e;
}
QPushButton#librarySortOrderBtn {
    background: #161920; border: 1px solid #2d333f; border-radius: 6px;
    color: #e4e4e7; font-size: 13px;
}
QPushButton#librarySortOrderBtn:hover { border-color: #10b981; color: #10b981; }
QPushButton#librarySortOrderBtn:checked {
    background: #064e3b; border-color: #10b981; color: #10b981;
}

/* ── Estado "sem resultado" da busca/filtro (Tarefa 2.6) ──────────── */
#searchEmptyIcon { font-size: 64px; background: transparent; }
#searchEmptyText { color: #94a3b8; font-size: 18px; font-weight: 600; background: transparent; }
#searchEmptyHint { color: #64748b; font-size: 13px; background: transparent; }

/* ── Sobreposição de arraste-e-solte (Onda 2) ────────────────────── */
#dropOverlay {
    background-color: rgba(15, 17, 21, 0.82);
    border: 3px dashed #10b981;
}
#dropOverlayIcon { font-size: 56px; background: transparent; }
#dropOverlayLabel {
    color: #10b981; font-size: 24px; font-weight: 700; background: transparent;
}

/* ── Flashcards: gerar dos destaques (3.3) ─────────── */
QPushButton#flashcardsHighlightBtn {
    background: #1f2937;
    color: #e5e7eb;
    border: 1px solid #2d333f;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsHighlightBtn:hover {
    background: #263041;
    border-color: #10b981;
}
QPushButton#flashcardsHighlightBtn:disabled {
    background: #161920;
    color: #4b5563;
    border-color: #2d333f;
}

/* ── Banner "Retomar leitura" (3.7) ────────────────── */
QFrame#resumeBanner {
    background: #161920;
    border: 1px solid #10b981;
    border-radius: 8px;
}
#resumeBannerIcon { font-size: 15px; background: transparent; }
#resumeBannerText {
    color: #d1d5db;
    font-size: 12px;
    background: transparent;
}
QPushButton#resumeBannerClose {
    background: transparent;
    border: none;
    border-radius: 12px;
}
QPushButton#resumeBannerClose:hover {
    background: #2d333f;
}
/* Indicador proeminente de raciocínio/preparo do modelo (painel do Assistente) */
QLabel#ragThinkingIndicator {
    background-color: rgba(16, 185, 129, 0.10);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.35);
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 700;
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
#bookCard[selected="true"] {
    border: 2px solid #6366f1;
    border-radius: 12px;
    background-color: rgba(99, 102, 241, 0.12);
}
#bookCoverImage {
    border-radius: 8px;
    background-color: #e4e4e7;
}
#bookCoverPlaceholder {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e0e7ff, stop:1 #c7d2fe);
    font-size: 48px;
    color: #4f46e5;
}
#bookCoverBroken {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #fef3c7, stop:1 #fde68a);
    font-size: 48px;
    color: #f59e0b;
    border: 2px solid #f59e0b;
}
QProgressBar#bookCardProgress {
    background-color: #e4e4e7; border: none; border-radius: 2px;
}
QProgressBar#bookCardProgress::chunk {
    background-color: #059669; border-radius: 2px;
}
QMenu#bookCardContextMenu {
    background-color: #ffffff; border: 1px solid #e4e4e7;
    border-radius: 8px; padding: 4px;
}
QMenu#bookCardContextMenu::item {
    padding: 8px 24px; border-radius: 4px; color: #1A1A1A;
}
QMenu#bookCardContextMenu::item:selected { background-color: #059669; color: #ffffff; }
QMenu#bookCardContextMenu::separator { height: 1px; background: #e4e4e7; margin: 4px 8px; }
#bookCardBrokenBadge {
    color: #f59e0b;
    font-size: 8px;
    font-weight: 700;
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

/* ── Busca no conteúdo (Tarefa 5.1) ─────────────────── */
QCheckBox#contentToggle { color: #52525b; spacing: 6px; padding: 4px 6px; }
QCheckBox#contentToggle::indicator {
    width: 16px; height: 16px; border: 1px solid #d4d4d8;
    border-radius: 4px; background-color: #ffffff;
}
QCheckBox#contentToggle::indicator:checked {
    background-color: #059669; border-color: #059669;
}
#contentSearchResults { background-color: #f4f4f5; }
#contentSearchTitle { font-size: 16px; font-weight: 600; color: #1A1A1A; }
#contentSearchCount { color: #6b7280; font-size: 12px; }
QPushButton#contentSearchBack {
    background-color: #e4e4e7; color: #1A1A1A; border: 1px solid #d4d4d8;
    border-radius: 8px; padding: 6px 14px; font-weight: 600;
}
QPushButton#contentSearchBack:hover { background-color: #d4d4d8; }
#contentResultRow {
    background-color: #ffffff; border: 1px solid #e4e4e7; border-radius: 10px;
}
#contentResultRow:hover { border-color: #059669; background-color: #f0fdf4; }
#contentResultBook { color: #1A1A1A; font-weight: 600; font-size: 13px; }
#contentResultSnippet { color: #3f3f46; font-size: 12px; }
#contentSearchEmpty { color: #6b7280; font-size: 14px; padding: 40px; }
#contentSearchFooter { color: #6b7280; font-size: 12px; padding-top: 4px; }

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

/* ── Estatísticas vivas (Tarefa 5.2) ─────────────────── */
#statsSectionTitle {
    color: #1A1A1A;
    font-size: 13px;
    font-weight: 600;
}
#statsEmptyHint {
    color: #71717a;
    font-size: 12px;
    font-style: italic;
}
#statsGoalCaption {
    color: #555555;
    font-size: 12px;
}
#weeklyBarTrack {
    background-color: #e4e4e7;
    border-radius: 4px;
}
#weeklyBarFill {
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
        stop:0 #059669, stop:1 #34d399);
    border-radius: 4px;
}
#weeklyBarLabel {
    color: #71717a;
    font-size: 10px;
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

/* ── Painel de Detalhes do Livro ──────────────────── */
#bookDetailsCover {
    border-radius: 8px;
    background: #e4e4e7;
}
#bookDetailsCoverPlaceholder {
    border-radius: 8px;
    background: #e4e4e7;
    font-size: 64px;
}
#bookDetailsTitle {
    color: #1A1A1A;
}
#bookDetailsAuthor {
    color: #4f46e5;
    font-size: 13px;
}
#bookDetailsMeta {
    color: #555555;
    font-size: 12px;
    line-height: 1.5;
}
#bookDetailsMutedText {
    color: #555555;
    font-size: 12px;
}
#bookDetailsSectionHeader {
    color: #555555;
    font-size: 11px;
    font-weight: 600;
}
QScrollArea#bookDetailsScroll {
    border: none;
    background: transparent;
}
#bookDetailsScrollContent {
    background: transparent;
}
#bookDetailsActionBar {
    background: transparent;
    border-top: 1px solid #d4d4d8;
}
QPushButton#dangerBtn {
    background: transparent;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 10px;
    color: #dc2626;
}
QPushButton#dangerBtn:hover {
    background: rgba(239, 68, 68, 0.08);
    border-color: #dc2626;
}
QPushButton#bookDetailsRelatedBtn {
    background: transparent;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 6px;
    color: #4f46e5;
    font-size: 11px;
    text-align: left;
}
QPushButton#bookDetailsRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Diálogo de Coleções ───────────────────────────── */
#collectionDialogTitle {
    color: #1A1A1A;
}
#collectionDialogSubtitle {
    color: #555555;
    font-size: 12px;
}
#collectionCreateFrame {
    background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
}
#collectionNewNameInput {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 8px 12px;
    color: #1A1A1A;
    font-size: 13px;
}
#collectionNewNameInput:focus {
    border-color: #6366f1;
}
QPushButton#collectionCreateBtn {
    background: #6366f1;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: white;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#collectionCreateBtn:hover {
    background: #818cf8;
}
#collectionList {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    color: #1A1A1A;
    font-size: 13px;
}
#collectionList::item {
    padding: 10px 14px;
    border-bottom: 1px solid #e4e4e7;
}
#collectionList::item:selected {
    background: rgba(99, 102, 241, 0.12);
}
#collectionList::item:hover {
    background: #f4f4f5;
}
#addToCollectionList {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    color: #1A1A1A;
    font-size: 13px;
}
#addToCollectionList::item {
    padding: 8px 12px;
}
QPushButton#dangerBtnSmall {
    background: transparent;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    padding: 8px 16px;
    color: #dc2626;
    font-size: 12px;
}
QPushButton#dangerBtnSmall:hover {
    background: rgba(239, 68, 68, 0.08);
    border-color: #dc2626;
}

/* ── Diálogo de Importação ─────────────────────────── */
#importDialogTitle {
    color: #1A1A1A;
}
#importDialogSubtitle {
    color: #555555;
    font-size: 13px;
}
QGroupBox#importFilesGroup {
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
    color: #555555;
    font-size: 12px;
}
QGroupBox#importFilesGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
#importFileList {
    background: #ffffff;
    border: none;
    border-radius: 6px;
    color: #1A1A1A;
    font-size: 12px;
}
#importFileList::item {
    padding: 6px 10px;
    border-bottom: 1px solid #e4e4e7;
}
#importFileList::item:selected {
    background: rgba(99, 102, 241, 0.12);
}
#importFilesCount {
    color: #8a8a8a;
    font-size: 11px;
}
#importOptionCheckbox {
    color: #555555;
    font-size: 12px;
}
#importProgressLabel {
    color: #555555;
    font-size: 12px;
}
#importLog {
    background: #f4f4f5;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 8px;
    color: #555555;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}

/* ── Diálogo de Exportação Anki ────────────────────── */
#ankiDeckLabel {
    font-weight: bold;
}
#ankiFrontLabel {
    font-weight: bold;
    color: #059669;
}
#ankiBackLabel {
    font-weight: bold;
    color: #2563eb;
}
#ankiStatusChecking {
    color: #555555;
    font-size: 11px;
}
#ankiStatusConnected {
    color: #059669;
    font-size: 11px;
}
#ankiStatusOffline {
    color: #d97706;
    font-size: 11px;
}
QPushButton#ankiSaveBtn {
    background-color: #10b981;
    color: white;
    font-weight: bold;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}
QPushButton#ankiSaveBtn:hover {
    background-color: #059669;
}
QPushButton#ankiSaveBtn:disabled {
    background-color: #94a3b8;
}

/* ── Diálogo do Dossiê do Livro ─────────────────────── */
QDialog#bookDossierDialog {
    background-color: #ffffff;
}
QScrollArea#dossierScroll {
    border: none;
    background: transparent;
}
#dossierContent {
    background: transparent;
}
#dossierSectionHeader {
    color: #555555;
    font-size: 11px;
    font-weight: 600;
}
#dossierBody {
    color: #333333;
    font-size: 12px;
}
QFrame#dossierCard {
    background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
}
#dossierCover {
    background: #e4e4e7;
    border-radius: 6px;
    font-size: 28px;
}
#dossierBookTitle {
    color: #1A1A1A;
    font-size: 16px;
    font-weight: 700;
}
#dossierBookAuthor {
    color: #4f46e5;
    font-size: 12px;
}
#dossierProgress {
    color: #555555;
    font-size: 11px;
}
QPushButton#dossierRelatedBtn {
    background: transparent;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 8px;
    color: #4f46e5;
    font-size: 12px;
    text-align: left;
}
QPushButton#dossierRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Gerenciador de Tags ───────────────────────────── */
#tagManagerHeader {
    color: #555555;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#tagAddBtn {
    background: rgba(99, 102, 241, 0.12);
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
    color: #4f46e5;
    font-size: 11px;
    font-weight: 600;
}
#tagManagerEmptyLabel {
    color: #8a8a8a;
    font-size: 11px;
}
#addTagDialogTitle {
    color: #1A1A1A;
}
#addTagList {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    color: #1A1A1A;
    font-size: 12px;
}
#addTagNameInput {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1A1A1A;
    font-size: 12px;
}

/* ── Diálogo de Configurações ──────────────────────── */
#settingsDialogTitle {
    color: #1A1A1A;
}
QGroupBox#settingsGroup {
    border: 1px solid #e4e4e7;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    padding-top: 24px;
    color: #555555;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox#settingsGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QGroupBox#settingsGroup QLabel {
    color: #555555;
    font-size: 12px;
}
QGroupBox#settingsGroup QCheckBox {
    color: #555555;
    font-size: 12px;
}
#settingsNumericInput {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 4px 8px;
    color: #1A1A1A;
}
#settingsWatchList {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    color: #1A1A1A;
    font-size: 12px;
}
#settingsAdvancedWarning {
    color: #d97706;
    font-size: 11px;
    font-style: italic;
}

/* ── Diálogo de Atalhos de Teclado ──────────────────── */
QGroupBox#settingsGroup QLabel#shortcutKeyBadge {
    background: #f4f4f5;
    border: 1px solid #d4d4d8;
    border-radius: 4px;
    padding: 2px 8px;
    color: #1A1A1A;
    font-family: 'Consolas', 'Courier New', monospace;
    font-weight: 600;
    font-size: 11px;
}

/* ── Diálogo de Flashcards ─────────────────────────── */
QFrame#flashcardItem {
    background-color: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 8px;
}
#flashcardBadgeNew {
    color: #059669;
    font-size: 10px;
    font-weight: 600;
}
#flashcardBadgeDue {
    color: #555555;
    font-size: 10px;
}
#flashcardOrigin {
    color: #4f46e5;
    font-size: 10px;
}
QPushButton#flashcardDeleteBtn {
    background: transparent;
    border: none;
    color: #8a8a8a;
    font-size: 12px;
}
QPushButton#flashcardDeleteBtn:hover {
    color: #dc2626;
}
#flashcardFront {
    color: #1A1A1A;
    font-size: 13px;
    font-weight: 600;
}
#flashcardBack {
    color: #333333;
    font-size: 12px;
}
QDialog#flashcardsDialog {
    background-color: #ffffff;
}
#flashcardsTitle {
    color: #1A1A1A;
    font-size: 16px;
    font-weight: 700;
}
QComboBox#flashcardsBookFilter {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 5px 8px;
    color: #1A1A1A;
    font-size: 12px;
}
QComboBox#flashcardsBookFilter QAbstractItemView {
    background: #ffffff;
    color: #1A1A1A;
    selection-background-color: #e4e4e7;
}
QPushButton#flashcardsStudyBtn {
    background: #10b981;
    color: #06281e;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsStudyBtn:hover {
    background: #34d399;
}
QPushButton#flashcardsStudyBtn:disabled {
    background: #d4d4d8;
    color: #8a8a8a;
}
#flashcardsEmptyLabel {
    color: #555555;
    font-size: 13px;
}
#flashcardsCountLabel {
    color: #8a8a8a;
    font-size: 11px;
}
#flashcardsProgressLabel {
    color: #555555;
    font-size: 12px;
}
QFrame#flashcardsStudyCard {
    background: #f4f4f5;
    border: 1px solid #e4e4e7;
    border-radius: 10px;
}
#flashcardsStudyFront {
    color: #1A1A1A;
    font-size: 15px;
    font-weight: 600;
}
QFrame#flashcardsStudySep {
    background: #e4e4e7;
}
#flashcardsStudyBack {
    color: #333333;
    font-size: 14px;
}
QPushButton#flashcardsRevealBtn {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#flashcardsRevealBtn:hover {
    background: #1d4ed8;
}
QPushButton#flashcardsGradeAgain {
    background: transparent;
    color: #ef4444;
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeAgain:hover {
    background: #ef4444;
    color: #0f1115;
}
QPushButton#flashcardsGradeHard {
    background: transparent;
    color: #f59e0b;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeHard:hover {
    background: #f59e0b;
    color: #0f1115;
}
QPushButton#flashcardsGradeGood {
    background: transparent;
    color: #10b981;
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeGood:hover {
    background: #10b981;
    color: #0f1115;
}
QPushButton#flashcardsGradeEasy {
    background: transparent;
    color: #3b82f6;
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeEasy:hover {
    background: #3b82f6;
    color: #0f1115;
}
QPushButton#flashcardsBackBtn {
    background: transparent;
    color: #555555;
    border: none;
    font-size: 12px;
}
QPushButton#flashcardsBackBtn:hover {
    color: #1A1A1A;
}

/* ── Wizard de Instalação do Ollama ────────────────── */
QDialog#wizardDialog {
    background-color: #ffffff;
}
#wizardHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #eef0ff, stop:1 #e0e4fb);
    border-bottom: 1px solid #e4e4e7;
}
#wizardHeaderTitle {
    color: #1A1A1A;
    font-size: 14px;
    font-weight: 700;
}
#wizardHeaderSub {
    color: #f59e0b;
    font-size: 11px;
}
#wizardPage {
    background-color: #ffffff;
}
#wizardDesc {
    color: #555555;
    font-size: 13px;
    line-height: 1.6;
}
QFrame#wizardInfoBox {
    background: #eef0ff;
    border: 1px solid #c7d2fe;
    border-radius: 8px;
    padding: 4px;
}
#wizardInfoItem {
    color: #4f46e5;
    font-size: 12px;
}
QPushButton#wizardInstallBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #818cf8);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#wizardInstallBtn:hover {
    background: #818cf8;
}
QPushButton#wizardManualBtn {
    background: transparent;
    color: #8a8a8a;
    border: 1px solid #d4d4d8;
    border-radius: 8px;
    font-size: 12px;
}
QPushButton#wizardManualBtn:hover {
    color: #555555;
    border-color: #8a8a8a;
}
QPushButton#wizardSkipBtn {
    color: #9ca3af;
    font-size: 11px;
}
#wizardProgTitle {
    color: #1A1A1A;
    font-size: 15px;
    font-weight: 700;
}
QProgressBar#wizardProgBar {
    background: #e4e4e7;
    border-radius: 4px;
}
QProgressBar#wizardProgBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #a78bfa);
    border-radius: 4px;
}
#wizardProgMsg {
    color: #8a8a8a;
    font-size: 11px;
}
QPushButton#wizardCancelBtn {
    background: transparent;
    color: #8a8a8a;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 11px;
}
QPushButton#wizardCancelBtn:hover {
    color: #dc2626;
    border-color: #dc2626;
}
#wizardDoneTitleSuccess {
    color: #059669;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneTitleError {
    color: #dc2626;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneMsg {
    color: #555555;
    font-size: 12px;
}
QPushButton#wizardManualLinkBtn {
    color: #8a8a8a;
    font-size: 11px;
}

/* ── Popover de Tipografia do Leitor (botão "Aa") ──── */
QDialog#readerTypographyPopover {
    background-color: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 10px;
}
#readerTypographyPopover QLabel {
    color: #71717a;
    font-size: 12px;
    background: transparent;
}
#readerTypographyTitle {
    color: #1a1a1a;
    font-size: 13px;
    font-weight: 700;
}
#readerTypographyPopover QSpinBox,
#readerTypographyPopover QFontComboBox {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 3px 6px;
    color: #1a1a1a;
}
#readerTypographyPopover QSlider::groove:horizontal {
    height: 4px; background: #d4d4d8; border-radius: 2px;
}
#readerTypographyPopover QSlider::handle:horizontal {
    background: #059669; width: 14px; margin: -6px 0; border-radius: 7px;
}
QPushButton#readerThemeButton {
    background: #ffffff;
    border: 1px solid #d4d4d8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #1a1a1a;
    font-size: 12px;
}
QPushButton#readerThemeButton:hover { background: #f4f4f5; }
QPushButton#readerThemeButton:checked {
    background: rgba(5,150,105,0.12);
    border-color: #059669;
    color: #059669;
}
QPushButton#readerTypographyClose {
    background: transparent; border: none; color: #71717a; font-size: 15px;
}
QPushButton#readerTypographyClose:hover { color: #059669; }

/* ── Painel de Marcadores (aba do TOC) ─────────────── */
#readerSidePanelTabs::pane { border: none; background: #f4f4f5; }
#bookmarksPanel { background: #f4f4f5; }
#bookmarksHeader {
    color: #71717a; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; padding: 8px 8px 4px 8px;
}
#bookmarksEmpty { color: #8a8a8a; font-size: 12px; padding: 12px; }
QListWidget#bookmarksList {
    background: #f4f4f5; border: none; color: #1A1A1A; font-size: 13px;
}
QListWidget#bookmarksList::item { padding: 0px; border-radius: 4px; }
QListWidget#bookmarksList::item:hover { background: #e4e4e7; }
QPushButton#bookmarkGotoBtn {
    background: transparent; border: none; color: #1A1A1A;
    text-align: left; padding: 6px 8px; font-size: 12px;
}
QPushButton#bookmarkGotoBtn:hover { color: #059669; }
QPushButton#bookmarkRemoveBtn {
    background: transparent; border: none; color: #71717a; font-size: 13px;
}
QPushButton#bookmarkRemoveBtn:hover { color: #dc2626; }

/* ── X-Ray da página (aba do painel lateral — Tarefa 3.2) ─────────── */
QLabel#xrayTitle {
    color: #059669; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; padding: 4px 4px 2px 4px;
}
QLabel#xrayEmpty {
    color: #8a8a8a; font-size: 12px; padding: 12px; line-height: 1.5;
}
QTreeWidget#xrayTree {
    background: #f4f4f5; border: none; color: #1A1A1A; font-size: 12px;
    outline: 0;
}
QTreeWidget#xrayTree::item { padding: 5px 4px; border-radius: 4px; }
QTreeWidget#xrayTree::item:hover { background: #e4e4e7; color: #059669; }
QTreeWidget#xrayTree::item:selected { background: rgba(5,150,105,0.15); color: #059669; }

/* ── Prateleira "Continuar lendo" + card compacto (Onda 2) ───────── */
#continueShelf { background: transparent; }
#continueShelfTitle {
    color: #1A1A1A; font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
}
QScrollArea#continueShelfScroll { background: transparent; border: none; }
#continueCard {
    background-color: #ffffff; border: 1px solid #e4e4e7; border-radius: 10px;
}
#continueCard:hover { border-color: #059669; }
#continueCardTitle { font-size: 12px; font-weight: 600; color: #1A1A1A; }
#continueCardMeta { font-size: 11px; color: #71717a; }
#continueCardCoverPlaceholder {
    border-radius: 6px; font-size: 34px; color: #4338ca;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e0e7ff, stop:1 #c7d2fe);
}
QProgressBar#continueProgress {
    background-color: #e4e4e7; border: none; border-radius: 3px;
}
QProgressBar#continueProgress::chunk {
    background-color: #059669; border-radius: 3px;
}

/* ── Ordenação do header da biblioteca (Tarefa 2.3) ───────────────── */
QComboBox#librarySortCombo {
    background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px;
    padding: 4px 8px; color: #1A1A1A; font-size: 12px;
}
QComboBox#librarySortCombo:hover { border-color: #059669; }
QComboBox#librarySortCombo QAbstractItemView {
    background: #ffffff; color: #1A1A1A; selection-background-color: #059669;
    selection-color: #ffffff;
}
QPushButton#librarySortOrderBtn {
    background: #ffffff; border: 1px solid #e4e4e7; border-radius: 6px;
    color: #1A1A1A; font-size: 13px;
}
QPushButton#librarySortOrderBtn:hover { border-color: #059669; color: #059669; }
QPushButton#librarySortOrderBtn:checked {
    background: #d1fae5; border-color: #059669; color: #059669;
}

/* ── Estado "sem resultado" da busca/filtro (Tarefa 2.6) ──────────── */
#searchEmptyIcon { font-size: 64px; background: transparent; }
#searchEmptyText { color: #71717a; font-size: 18px; font-weight: 600; background: transparent; }
#searchEmptyHint { color: #a1a1aa; font-size: 13px; background: transparent; }

/* ── Sobreposição de arraste-e-solte (Onda 2) ────────────────────── */
#dropOverlay {
    background-color: rgba(244, 244, 245, 0.86);
    border: 3px dashed #059669;
}
#dropOverlayIcon { font-size: 56px; background: transparent; }
#dropOverlayLabel {
    color: #059669; font-size: 24px; font-weight: 700; background: transparent;
}

/* ── Flashcards: gerar dos destaques (3.3) ─────────── */
QPushButton#flashcardsHighlightBtn {
    background: #f3f4f6;
    color: #374151;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsHighlightBtn:hover {
    background: #e5e7eb;
    border-color: #059669;
}
QPushButton#flashcardsHighlightBtn:disabled {
    background: #f9fafb;
    color: #9ca3af;
    border-color: #e5e7eb;
}

/* ── Banner "Retomar leitura" (3.7) ────────────────── */
QFrame#resumeBanner {
    background: #ffffff;
    border: 1px solid #059669;
    border-radius: 8px;
}
#resumeBannerIcon { font-size: 15px; background: transparent; }
#resumeBannerText {
    color: #374151;
    font-size: 12px;
    background: transparent;
}
QPushButton#resumeBannerClose {
    background: transparent;
    border: none;
    border-radius: 12px;
}
QPushButton#resumeBannerClose:hover {
    background: #e5e7eb;
}
/* Indicador proeminente de raciocínio/preparo do modelo (painel do Assistente) */
QLabel#ragThinkingIndicator {
    background-color: #f0fdf4;
    color: #166534;
    border: 1px solid #bbf7d0;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 700;
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
#bookCard[selected="true"] {
    border: 2px solid #6366f1;
    border-radius: 12px;
    background-color: rgba(99, 102, 241, 0.12);
}
#bookCoverImage {
    border-radius: 8px;
    background-color: #dfd8c8;
}
#bookCoverPlaceholder {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #ded6c4, stop:1 #c3b8d9);
    font-size: 48px;
    color: #4c3f8f;
}
#bookCoverBroken {
    border-radius: 8px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f5e6c8, stop:1 #e8d1a0);
    font-size: 48px;
    color: #d97706;
    border: 2px solid #d97706;
}
QProgressBar#bookCardProgress {
    background-color: #d4cbb8; border: none; border-radius: 2px;
}
QProgressBar#bookCardProgress::chunk {
    background-color: #8b6c42; border-radius: 2px;
}
QMenu#bookCardContextMenu {
    background-color: #EADFCA; border: 1px solid #d4cbb8;
    border-radius: 8px; padding: 4px;
}
QMenu#bookCardContextMenu::item {
    padding: 8px 24px; border-radius: 4px; color: #433422;
}
QMenu#bookCardContextMenu::item:selected { background-color: #8b6c42; color: #F4ECD8; }
QMenu#bookCardContextMenu::separator { height: 1px; background: #d4cbb8; margin: 4px 8px; }
#bookCardBrokenBadge {
    color: #d97706;
    font-size: 8px;
    font-weight: 700;
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

/* ── Busca no conteúdo (Tarefa 5.1) ─────────────────── */
QCheckBox#contentToggle { color: #5c4b33; spacing: 6px; padding: 4px 6px; }
QCheckBox#contentToggle::indicator {
    width: 16px; height: 16px; border: 1px solid #d4cbb8;
    border-radius: 4px; background-color: #EADFCA;
}
QCheckBox#contentToggle::indicator:checked {
    background-color: #059669; border-color: #059669;
}
#contentSearchResults { background-color: #F4ECD8; }
#contentSearchTitle { font-size: 16px; font-weight: 600; color: #433422; }
#contentSearchCount { color: #6b5d49; font-size: 12px; }
QPushButton#contentSearchBack {
    background-color: #EADFCA; color: #433422; border: 1px solid #d4cbb8;
    border-radius: 8px; padding: 6px 14px; font-weight: 600;
}
QPushButton#contentSearchBack:hover { background-color: #e0d4bb; }
#contentResultRow {
    background-color: #EADFCA; border: 1px solid #d4cbb8; border-radius: 10px;
}
#contentResultRow:hover { border-color: #059669; background-color: #efe6d0; }
#contentResultBook { color: #433422; font-weight: 600; font-size: 13px; }
#contentResultSnippet { color: #5c4b33; font-size: 12px; }
#contentSearchEmpty { color: #6b5d49; font-size: 14px; padding: 40px; }
#contentSearchFooter { color: #6b5d49; font-size: 12px; padding-top: 4px; }

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

/* ── Estatísticas vivas (Tarefa 5.2) ─────────────────── */
#statsSectionTitle {
    color: #433422;
    font-size: 13px;
    font-weight: 600;
}
#statsEmptyHint {
    color: #705E4B;
    font-size: 12px;
    font-style: italic;
}
#statsGoalCaption {
    color: #705E4B;
    font-size: 12px;
}
#weeklyBarTrack {
    background-color: #d4cbb8;
    border-radius: 4px;
}
#weeklyBarFill {
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
        stop:0 #059669, stop:1 #34d399);
    border-radius: 4px;
}
#weeklyBarLabel {
    color: #705E4B;
    font-size: 10px;
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

/* ── Painel de Detalhes do Livro ──────────────────── */
#bookDetailsCover {
    border-radius: 8px;
    background: #dfd8c8;
}
#bookDetailsCoverPlaceholder {
    border-radius: 8px;
    background: #dfd8c8;
    font-size: 64px;
}
#bookDetailsTitle {
    color: #433422;
}
#bookDetailsAuthor {
    color: #4c3f8f;
    font-size: 13px;
}
#bookDetailsMeta {
    color: #705E4B;
    font-size: 12px;
    line-height: 1.5;
}
#bookDetailsMutedText {
    color: #705E4B;
    font-size: 12px;
}
#bookDetailsSectionHeader {
    color: #705E4B;
    font-size: 11px;
    font-weight: 600;
}
QScrollArea#bookDetailsScroll {
    border: none;
    background: transparent;
}
#bookDetailsScrollContent {
    background: transparent;
}
#bookDetailsActionBar {
    background: transparent;
    border-top: 1px solid #d4cbb8;
}
QPushButton#dangerBtn {
    background: transparent;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 10px;
    color: #b91c1c;
}
QPushButton#dangerBtn:hover {
    background: rgba(239, 68, 68, 0.08);
    border-color: #b91c1c;
}
QPushButton#bookDetailsRelatedBtn {
    background: transparent;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 6px;
    color: #4c3f8f;
    font-size: 11px;
    text-align: left;
}
QPushButton#bookDetailsRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Diálogo de Coleções ───────────────────────────── */
#collectionDialogTitle {
    color: #433422;
}
#collectionDialogSubtitle {
    color: #705E4B;
    font-size: 12px;
}
#collectionCreateFrame {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
}
#collectionNewNameInput {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 8px 12px;
    color: #433422;
    font-size: 13px;
}
#collectionNewNameInput:focus {
    border-color: #6366f1;
}
QPushButton#collectionCreateBtn {
    background: #6366f1;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: white;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#collectionCreateBtn:hover {
    background: #818cf8;
}
#collectionList {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    color: #433422;
    font-size: 13px;
}
#collectionList::item {
    padding: 10px 14px;
    border-bottom: 1px solid #d4cbb8;
}
#collectionList::item:selected {
    background: rgba(99, 102, 241, 0.15);
}
#collectionList::item:hover {
    background: #dfd8c8;
}
#addToCollectionList {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    color: #433422;
    font-size: 13px;
}
#addToCollectionList::item {
    padding: 8px 12px;
}
QPushButton#dangerBtnSmall {
    background: transparent;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 8px 16px;
    color: #b91c1c;
    font-size: 12px;
}
QPushButton#dangerBtnSmall:hover {
    background: rgba(239, 68, 68, 0.08);
    border-color: #b91c1c;
}

/* ── Diálogo de Importação ─────────────────────────── */
#importDialogTitle {
    color: #433422;
}
#importDialogSubtitle {
    color: #705E4B;
    font-size: 13px;
}
QGroupBox#importFilesGroup {
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 20px;
    color: #705E4B;
    font-size: 12px;
}
QGroupBox#importFilesGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
#importFileList {
    background: #F4ECD8;
    border: none;
    border-radius: 6px;
    color: #433422;
    font-size: 12px;
}
#importFileList::item {
    padding: 6px 10px;
    border-bottom: 1px solid #d4cbb8;
}
#importFileList::item:selected {
    background: rgba(99, 102, 241, 0.15);
}
#importFilesCount {
    color: #9c8a6f;
    font-size: 11px;
}
#importOptionCheckbox {
    color: #705E4B;
    font-size: 12px;
}
#importProgressLabel {
    color: #705E4B;
    font-size: 12px;
}
#importLog {
    background: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 8px;
    color: #705E4B;
    font-family: 'Consolas', monospace;
    font-size: 11px;
}

/* ── Diálogo de Exportação Anki ────────────────────── */
#ankiDeckLabel {
    font-weight: bold;
}
#ankiFrontLabel {
    font-weight: bold;
    color: #059669;
}
#ankiBackLabel {
    font-weight: bold;
    color: #2563eb;
}
#ankiStatusChecking {
    color: #705E4B;
    font-size: 11px;
}
#ankiStatusConnected {
    color: #059669;
    font-size: 11px;
}
#ankiStatusOffline {
    color: #d97706;
    font-size: 11px;
}
QPushButton#ankiSaveBtn {
    background-color: #10b981;
    color: white;
    font-weight: bold;
    padding: 6px 12px;
    border-radius: 4px;
    border: none;
}
QPushButton#ankiSaveBtn:hover {
    background-color: #059669;
}
QPushButton#ankiSaveBtn:disabled {
    background-color: #94a3b8;
}

/* ── Diálogo do Dossiê do Livro ─────────────────────── */
QDialog#bookDossierDialog {
    background-color: #F4ECD8;
}
QScrollArea#dossierScroll {
    border: none;
    background: transparent;
}
#dossierContent {
    background: transparent;
}
#dossierSectionHeader {
    color: #705E4B;
    font-size: 11px;
    font-weight: 600;
}
#dossierBody {
    color: #4a3d2a;
    font-size: 12px;
}
QFrame#dossierCard {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
}
#dossierCover {
    background: #dfd8c8;
    border-radius: 6px;
    font-size: 28px;
}
#dossierBookTitle {
    color: #433422;
    font-size: 16px;
    font-weight: 700;
}
#dossierBookAuthor {
    color: #4c3f8f;
    font-size: 12px;
}
#dossierProgress {
    color: #705E4B;
    font-size: 11px;
}
QPushButton#dossierRelatedBtn {
    background: transparent;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 8px;
    color: #4c3f8f;
    font-size: 12px;
    text-align: left;
}
QPushButton#dossierRelatedBtn:hover {
    border-color: #6366f1;
}

/* ── Gerenciador de Tags ───────────────────────────── */
#tagManagerHeader {
    color: #705E4B;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#tagAddBtn {
    background: rgba(99, 102, 241, 0.12);
    border: none;
    border-radius: 4px;
    padding: 3px 10px;
    color: #4c3f8f;
    font-size: 11px;
    font-weight: 600;
}
#tagManagerEmptyLabel {
    color: #9c8a6f;
    font-size: 11px;
}
#addTagDialogTitle {
    color: #433422;
}
#addTagList {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    color: #433422;
    font-size: 12px;
}
#addTagNameInput {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #433422;
    font-size: 12px;
}

/* ── Diálogo de Configurações ──────────────────────── */
#settingsDialogTitle {
    color: #433422;
}
QGroupBox#settingsGroup {
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px;
    padding-top: 24px;
    color: #705E4B;
    font-size: 12px;
    font-weight: 600;
}
QGroupBox#settingsGroup::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QGroupBox#settingsGroup QLabel {
    color: #705E4B;
    font-size: 12px;
}
QGroupBox#settingsGroup QCheckBox {
    color: #705E4B;
    font-size: 12px;
}
#settingsNumericInput {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 4px 8px;
    color: #433422;
}
#settingsWatchList {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    color: #433422;
    font-size: 12px;
}
#settingsAdvancedWarning {
    color: #d97706;
    font-size: 11px;
    font-style: italic;
}

/* ── Diálogo de Atalhos de Teclado ──────────────────── */
QGroupBox#settingsGroup QLabel#shortcutKeyBadge {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 4px;
    padding: 2px 8px;
    color: #433422;
    font-family: 'Consolas', 'Courier New', monospace;
    font-weight: 600;
    font-size: 11px;
}

/* ── Diálogo de Flashcards ─────────────────────────── */
QFrame#flashcardItem {
    background-color: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
}
#flashcardBadgeNew {
    color: #059669;
    font-size: 10px;
    font-weight: 600;
}
#flashcardBadgeDue {
    color: #705E4B;
    font-size: 10px;
}
#flashcardOrigin {
    color: #4c3f8f;
    font-size: 10px;
}
QPushButton#flashcardDeleteBtn {
    background: transparent;
    border: none;
    color: #9c8a6f;
    font-size: 12px;
}
QPushButton#flashcardDeleteBtn:hover {
    color: #b91c1c;
}
#flashcardFront {
    color: #433422;
    font-size: 13px;
    font-weight: 600;
}
#flashcardBack {
    color: #4a3d2a;
    font-size: 12px;
}
QDialog#flashcardsDialog {
    background-color: #F4ECD8;
}
#flashcardsTitle {
    color: #433422;
    font-size: 16px;
    font-weight: 700;
}
QComboBox#flashcardsBookFilter {
    background: #F4ECD8;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 5px 8px;
    color: #433422;
    font-size: 12px;
}
QComboBox#flashcardsBookFilter QAbstractItemView {
    background: #F4ECD8;
    color: #433422;
    selection-background-color: #d4cbb8;
}
QPushButton#flashcardsStudyBtn {
    background: #10b981;
    color: #06281e;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsStudyBtn:hover {
    background: #34d399;
}
QPushButton#flashcardsStudyBtn:disabled {
    background: #d4cbb8;
    color: #9c8a6f;
}
#flashcardsEmptyLabel {
    color: #705E4B;
    font-size: 13px;
}
#flashcardsCountLabel {
    color: #9c8a6f;
    font-size: 11px;
}
#flashcardsProgressLabel {
    color: #705E4B;
    font-size: 12px;
}
QFrame#flashcardsStudyCard {
    background: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 10px;
}
#flashcardsStudyFront {
    color: #433422;
    font-size: 15px;
    font-weight: 600;
}
QFrame#flashcardsStudySep {
    background: #d4cbb8;
}
#flashcardsStudyBack {
    color: #4a3d2a;
    font-size: 14px;
}
QPushButton#flashcardsRevealBtn {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#flashcardsRevealBtn:hover {
    background: #1d4ed8;
}
QPushButton#flashcardsGradeAgain {
    background: transparent;
    color: #ef4444;
    border: 1px solid #ef4444;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeAgain:hover {
    background: #ef4444;
    color: #0f1115;
}
QPushButton#flashcardsGradeHard {
    background: transparent;
    color: #d97706;
    border: 1px solid #d97706;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeHard:hover {
    background: #d97706;
    color: #0f1115;
}
QPushButton#flashcardsGradeGood {
    background: transparent;
    color: #10b981;
    border: 1px solid #10b981;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeGood:hover {
    background: #10b981;
    color: #0f1115;
}
QPushButton#flashcardsGradeEasy {
    background: transparent;
    color: #3b82f6;
    border: 1px solid #3b82f6;
    border-radius: 8px;
    padding: 8px 6px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsGradeEasy:hover {
    background: #3b82f6;
    color: #0f1115;
}
QPushButton#flashcardsBackBtn {
    background: transparent;
    color: #705E4B;
    border: none;
    font-size: 12px;
}
QPushButton#flashcardsBackBtn:hover {
    color: #433422;
}

/* ── Wizard de Instalação do Ollama ────────────────── */
QDialog#wizardDialog {
    background-color: #F4ECD8;
}
#wizardHeader {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #f6ecd9, stop:1 #efe3c8);
    border-bottom: 1px solid #d4cbb8;
}
#wizardHeaderTitle {
    color: #433422;
    font-size: 14px;
    font-weight: 700;
}
#wizardHeaderSub {
    color: #d97706;
    font-size: 11px;
}
#wizardPage {
    background-color: #F4ECD8;
}
#wizardDesc {
    color: #705E4B;
    font-size: 13px;
    line-height: 1.6;
}
QFrame#wizardInfoBox {
    background: #EADFCA;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 4px;
}
#wizardInfoItem {
    color: #4c3f8f;
    font-size: 12px;
}
QPushButton#wizardInstallBtn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #818cf8);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 700;
}
QPushButton#wizardInstallBtn:hover {
    background: #818cf8;
}
QPushButton#wizardManualBtn {
    background: transparent;
    color: #9c8a6f;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    font-size: 12px;
}
QPushButton#wizardManualBtn:hover {
    color: #705E4B;
    border-color: #9c8a6f;
}
QPushButton#wizardSkipBtn {
    color: #b3a58c;
    font-size: 11px;
}
#wizardProgTitle {
    color: #433422;
    font-size: 15px;
    font-weight: 700;
}
QProgressBar#wizardProgBar {
    background: #d4cbb8;
    border-radius: 4px;
}
QProgressBar#wizardProgBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #6366f1, stop:1 #a78bfa);
    border-radius: 4px;
}
#wizardProgMsg {
    color: #9c8a6f;
    font-size: 11px;
}
QPushButton#wizardCancelBtn {
    background: transparent;
    color: #9c8a6f;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 6px 20px;
    font-size: 11px;
}
QPushButton#wizardCancelBtn:hover {
    color: #b91c1c;
    border-color: #b91c1c;
}
#wizardDoneTitleSuccess {
    color: #059669;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneTitleError {
    color: #b91c1c;
    font-size: 16px;
    font-weight: 700;
}
#wizardDoneMsg {
    color: #705E4B;
    font-size: 12px;
}
QPushButton#wizardManualLinkBtn {
    color: #9c8a6f;
    font-size: 11px;
}

/* ── Popover de Tipografia do Leitor (botão "Aa") ──── */
QDialog#readerTypographyPopover {
    background-color: #f4ecd8;
    border: 1px solid #d4cbb8;
    border-radius: 10px;
}
#readerTypographyPopover QLabel {
    color: #8b7355;
    font-size: 12px;
    background: transparent;
}
#readerTypographyTitle {
    color: #433422;
    font-size: 13px;
    font-weight: 700;
}
#readerTypographyPopover QSpinBox,
#readerTypographyPopover QFontComboBox {
    background: #ebe5d9;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 3px 6px;
    color: #433422;
}
#readerTypographyPopover QSlider::groove:horizontal {
    height: 4px; background: #d4cbb8; border-radius: 2px;
}
#readerTypographyPopover QSlider::handle:horizontal {
    background: #8b6c42; width: 14px; margin: -6px 0; border-radius: 7px;
}
QPushButton#readerThemeButton {
    background: #ebe5d9;
    border: 1px solid #d4cbb8;
    border-radius: 6px;
    padding: 6px 10px;
    color: #433422;
    font-size: 12px;
}
QPushButton#readerThemeButton:hover { background: #dfd8c8; }
QPushButton#readerThemeButton:checked {
    background: rgba(139,108,66,0.18);
    border-color: #8b6c42;
    color: #8b6c42;
}
QPushButton#readerTypographyClose {
    background: transparent; border: none; color: #8b7355; font-size: 15px;
}
QPushButton#readerTypographyClose:hover { color: #8b6c42; }

/* ── Painel de Marcadores (aba do TOC) ─────────────── */
#readerSidePanelTabs::pane { border: none; background: #ebe5d9; }
#bookmarksPanel { background: #ebe5d9; }
#bookmarksHeader {
    color: #8b7355; font-size: 11px; font-weight: 700;
    letter-spacing: 1px; padding: 8px 8px 4px 8px;
}
#bookmarksEmpty { color: #9c8a6f; font-size: 12px; padding: 12px; }
QListWidget#bookmarksList {
    background: #ebe5d9; border: none; color: #5B4636; font-size: 13px;
}
QListWidget#bookmarksList::item { padding: 0px; border-radius: 4px; }
QListWidget#bookmarksList::item:hover { background: #dfd8c8; }
QPushButton#bookmarkGotoBtn {
    background: transparent; border: none; color: #5B4636;
    text-align: left; padding: 6px 8px; font-size: 12px;
}
QPushButton#bookmarkGotoBtn:hover { color: #8b6c42; }
QPushButton#bookmarkRemoveBtn {
    background: transparent; border: none; color: #8b7355; font-size: 13px;
}
QPushButton#bookmarkRemoveBtn:hover { color: #b91c1c; }

/* ── X-Ray da página (aba do painel lateral — Tarefa 3.2) ─────────── */
QLabel#xrayTitle {
    color: #8b6c42; font-size: 12px; font-weight: 700;
    letter-spacing: 0.5px; padding: 4px 4px 2px 4px;
}
QLabel#xrayEmpty {
    color: #9c8a6f; font-size: 12px; padding: 12px; line-height: 1.5;
}
QTreeWidget#xrayTree {
    background: #ebe5d9; border: none; color: #5B4636; font-size: 12px;
    outline: 0;
}
QTreeWidget#xrayTree::item { padding: 5px 4px; border-radius: 4px; }
QTreeWidget#xrayTree::item:hover { background: #dfd8c8; color: #8b6c42; }
QTreeWidget#xrayTree::item:selected { background: rgba(139,108,66,0.15); color: #8b6c42; }

/* ── Prateleira "Continuar lendo" + card compacto (Onda 2) ───────── */
#continueShelf { background: transparent; }
#continueShelfTitle {
    color: #433422; font-size: 14px; font-weight: 700; letter-spacing: 0.3px;
}
QScrollArea#continueShelfScroll { background: transparent; border: none; }
#continueCard {
    background-color: #EADFCA; border: 1px solid #d4cbb8; border-radius: 10px;
}
#continueCard:hover { border-color: #8b6c42; }
#continueCardTitle { font-size: 12px; font-weight: 600; color: #433422; }
#continueCardMeta { font-size: 11px; color: #7a6a4f; }
#continueCardCoverPlaceholder {
    border-radius: 6px; font-size: 34px; color: #5c4426;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e6d8bd, stop:1 #d8c4a0);
}
QProgressBar#continueProgress {
    background-color: #d4cbb8; border: none; border-radius: 3px;
}
QProgressBar#continueProgress::chunk {
    background-color: #8b6c42; border-radius: 3px;
}

/* ── Ordenação do header da biblioteca (Tarefa 2.3) ───────────────── */
QComboBox#librarySortCombo {
    background: #EADFCA; border: 1px solid #d4cbb8; border-radius: 6px;
    padding: 4px 8px; color: #433422; font-size: 12px;
}
QComboBox#librarySortCombo:hover { border-color: #8b6c42; }
QComboBox#librarySortCombo QAbstractItemView {
    background: #EADFCA; color: #433422; selection-background-color: #8b6c42;
    selection-color: #F4ECD8;
}
QPushButton#librarySortOrderBtn {
    background: #EADFCA; border: 1px solid #d4cbb8; border-radius: 6px;
    color: #433422; font-size: 13px;
}
QPushButton#librarySortOrderBtn:hover { border-color: #8b6c42; color: #8b6c42; }
QPushButton#librarySortOrderBtn:checked {
    background: #d8c4a0; border-color: #8b6c42; color: #5c4426;
}

/* ── Estado "sem resultado" da busca/filtro (Tarefa 2.6) ──────────── */
#searchEmptyIcon { font-size: 64px; background: transparent; }
#searchEmptyText { color: #7a6a4f; font-size: 18px; font-weight: 600; background: transparent; }
#searchEmptyHint { color: #9c8a6f; font-size: 13px; background: transparent; }

/* ── Sobreposição de arraste-e-solte (Onda 2) ────────────────────── */
#dropOverlay {
    background-color: rgba(244, 236, 216, 0.86);
    border: 3px dashed #8b6c42;
}
#dropOverlayIcon { font-size: 56px; background: transparent; }
#dropOverlayLabel {
    color: #8b6c42; font-size: 24px; font-weight: 700; background: transparent;
}

/* ── Flashcards: gerar dos destaques (3.3) ─────────── */
QPushButton#flashcardsHighlightBtn {
    background: #E8DCC0;
    color: #433422;
    border: 1px solid #C9B896;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 600;
}
QPushButton#flashcardsHighlightBtn:hover {
    background: #DED0B0;
    border-color: #8b6c42;
}
QPushButton#flashcardsHighlightBtn:disabled {
    background: #EFE7D3;
    color: #A89878;
    border-color: #D8C9A8;
}

/* ── Banner "Retomar leitura" (3.7) ────────────────── */
QFrame#resumeBanner {
    background: #EFE7D3;
    border: 1px solid #8b6c42;
    border-radius: 8px;
}
#resumeBannerIcon { font-size: 15px; background: transparent; }
#resumeBannerText {
    color: #433422;
    font-size: 12px;
    background: transparent;
}
QPushButton#resumeBannerClose {
    background: transparent;
    border: none;
    border-radius: 12px;
}
QPushButton#resumeBannerClose:hover {
    background: #DED0B0;
}
/* Indicador proeminente de raciocínio/preparo do modelo (painel do Assistente) */
QLabel#ragThinkingIndicator {
    background-color: #EADFCA;
    color: #705E4B;
    border: 1px solid #d4cbb8;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 700;
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


def get_reader_css(
    theme: str,
    font_family: str | None = None,
    font_size: int | None = None,
    line_height: float | None = None,
    margin_h: int | None = None,
    margin_v: int | None = None,
) -> str:
    """CSS do conteúdo HTML do leitor (EPUB/TXT/DOCX) para o *theme* dado.

    A tipografia (fonte, tamanho, entrelinha, margens) vem das MESMAS chaves
    ``reader.*`` da config — o chamador (ReaderView) as repassa. Quando omitida,
    usa os padrões de ``constants`` (fonte única de verdade). O bloco ``body`` de
    tipografia é ANEXADO ao tema (mesma especificidade → a regra posterior
    vence), sobrepondo APENAS a tipografia e preservando cores/estrutura de cada
    tema. Isto corrige uma lacuna anterior: ``get_reader_css`` ignorava a config
    e renderizava sempre 16px/1.8/40-60px.
    """
    base = READER_THEMES.get(theme, READER_CSS_DARK)
    family = font_family or DEFAULT_FONT_FAMILY
    size = DEFAULT_FONT_SIZE if font_size is None else font_size
    line = DEFAULT_LINE_HEIGHT if line_height is None else line_height
    mh = 60 if margin_h is None else margin_h
    mv = 40 if margin_v is None else margin_v
    override = (
        "body {"
        f" font-family: '{family}', 'Georgia', 'Palatino', serif;"
        f" font-size: {size}px;"
        f" line-height: {line};"
        f" padding: {mv}px {mh}px;"
        " }"
    )
    return base + "\n" + override


# ── Helper de ícone-emoji ──────────────────────────────────────────────
#
# Embutir o emoji no texto do botão — ``QPushButton("📖 Ler")`` — renderiza
# com o glifo sobreposto ao texto no Windows (bug visual). A solução é pintar
# o emoji num QPixmap e usá-lo como ÍCONE (``setIcon``), mantendo o texto do
# botão SEM emoji: ``btn.setIcon(emoji_icon("📖")); btn.setText("Ler")``.

_EMOJI_FONT_FAMILIES = ["Segoe UI Emoji", "Noto Color Emoji"]


def emoji_icon(emoji: str, size: int = 18) -> QIcon:
    """Renderiza *emoji* num QPixmap e devolve um QIcon pronto p/ ``setIcon``.

    ``size`` é o lado do ícone em px (lógicos). Pinta em 2x (devicePixelRatio)
    para nitidez em telas HiDPI. Requer uma QApplication ativa — como todo
    QPixmap/QPainter do Qt. Fonte de emoji resolvida por família, com fallback.
    """
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        font = QFont()
        font.setFamilies(_EMOJI_FONT_FAMILIES)
        font.setPixelSize(int(size * scale * 0.86))
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
    finally:
        painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)
