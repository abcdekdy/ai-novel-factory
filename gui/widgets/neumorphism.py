"""
Apple Light 核心组件 — PyQt6 实现 (v6)

实心白色卡片 + 轻投影 (macOS 风格):
  - AppleCard (凸面卡片): 纯白底 + 轻投影 (QGraphicsDropShadowEffect)
  - AppleInset (输入/凹陷面): 浅灰底 + 细边框
  - AppleInput: 包装 QTextEdit / QLineEdit 的 AppleInset 容器

用法:
    card = AppleCard(radius=14, parent=self)
    lay = card.content_layout()
    lay.addWidget(...)

    edit = QTextEdit()
    neu = AppleInput(edit, radius=10, parent=self)
"""

from PyQt6.QtWidgets import (
    QFrame, QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect,
    QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QPainter

import assets.design_tokens as dt


# =======================================================================
#  私有辅助
# =======================================================================
def _shadow_effect(color_hex, alpha, blur, y_offset, parent):
    """构建 Apple 风格轻投影 QGraphicsDropShadowEffect。"""
    eff = QGraphicsDropShadowEffect(parent)
    c = QColor(color_hex)
    c.setAlphaF(alpha)
    eff.setColor(c)
    eff.setOffset(0, y_offset)
    eff.setBlurRadius(blur)
    return eff


def _card_shadow(parent, strong=False):
    """Apple 卡片标准投影。"""
    alpha = dt.SHADOW_STRONG_ALPHA if strong else dt.SHADOW_ALPHA
    blur = dt.SHADOW_STRONG_BLUR if strong else dt.SHADOW_BLUR
    y = dt.SHADOW_STRONG_Y if strong else dt.SHADOW_Y
    return _shadow_effect(dt.SHADOW_COLOR, alpha, blur, y, parent)


# =======================================================================
#  AppleCard — 纯白卡片 + 轻投影
# =======================================================================
class AppleCard(QFrame):
    """
    Apple 风格卡片 — 纯白底 + 轻投影 + 顶部高光。
    .content_layout() 获取内容 QVBoxLayout。
    """
    def __init__(self, radius=None, strong_shadow=False, parent=None):
        super().__init__(parent)
        self._radius = radius if radius is not None else dt.RADIUS_LG
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setGraphicsEffect(_card_shadow(self, strong=strong_shadow))
        self.setStyleSheet(f"""
            AppleCard {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {self._radius}px;
            }}
        """)
        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(dt.LG, dt.LG, dt.LG, dt.LG)
        self._inner.setSpacing(0)

    def content_layout(self):
        return self._inner

    def paintEvent(self, event):
        """绘制顶部高光（参考 dashdot 玻璃拟态）。"""
        try:
            super().paintEvent(event)
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            # 顶部 1px 高光
            highlight = QColor(dt.TEXT_PRIMARY)
            highlight.setAlphaF(dt.HIGHLIGHT_ALPHA)
            p.setPen(highlight)
            p.drawLine(0, 0, self.width(), 0)
        except Exception as e:
            print(f"[AppleCard paintEvent ERROR] {e}")


# =======================================================================
#  AppleInset — 浅灰凹陷面 (输入区 / 日志区)
# =======================================================================
class AppleInset(QFrame):
    """
    Apple 风格凹陷容器 — 浅灰底 + 细边框。
    适合输入框背景、日志控制台、章节列表。
    """
    def __init__(self, radius=None, parent=None):
        super().__init__(parent)
        self._radius = radius if radius is not None else dt.RADIUS_MD
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AppleInset {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER};
                border-radius: {self._radius}px;
            }}
        """)


# =======================================================================
#  AppleInput — 凹陷输入区包装器
# =======================================================================
class AppleInput(QFrame):
    """
    包装任意 QTextEdit / QLineEdit，外层套 AppleInset 视觉。
    """
    def __init__(self, child_widget, radius=None, parent=None):
        super().__init__(parent)
        self._radius = radius if radius is not None else dt.RADIUS_MD
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AppleInput {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {self._radius}px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(dt.MD, dt.MD, dt.MD, dt.MD)
        lay.setSpacing(0)
        self._child = child_widget
        child_widget.setParent(self)
        lay.addWidget(child_widget)


# =======================================================================
#  便捷函数
# =======================================================================
def neu_bump(widget, radius=None):
    """快速给 widget 加 Apple 卡片效果 (白底 + 轻投影)。"""
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    widget.setGraphicsEffect(_card_shadow(widget, strong=False))
    r = radius if radius is not None else dt.RADIUS_LG
    widget.setStyleSheet(f"""
        background-color: {dt.SURFACE};
        border: 1px solid {dt.BORDER_LIGHT};
        border-radius: {r}px;
    """)


def neu_pressed(widget):
    """按下态 — 浅灰底。"""
    widget.setStyleSheet(f"background-color: {dt.BG_PRESSED};")


def fade_widget(widget, duration=200):
    """淡入效果（用于卡片/页面出现动画）。"""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start()
    # 防止动画被垃圾回收
    widget._fade_anim = anim
    return anim


# =======================================================================
#  AppleContainer — 兼容旧 QFrame + inner_layout 用法
# =======================================================================
class AppleContainer(QFrame):
    """
    语义对齐旧 'QFrame + inner_layout'。
    .inner_layout() 返回 QVBoxLayout, 首次调用时创建。
    默认 Apple 卡片风格 (白底 + 轻投影)。
    """
    def __init__(self, radius=None, parent=None):
        super().__init__(parent)
        self._radius = radius if radius is not None else dt.RADIUS_LG
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setGraphicsEffect(_card_shadow(self, strong=False))
        self.setStyleSheet(f"""
            background-color: {dt.SURFACE};
            border: 1px solid {dt.BORDER_LIGHT};
            border-radius: {self._radius}px;
        """)

    def inner_layout(self):
        if not hasattr(self, "_inner"):
            self._inner = QVBoxLayout(self)
            self._inner.setContentsMargins(8, 8, 8, 8)
            self._inner.setSpacing(0)
        return self._inner
