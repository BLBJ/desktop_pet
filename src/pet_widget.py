"""
宠物渲染控件 - PetWidget
负责在透明背景上绘制当前动画帧。
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtWidgets import QWidget


class PetWidget(QWidget):

    def __init__(self, scale: float = 1.0, parent=None):
        super().__init__(parent)
        self._scale = scale
        self._current_pixmap: QPixmap | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")
        self.setFixedSize(128, 128)

    def set_frame(self, pixmap: QPixmap) -> None:
        if pixmap is None or pixmap.isNull():
            return
        self._current_pixmap = pixmap
        new_w = max(1, int(pixmap.width() * self._scale))
        new_h = max(1, int(pixmap.height() * self._scale))
        if self.width() != new_w or self.height() != new_h:
            self.setFixedSize(new_w, new_h)
        self.update()

    def set_scale(self, scale: float) -> None:
        self._scale = max(0.1, min(scale, 5.0))
        if self._current_pixmap:
            new_w = max(1, int(self._current_pixmap.width() * self._scale))
            new_h = max(1, int(self._current_pixmap.height() * self._scale))
            self.setFixedSize(new_w, new_h)
            self.update()

    def scale_factor(self) -> float:
        return self._scale

    def paintEvent(self, event) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target_rect = self.rect()
        source_rect = self._current_pixmap.rect()
        painter.drawPixmap(target_rect, self._current_pixmap, source_rect)
        painter.end()
