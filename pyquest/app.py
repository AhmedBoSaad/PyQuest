"""QApplication bootstrap."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from pyquest.config import APP_NAME, APP_VERSION, PYQUEST_DIR, get_theme
from pyquest.logging_setup import setup_logging
from pyquest.ui.main_window import MainWindow
from pyquest.ui.theme import build_stylesheet


def _load_bundled_fonts() -> None:
    """Register any .ttf/.otf files shipped in pyquest/data/fonts/.

    Lets the editorial 'Studio' theme use Instrument Serif / Geist / JetBrains Mono
    when the user drops them in. If absent, the theme falls back to system serif /
    Segoe UI / Cascadia Code automatically via QSS font-family lists.
    """
    fonts_dir: Path = PYQUEST_DIR / "data" / "fonts"
    if not fonts_dir.is_dir():
        return
    for path in list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")):
        QFontDatabase.addApplicationFont(str(path))


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyle("Fusion")
    _load_bundled_fonts()
    app.setStyleSheet(build_stylesheet(get_theme()))
    # Default UI font. QSS overrides per widget with proper family lists.
    app.setFont(QFont("Segoe UI", 10))

    window = MainWindow()
    window.show()
    return app.exec()
