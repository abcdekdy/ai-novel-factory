"""
Launch Window — Apple Light Style
极简白底入口页 · Apple Blue 启动按钮 · 轻投影 logo 卡片
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QColor

from assets import design_tokens as dt


class LaunchWindow(QWidget):
    """Apple-style launch entry — clean white welcome."""

    launched = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Novel Factory")
        self.setFixedSize(540, 680)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(64, 80, 64, 64)

        # Apple 风格 logo 卡片 — 白底 + 轻投影
        logo_card = _LaunchCard()
        layout.addWidget(logo_card)

        layout.addStretch()

        # 提供商标识
        provider = QLabel("Powered by LongCat-2.0")
        provider.setFont(QFont("Inter", 11))
        provider.setStyleSheet(f"color: {dt.TEXT_MUTED}; margin-bottom: 16px;")
        provider.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(provider)

        # 状态
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Inter", 12))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            f"color: {dt.TEXT_MUTED}; margin-bottom: 12px;")
        layout.addWidget(self.status_label)

        # 主按钮 — Apple Blue
        self.launch_btn = QPushButton("Start")
        self.launch_btn.setFixedSize(200, 50)
        self.launch_btn.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        self.launch_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.launch_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {dt.ACCENT};
                color: {dt.TEXT_INVERSE};
                border: none;
                border-radius: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {dt.ACCENT_HOVER}; }}
            QPushButton:pressed {{ background-color: {dt.ACCENT_DIM}; }}
        """)
        self.launch_btn.clicked.connect(self._on_launch)
        layout.addWidget(self.launch_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Footer
        footer = QLabel("v1.0  ·  AI Novel Factory")
        footer.setFont(QFont("Inter", 10))
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet(f"color: {dt.TEXT_DISABLED}; margin-top: 28px;")
        layout.addWidget(footer)

    def _on_launch(self):
        self.launch_btn.setEnabled(False)
        self.status_label.setText("Loading...")
        self.status_label.setStyleSheet(
            f"color: {dt.ACCENT}; margin-bottom: 12px;")
        QTimer.singleShot(500, self.launched.emit)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_launch()
        super().keyPressEvent(event)


# ---------- helper widgets ----------
class _LaunchCard(QFrame):
    """Apple 风格 logo 卡片 — 白底 + 轻投影。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(280)

        # Apple 轻投影
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)

        self.setStyleSheet(f"""
            _LaunchCard {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {dt.RADIUS_XL}px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 28, 24, 28)
        lay.setSpacing(10)

        name = QLabel("AI Novel Factory")
        name.setFont(QFont("Inter", 36, QFont.Weight.Bold))
        name.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        lay.addWidget(name)

        tagline = QLabel("Multi-Agent Novel Generation")
        tagline.setFont(QFont("Inter", 14, QFont.Weight.Normal))
        tagline.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        lay.addWidget(tagline)

        # 细分隔线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {dt.BORDER_LIGHT}; margin: 22px 0;")
        line.setMinimumWidth(320)
        lay.addWidget(line)

        caps = QLabel(
            "World Building\n"
            "Parallel Chapter Generation\n"
            "Quality Review & Auto Revision\n"
            "Multi-Platform Export"
        )
        caps.setFont(QFont("Inter", 13))
        caps.setStyleSheet(
            f"color: {dt.TEXT_SECONDARY}; line-height: 2.0; margin-top:4px;")
        caps.setWordWrap(True)
        lay.addWidget(caps)
