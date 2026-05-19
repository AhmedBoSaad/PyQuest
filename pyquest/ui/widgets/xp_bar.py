"""Animated XP progress bar with level + streak chips."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class XPBar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Standing pill (LEVEL 1, LEVEL 2, …)
        self.level_label = QLabel("LEVEL 1")
        self.level_label.setObjectName("PillAccent")
        self.level_label.setStyleSheet(
            "background-color: #D4B361; color: #2E2210; border-radius: 999px;"
            "padding: 5px 14px; font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; font-weight: 700; letter-spacing: 2px;"
        )

        self.bar = QProgressBar()
        self.bar.setRange(0, 200)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setFixedWidth(240)

        self.xp_label = QLabel("0 / 200 XP")
        self.xp_label.setStyleSheet(
            "font-family: 'JetBrains Mono','Cascadia Code','Consolas',monospace;"
            "font-size: 11px; color: #C4BFB1; letter-spacing: 1px;"
        )

        self.streak_label = QLabel("· 0 days ·")
        self.streak_label.setObjectName("Pill")

        layout.addWidget(self.level_label)
        layout.addWidget(self.bar)
        layout.addWidget(self.xp_label)
        layout.addStretch(1)
        layout.addWidget(self.streak_label)

        self._anim = QPropertyAnimation(self.bar, b"value")
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def update_state(self, level: int, xp_into: int, xp_for_next: int, streak: int) -> None:
        self.level_label.setText(f"LEVEL {level}")
        self.bar.setRange(0, max(1, xp_for_next))
        self._anim.stop()
        self._anim.setStartValue(self.bar.value())
        self._anim.setEndValue(xp_into)
        self._anim.start()
        self.xp_label.setText(f"{xp_into} / {xp_for_next} XP")
        if streak:
            self.streak_label.setText(f"·  {streak}-DAY STREAK  ·")
        else:
            self.streak_label.setText("·  NEW BOOK  ·")


