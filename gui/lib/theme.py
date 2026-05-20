from PyQt5.QtWidgets import QApplication


ThemeName = str


LIGHT_THEME = """
QWidget {
    background-color: #f4f6f8;
    color: #1f2933;
    selection-background-color: #277da1;
    selection-color: #ffffff;
}
QMainWindow,
QSplitter,
QStackedWidget {
    background-color: #f4f6f8;
}
QFrame {
    background-color: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 6px;
}
QLineEdit,
QPlainTextEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #1f2933;
    padding: 7px 9px;
}
QLineEdit:focus,
QPlainTextEdit:focus {
    border-color: #277da1;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #1f2933;
    min-height: 28px;
    padding: 6px 10px;
}
QPushButton:hover {
    background-color: #eef6f9;
    border-color: #89bccc;
}
QPushButton:checked {
    background-color: #d8eef5;
    border-color: #277da1;
    color: #0b4253;
    font-weight: bold;
}
QPushButton:disabled {
    background-color: #e5e7eb;
    border-color: #d1d5db;
    color: #8b95a1;
}
QPushButton#TopBarButton {
    min-height: 24px;
    padding: 2px 10px;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox#TopBarCheck {
    padding: 0;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QTabWidget::pane {
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #e5e7eb;
    border: 1px solid #cbd5e1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #334155;
    min-width: 92px;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0b4253;
    font-weight: bold;
}
QToolTip {
    background-color: #1f2933;
    border: 1px solid #64748b;
    color: #ffffff;
}
QLabel#PanelTitle {
    color: #1f2933;
    font-size: 15px;
    font-weight: bold;
}
QLabel#SummaryLabel {
    background-color: rgba(31, 41, 51, 0.06);
    border: 1px solid #d9e2ec;
    border-radius: 6px;
    color: #334155;
    font-size: 12px;
    padding: 8px;
}
"""


DARK_THEME = """
QWidget {
    background-color: #101419;
    color: #e6edf3;
    selection-background-color: #2aa9c0;
    selection-color: #061216;
}
QMainWindow,
QSplitter,
QStackedWidget {
    background-color: #101419;
}
QFrame {
    background-color: #161d24;
    border: 1px solid #2c3845;
    border-radius: 6px;
}
QLineEdit,
QPlainTextEdit {
    background-color: #0d1117;
    border: 1px solid #314150;
    border-radius: 6px;
    color: #e6edf3;
    padding: 7px 9px;
}
QLineEdit:focus,
QPlainTextEdit:focus {
    border-color: #2aa9c0;
}
QLineEdit::placeholder,
QPlainTextEdit {
    color: #9aa8b5;
}
QPushButton {
    background-color: #1d2730;
    border: 1px solid #354656;
    border-radius: 6px;
    color: #e6edf3;
    min-height: 28px;
    padding: 6px 10px;
}
QPushButton:hover {
    background-color: #263440;
    border-color: #4f7184;
}
QPushButton:checked {
    background-color: #144c5a;
    border-color: #2aa9c0;
    color: #ecfeff;
    font-weight: bold;
}
QPushButton:disabled {
    background-color: #182029;
    border-color: #25313d;
    color: #667789;
}
QPushButton#TopBarButton {
    min-height: 24px;
    padding: 2px 10px;
}
QCheckBox {
    spacing: 8px;
}
QCheckBox#TopBarCheck {
    padding: 0;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    background-color: #0d1117;
    border: 1px solid #516170;
    border-radius: 4px;
}
QCheckBox::indicator:checked {
    background-color: #2aa9c0;
    border: 1px solid #6fe6f7;
    border-radius: 4px;
}
QTabWidget::pane {
    border: 1px solid #354656;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #182029;
    border: 1px solid #354656;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #9aa8b5;
    min-width: 92px;
    padding: 5px 10px;
}
QTabBar::tab:selected {
    background-color: #0d1117;
    color: #ecfeff;
    font-weight: bold;
}
QScrollBar:vertical,
QScrollBar:horizontal {
    background-color: #101419;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {
    background-color: #344554;
    border-radius: 4px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {
    background-color: #486174;
}
QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {
    background: none;
    border: none;
}
QToolTip {
    background-color: #17212b;
    border: 1px solid #4f7184;
    color: #e6edf3;
}
QLabel#PanelTitle {
    color: #e6edf3;
    font-size: 15px;
    font-weight: bold;
}
QLabel#SummaryLabel {
    background-color: rgba(255, 255, 255, 0.035);
    border: 1px solid #2c3845;
    border-radius: 6px;
    color: #c9d6e2;
    font-size: 12px;
    padding: 8px;
}
"""


def normalize_theme(theme_name: str | None) -> ThemeName:
    if theme_name and theme_name.lower() == "light":
        return "light"
    return "dark"


def apply_app_theme(theme_name: str | None) -> ThemeName:
    theme = normalize_theme(theme_name)
    app = QApplication.instance()
    if app is None:
        return theme

    app.setStyleSheet(DARK_THEME if theme == "dark" else LIGHT_THEME)
    return theme
