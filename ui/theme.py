"""
Theme Manager - Light, Dark, and Night (red-tint) modes
"""

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal


THEMES = {
    "dark": {
        "name": "Dark",
        "icon": "🌙",
        "bg_primary":       "#0d1117",
        "bg_secondary":     "#161b22",
        "bg_tertiary":      "#21262d",
        "bg_panel":         "#1c2128",
        "bg_input":         "#0d1117",
        "border":           "#30363d",
        "border_focus":     "#58a6ff",
        "text_primary":     "#e6edf3",
        "text_secondary":   "#8b949e",
        "text_muted":       "#484f58",
        "accent":           "#1f6feb",
        "accent_hover":     "#388bfd",
        "accent_text":      "#ffffff",
        "success":          "#238636",
        "success_text":     "#3fb950",
        "warning":          "#9e6a03",
        "warning_text":     "#d29922",
        "danger":           "#da3633",
        "danger_text":      "#f85149",
        "tx_active":        "#da3633",
        "rx_active":        "#238636",
        "freq_display":     "#0d1117",
        "freq_text":        "#39d353",
        "meter_bg":         "#0d1117",
        "meter_fg":         "#39d353",
        "meter_peak":       "#f85149",
        "scrollbar_bg":     "#161b22",
        "scrollbar_fg":     "#30363d",
        "tab_active":       "#1f6feb",
        "tab_inactive":     "#161b22",
        "highlight":        "#1f6feb33",
    },
    "light": {
        "name": "Light",
        "icon": "☀️",
        "bg_primary":       "#ffffff",
        "bg_secondary":     "#f6f8fa",
        "bg_tertiary":      "#eaeef2",
        "bg_panel":         "#f0f3f7",
        "bg_input":         "#ffffff",
        "border":           "#d0d7de",
        "border_focus":     "#0969da",
        "text_primary":     "#1f2328",
        "text_secondary":   "#656d76",
        "text_muted":       "#9198a1",
        "accent":           "#0969da",
        "accent_hover":     "#0860ca",
        "accent_text":      "#ffffff",
        "success":          "#1a7f37",
        "success_text":     "#1a7f37",
        "warning":          "#9a6700",
        "warning_text":     "#9a6700",
        "danger":           "#cf222e",
        "danger_text":      "#cf222e",
        "tx_active":        "#cf222e",
        "rx_active":        "#1a7f37",
        "freq_display":     "#1f2328",
        "freq_text":        "#0969da",
        "meter_bg":         "#eaeef2",
        "meter_fg":         "#0969da",
        "meter_peak":       "#cf222e",
        "scrollbar_bg":     "#f6f8fa",
        "scrollbar_fg":     "#d0d7de",
        "tab_active":       "#0969da",
        "tab_inactive":     "#f6f8fa",
        "highlight":        "#0969da1a",
    },
    "night": {
        "name": "Night",
        "icon": "🔴",
        "bg_primary":       "#0a0000",
        "bg_secondary":     "#110000",
        "bg_tertiary":      "#1a0000",
        "bg_panel":         "#130000",
        "bg_input":         "#0a0000",
        "border":           "#3d1010",
        "border_focus":     "#cc2200",
        "text_primary":     "#ff6644",
        "text_secondary":   "#cc3311",
        "text_muted":       "#661100",
        "accent":           "#cc2200",
        "accent_hover":     "#ee3311",
        "accent_text":      "#ffccaa",
        "success":          "#660000",
        "success_text":     "#cc3300",
        "warning":          "#663300",
        "warning_text":     "#cc6600",
        "danger":           "#880000",
        "danger_text":      "#ff2200",
        "tx_active":        "#ff2200",
        "rx_active":        "#cc3300",
        "freq_display":     "#0a0000",
        "freq_text":        "#ff4400",
        "meter_bg":         "#0a0000",
        "meter_fg":         "#cc2200",
        "meter_peak":       "#ff0000",
        "scrollbar_bg":     "#110000",
        "scrollbar_fg":     "#3d1010",
        "tab_active":       "#cc2200",
        "tab_inactive":     "#110000",
        "highlight":        "#cc220033",
    },
}


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._current = "dark"

    @property
    def current(self):
        return self._current

    @property
    def colors(self):
        return THEMES[self._current]

    def set_theme(self, name: str):
        if name not in THEMES:
            return
        self._current = name
        self.apply_theme()
        self.theme_changed.emit(name)

    def apply_theme(self):
        c = THEMES[self._current]
        app = QApplication.instance()

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor(c["bg_primary"]))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor(c["text_primary"]))
        palette.setColor(QPalette.ColorRole.Base,            QColor(c["bg_secondary"]))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(c["bg_tertiary"]))
        palette.setColor(QPalette.ColorRole.Text,            QColor(c["text_primary"]))
        palette.setColor(QPalette.ColorRole.BrightText,      QColor(c["accent_text"]))
        palette.setColor(QPalette.ColorRole.Button,          QColor(c["bg_secondary"]))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor(c["text_primary"]))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor(c["accent"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["accent_text"]))
        palette.setColor(QPalette.ColorRole.Link,            QColor(c["accent"]))
        palette.setColor(QPalette.ColorRole.Mid,             QColor(c["border"]))
        palette.setColor(QPalette.ColorRole.Dark,            QColor(c["bg_tertiary"]))
        palette.setColor(QPalette.ColorRole.Shadow,          QColor(c["bg_primary"]))
        app.setPalette(palette)

        # Full QSS stylesheet
        app.setStyleSheet(self._build_qss(c))

    def _build_qss(self, c: dict) -> str:
        return f"""
/* ─── Global ─────────────────────────────────────────────── */
QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: Consolas, 'Courier New', monospace;
    font-size: 11px;
    border: none;
    outline: none;
}}

/* ─── Main Window ─────────────────────────────────────────── */
QMainWindow {{
    background-color: {c['bg_primary']};
}}

/* ─── Menu Bar ────────────────────────────────────────────── */
QMenuBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border-bottom: 1px solid {c['border']};
    padding: 2px;
}}
QMenuBar::item:selected {{
    background-color: {c['accent']};
    color: {c['accent_text']};
    border-radius: 4px;
}}
QMenu {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['accent']};
    color: {c['accent_text']};
}}

/* ─── Status Bar ──────────────────────────────────────────── */
QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    border-top: 1px solid {c['border']};
    font-size: 10px;
}}

/* ─── Tabs ────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    background-color: {c['bg_secondary']};
}}
QTabBar::tab {{
    background-color: {c['tab_inactive']};
    color: {c['text_secondary']};
    padding: 8px 18px;
    border: 1px solid {c['border']};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: bold;
    font-size: 11px;
}}
QTabBar::tab:selected {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border-bottom: 2px solid {c['accent']};
}}
QTabBar::tab:hover:!selected {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
}}

/* ─── GroupBox ────────────────────────────────────────────── */
QGroupBox {{
    border: 1px solid {c['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding: 8px;
    font-weight: bold;
    color: {c['text_secondary']};
    font-size: 10px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {c['text_secondary']};
}}

/* ─── Buttons ─────────────────────────────────────────────── */
QPushButton {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 14px;
    font-family: Consolas, monospace;
    font-weight: bold;
    font-size: 11px;
}}
QPushButton:hover {{
    background-color: {c['accent']};
    color: {c['accent_text']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['accent_hover']};
}}
QPushButton:disabled {{
    color: {c['text_muted']};
    border-color: {c['border']};
    background-color: {c['bg_secondary']};
}}
QPushButton#btn_connect {{
    background-color: {c['success']};
    color: {c['success_text']};
    border-color: {c['success_text']};
    font-size: 12px;
    padding: 8px 20px;
}}
QPushButton#btn_connect:hover {{
    background-color: {c['success_text']};
    color: #000000;
}}
QPushButton#btn_ptt {{
    background-color: {c['danger']};
    color: {c['danger_text']};
    border-color: {c['danger_text']};
    font-size: 18px;
    font-weight: bold;
    padding: 16px 32px;
    border-radius: 8px;
    border-width: 2px;
}}
QPushButton#btn_ptt:checked {{
    background-color: {c['tx_active']};
    color: #ffffff;
    border-color: #ffffff;
}}
QPushButton#btn_tx_toggle {{
    background-color: {c['warning']};
    color: {c['warning_text']};
    border-color: {c['warning_text']};
}}

/* ─── Line Edits ──────────────────────────────────────────── */
QLineEdit {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 5px 8px;
    font-family: Consolas, monospace;
    selection-background-color: {c['accent']};
}}
QLineEdit:focus {{
    border-color: {c['border_focus']};
}}

/* ─── Combo Boxes ─────────────────────────────────────────── */
QComboBox {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 5px 8px;
    font-family: Consolas, monospace;
    min-width: 80px;
}}
QComboBox:focus {{
    border-color: {c['border_focus']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent']};
    selection-color: {c['accent_text']};
    border-radius: 4px;
}}

/* ─── Spin Boxes ──────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 4px 6px;
    font-family: Consolas, monospace;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['border_focus']};
}}

/* ─── Sliders ─────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    height: 4px;
    background-color: {c['border']};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {c['accent']};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::sub-page:horizontal {{
    background-color: {c['accent']};
    border-radius: 2px;
}}

/* ─── CheckBox ────────────────────────────────────────────── */
QCheckBox {{
    color: {c['text_primary']};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {c['border']};
    border-radius: 3px;
    background-color: {c['bg_input']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}

/* ─── Table ───────────────────────────────────────────────── */
QTableWidget {{
    background-color: {c['bg_secondary']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    selection-background-color: {c['highlight']};
    alternate-background-color: {c['bg_tertiary']};
}}
QTableWidget::item {{
    padding: 4px 8px;
    border: none;
    color: {c['text_primary']};
}}
QTableWidget::item:selected {{
    background-color: {c['highlight']};
    color: {c['text_primary']};
}}
QHeaderView::section {{
    background-color: {c['bg_tertiary']};
    color: {c['text_secondary']};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {c['border']};
    border-bottom: 1px solid {c['border']};
    font-weight: bold;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* ─── Text Edit / Log ─────────────────────────────────────── */
QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 11px;
    selection-background-color: {c['accent']};
}}

/* ─── Scrollbars ──────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: {c['scrollbar_bg']};
    width: 10px;
    border-radius: 5px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {c['scrollbar_fg']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {c['accent']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{
    background-color: {c['scrollbar_bg']};
    height: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal {{
    background-color: {c['scrollbar_fg']};
    border-radius: 5px;
    min-width: 30px;
}}

/* ─── Label ───────────────────────────────────────────────── */
QLabel#freq_display {{
    font-family: 'Courier New', Consolas, monospace;
    font-size: 36px;
    font-weight: bold;
    color: {c['freq_text']};
    background-color: {c['freq_display']};
    border: 2px solid {c['border']};
    border-radius: 8px;
    padding: 8px 16px;
    letter-spacing: 4px;
}}
QLabel#band_label {{
    font-size: 14px;
    font-weight: bold;
    color: {c['accent']};
    letter-spacing: 2px;
}}
QLabel#mode_label {{
    font-size: 20px;
    font-weight: bold;
    color: {c['warning_text']};
    letter-spacing: 2px;
}}
QLabel#status_indicator {{
    font-size: 11px;
    font-weight: bold;
    padding: 3px 10px;
    border-radius: 10px;
}}
QLabel#status_rx {{
    background-color: {c['rx_active']};
    color: {c['success_text']};
}}
QLabel#status_tx {{
    background-color: {c['tx_active']};
    color: #ffffff;
}}
QLabel#status_off {{
    background-color: {c['bg_tertiary']};
    color: {c['text_muted']};
}}

/* ─── Splitter ────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {c['border']};
    width: 2px;
    height: 2px;
}}

/* ─── ToolTip ─────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ─── Progress Bar ────────────────────────────────────────── */
QProgressBar {{
    background-color: {c['meter_bg']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    text-align: center;
    color: {c['text_primary']};
    font-size: 10px;
}}
QProgressBar::chunk {{
    background-color: {c['meter_fg']};
    border-radius: 3px;
}}

/* ─── Frame ───────────────────────────────────────────────── */
QFrame[frameShape="4"],  /* HLine */
QFrame[frameShape="5"]   /* VLine */ {{
    color: {c['border']};
    background-color: {c['border']};
}}
"""


# Global theme manager instance
theme_manager = ThemeManager()
