"""PyQuest Studio theme: editorial.

Two palettes: dark "ink" (warm near-black) and light "cream" (warm paper).
Same gold signal accent in both. Single source of truth for every color so
runtime theme swapping is a single function call.
"""
from __future__ import annotations

# ---- Fonts (with cross-platform fallbacks) ---------------------------------
FONT_DISPLAY = '"Instrument Serif", "Cambria", "Georgia", serif'
FONT_SANS = '"Geist", "Inter", "Segoe UI", system-ui, sans-serif'
FONT_MONO = '"JetBrains Mono", "Cascadia Code", "Consolas", monospace'

# ---- Palettes --------------------------------------------------------------
DARK = {
    "BG": "#1B1815",
    "SURFACE": "#23201D",
    "SURFACE_ALT": "#2D2925",
    "LINE": "#454039",
    "LINE_SOFT": "#3D3933",
    "TEXT": "#EEEAE0",
    "TEXT_DIM": "#C4BFB1",
    "TEXT_MUTED": "#928D7F",
    "ACCENT": "#D4B361",
    "ACCENT_DIM": "#A0853F",
    "ACCENT_HOVER": "#E0C075",
    "ACCENT_INK": "#2E2210",
    "GREEN": "#5DC78C",
    "GREEN_INK": "#0A2A1C",
    "ROSE": "#E08B7B",
    "WARNING": "#D4A85B",
    "CONSOLE_BG": "#100D0A",
    "EDITOR_BG": "#1B1815",
}

LIGHT = {
    "BG": "#F5F1E8",            # warm cream
    "SURFACE": "#FFFFFF",       # cards
    "SURFACE_ALT": "#EDE7D7",   # raised
    "LINE": "#C9C0AC",
    "LINE_SOFT": "#DBD3BE",
    "TEXT": "#1B1815",
    "TEXT_DIM": "#4A4540",
    "TEXT_MUTED": "#7B7368",
    "ACCENT": "#A0853F",        # darker gold so contrast works on cream
    "ACCENT_DIM": "#7C6829",
    "ACCENT_HOVER": "#B89945",
    "ACCENT_INK": "#FFFFFF",
    "GREEN": "#2E8C5A",
    "GREEN_INK": "#FFFFFF",
    "ROSE": "#C75646",
    "WARNING": "#A77026",
    "CONSOLE_BG": "#FFFFFF",
    "EDITOR_BG": "#FCF8EE",
}


def _stylesheet(p: dict[str, str]) -> str:
    """Render the QSS string for a palette dict."""
    return f"""
/* ----- base ----- */
* {{
    color: {p['TEXT']};
    font-family: {FONT_SANS};
    font-size: 13px;
    letter-spacing: 0px;
}}
QMainWindow, QWidget {{
    background-color: {p['BG']};
}}

/* ----- sidebar / topbar / cards ----- */
QFrame#Sidebar {{
    background-color: {p['SURFACE']};
    border-right: 1px solid {p['LINE_SOFT']};
}}
QFrame#TopBar {{
    background-color: {p['BG']};
    border-bottom: 1px solid {p['LINE_SOFT']};
}}
QFrame#Card {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 14px;
}}
QFrame#CardAccent {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['ACCENT']};
    border-radius: 14px;
}}

/* ----- typography ----- */
QLabel#H1 {{
    font-family: {FONT_DISPLAY};
    font-size: 38px; font-weight: 400; color: {p['TEXT']};
}}
QLabel#H2 {{
    font-family: {FONT_DISPLAY};
    font-size: 24px; font-weight: 400; color: {p['TEXT']};
}}
QLabel#H3 {{
    font-size: 13px; font-weight: 600; color: {p['TEXT']};
}}
QLabel#Dim {{ color: {p['TEXT_DIM']}; }}
QLabel#Eyebrow {{
    font-family: {FONT_MONO};
    font-size: 10px;
    color: {p['ACCENT']};
    letter-spacing: 2px;
}}
QLabel#Pill {{
    background-color: {p['SURFACE_ALT']};
    color: {p['TEXT_DIM']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 999px;
    padding: 4px 10px;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
QLabel#PillAccent {{
    background-color: {p['ACCENT']};
    color: {p['ACCENT_INK']};
    border-radius: 999px;
    padding: 5px 12px;
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QLabel#PillSuccess {{
    background-color: {p['GREEN']};
    color: {p['GREEN_INK']};
    border-radius: 999px;
    padding: 5px 12px;
    font-family: {FONT_MONO};
    font-size: 11px;
    font-weight: 700;
}}

/* ----- buttons ----- */
QPushButton {{
    background-color: transparent;
    color: {p['TEXT']};
    border: 1px solid {p['LINE']};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 500;
}}
QPushButton:hover {{ border-color: {p['TEXT_MUTED']}; }}
QPushButton:disabled {{ color: {p['TEXT_MUTED']}; border-color: {p['LINE_SOFT']}; }}
QPushButton#Primary {{
    background-color: {p['ACCENT']};
    color: {p['ACCENT_INK']};
    border: 1px solid {p['ACCENT']};
    font-weight: 600;
    padding: 10px 18px;
}}
QPushButton#Primary:hover {{
    background-color: {p['ACCENT_HOVER']};
    border-color: {p['ACCENT_HOVER']};
}}
QPushButton#Success {{
    background-color: {p['GREEN']};
    color: {p['GREEN_INK']};
    border: 1px solid {p['GREEN']};
    font-weight: 600;
}}
QPushButton#Ghost {{
    background-color: transparent;
    color: {p['TEXT_DIM']};
    border: 1px solid transparent;
}}
QPushButton#Ghost:hover {{
    color: {p['TEXT']};
    background-color: {p['SURFACE_ALT']};
    border: 1px solid {p['LINE_SOFT']};
}}

QPushButton#NavItem {{
    background-color: transparent;
    border: none;
    text-align: left;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13.5px;
    font-weight: 500;
    color: {p['TEXT_DIM']};
}}
QPushButton#NavItem:hover {{
    background-color: {p['SURFACE_ALT']};
    color: {p['TEXT']};
}}
QPushButton#NavItem:checked {{
    background-color: {p['SURFACE_ALT']};
    color: {p['TEXT']};
    border-left: 2px solid {p['ACCENT']};
    padding-left: 12px;
    font-weight: 600;
}}

/* ----- inputs ----- */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background-color: {p['SURFACE_ALT']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 8px;
    padding: 8px 10px;
    color: {p['TEXT']};
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ACCENT_INK']};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border-color: {p['ACCENT']};
}}

QComboBox {{
    padding-right: 28px;
    combobox-popup: 0;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border: none;
    border-left: 1px solid {p['LINE_SOFT']};
    background: transparent;
}}
QComboBox::down-arrow {{
    width: 0px; height: 0px;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {p['ACCENT']};
    margin-right: 2px;
}}
QComboBox::down-arrow:on {{ border-top: 6px solid {p['ACCENT_HOVER']}; }}
QComboBox QAbstractItemView {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['LINE']};
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ACCENT_INK']};
    outline: 0;
    padding: 6px 0;
    color: {p['TEXT']};
}}
QComboBox QAbstractItemView::item {{
    background-color: {p['SURFACE']};
    color: {p['TEXT']};
    padding: 8px 12px;
    border: none;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: {p['SURFACE_ALT']};
    color: {p['TEXT']};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {p['ACCENT']};
    color: {p['ACCENT_INK']};
}}

QPlainTextEdit#Editor {{
    font-family: {FONT_MONO};
    font-size: 13px;
    background-color: {p['EDITOR_BG']};
    border: 1px solid {p['LINE_SOFT']};
    color: {p['TEXT']};
}}
QPlainTextEdit#Console {{
    font-family: {FONT_MONO};
    font-size: 12px;
    background-color: {p['CONSOLE_BG']};
    border: 1px solid {p['LINE_SOFT']};
    color: {p['TEXT']};
}}

/* ----- progress bar ----- */
QProgressBar {{
    background-color: {p['SURFACE_ALT']};
    border: none;
    border-radius: 4px;
    text-align: center;
    color: {p['TEXT']};
    height: 8px;
}}
QProgressBar::chunk {{
    background-color: {p['ACCENT']};
    border-radius: 4px;
}}

/* ----- scrollbars ----- */
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {p['LINE']}; border-radius: 5px; min-height: 24px; }}
QScrollBar::handle:vertical:hover {{ background: {p['ACCENT_DIM']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {p['LINE']}; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0px; }}

/* ----- lesson cards ----- */
QPushButton#LessonCard {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 14px;
    padding: 18px;
    text-align: left;
}}
QPushButton#LessonCard:hover {{
    border-color: {p['ACCENT']};
    background-color: {p['SURFACE_ALT']};
}}
QPushButton#LessonCardLocked {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 14px;
    padding: 18px;
    text-align: left;
    color: {p['TEXT_MUTED']};
}}
QPushButton#LessonCardDone {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['GREEN']};
    border-radius: 14px;
    padding: 18px;
    text-align: left;
}}

/* ----- quiz options ----- */
QPushButton#QuizOption {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['LINE_SOFT']};
    border-radius: 12px;
    padding: 16px 20px;
    text-align: left;
    font-size: 15px;
    color: {p['TEXT']};
}}
QPushButton#QuizOption:hover {{ border-color: {p['LINE']}; }}
QPushButton#QuizOptionCorrect {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['GREEN']};
    border-radius: 12px;
    padding: 16px 20px;
    text-align: left;
    font-size: 15px;
    color: {p['GREEN']};
    font-weight: 600;
}}
QPushButton#QuizOptionWrong {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['ROSE']};
    border-radius: 12px;
    padding: 16px 20px;
    text-align: left;
    font-size: 15px;
    color: {p['ROSE']};
    font-weight: 600;
}}

/* ----- tooltips ----- */
QToolTip {{
    background-color: {p['SURFACE_ALT']};
    color: {p['TEXT']};
    border: 1px solid {p['LINE']};
    padding: 6px 8px;
    border-radius: 6px;
    font-family: {FONT_MONO};
    font-size: 11px;
}}

/* ----- check boxes ----- */
QCheckBox {{ color: {p['TEXT_DIM']}; spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {p['LINE']};
    border-radius: 4px;
    background: {p['SURFACE_ALT']};
}}
QCheckBox::indicator:checked {{
    background: {p['ACCENT']};
    border-color: {p['ACCENT']};
}}
"""


def build_stylesheet(theme: str = "dark") -> str:
    palette = LIGHT if theme == "light" else DARK
    return _stylesheet(palette)
