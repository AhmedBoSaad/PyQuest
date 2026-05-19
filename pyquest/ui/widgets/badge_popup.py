"""Achievement toast: fades + slides in, auto-dismisses."""
from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    QTimer,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class BadgePopup(QFrame):
    def __init__(self, parent: QWidget, title: str, subtitle: str, icon: str = "🏆") -> None:
        super().__init__(parent)
        self.setObjectName("CardAccent")
        self.setFixedSize(360, 90)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(None)  # placeholder; opacity effect set below

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px;")

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        head = QLabel(title)
        head.setObjectName("H3")
        sub = QLabel(subtitle)
        sub.setObjectName("Dim")
        sub.setWordWrap(True)
        text_box.addWidget(head)
        text_box.addWidget(sub)

        layout.addWidget(icon_label)
        layout.addLayout(text_box, 1)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

    def show_at_top_right(self, parent_rect_w: int, parent_rect_h: int) -> None:
        margin = 24
        target_x = parent_rect_w - self.width() - margin
        target_y = margin
        self.move(target_x + 80, target_y - 20)
        self.show()

        fade_in = QPropertyAnimation(self._opacity, b"opacity")
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)

        slide_in = QPropertyAnimation(self, b"pos")
        slide_in.setDuration(400)
        slide_in.setStartValue(self.pos())
        slide_in.setEndValue(QPoint(target_x, target_y))
        slide_in.setEasingCurve(QEasingCurve.OutCubic)

        fade_out = QPropertyAnimation(self._opacity, b"opacity")
        fade_out.setDuration(400)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addPause(2400)
        group.addAnimation(fade_out)
        group.finished.connect(self.deleteLater)
        group.start()

        # Run slide_in in parallel
        slide_in.start()
        self._anim_refs = (fade_in, slide_in, fade_out, group)
        QTimer.singleShot(100, self.raise_)
