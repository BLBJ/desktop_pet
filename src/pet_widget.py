"""
宠物渲染控件 - PetWidget
负责在透明背景上绘制当前动画帧。
Paints the current animation frame on a transparent background.
"""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter
from PyQt6.QtWidgets import QWidget


class PetWidget(QWidget):
    """
    宠物渲染控件。
    - 完全透明背景，仅显示宠物图像的可见像素（RGBA alpha 通道）。
    - 根据缩放比例调整自身大小。
    """

    def __init__(self, scale: float = 1.0, parent=None):
        """
        Args:
            scale: 缩放比例（1.0 = 原始大小）
            parent: 父控件
        """
        super().__init__(parent)
        self._scale = scale
        self._current_pixmap: QPixmap | None = None

        # 启用透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        # 初始尺寸
        self.setFixedSize(128, 128)

    # ---- 公共接口 ----

    def set_frame(self, pixmap: QPixmap) -> None:
        """
        设置当前要显示的帧。

        Args:
            pixmap: 当前动画帧（QPixmap with alpha channel）
        """
        if pixmap is None or pixmap.isNull():
            return
        self._current_pixmap = pixmap

        # 根据缩放调整控件大小
        new_w = max(1, int(pixmap.width() * self._scale))
        new_h = max(1, int(pixmap.height() * self._scale))
        if self.width() != new_w or self.height() != new_h:
            self.setFixedSize(new_w, new_h)

        self.update()  # 触发重绘

    def set_scale(self, scale: float) -> None:
        """动态修改缩放比例。"""
        self._scale = max(0.1, min(scale, 5.0))

        # 用当前帧重新计算尺寸
        if self._current_pixmap:
            new_w = max(1, int(self._current_pixmap.width() * self._scale))
            new_h = max(1, int(self._current_pixmap.height() * self._scale))
            self.setFixedSize(new_w, new_h)
            self.update()

    def scale_factor(self) -> float:
        return self._scale

    # ---- 绘制 ----

    def paintEvent(self, event) -> None:
        """
        绘制事件：在透明背景上渲染当前帧。
        整个控件区域除宠物像素外完全透明。
        """
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 缩放绘制
        target_rect = self.rect()
        source_rect = self._current_pixmap.rect()
        painter.drawPixmap(target_rect, self._current_pixmap, source_rect)

        painter.end()
