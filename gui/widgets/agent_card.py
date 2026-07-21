"""
Agent Card — Apple Light 风格
纯白底 + 轻投影 · 名字 + 角色 + 微进度条 · 动态状态色
"""

from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from assets import design_tokens as dt


class AgentCard(QFrame):
    """Apple 风格 Agent 状态卡片 — 纯白底 + 轻投影。"""

    STATUS = {
        "idle":    ("#AEAEB2", "空闲"),
        "running": ("#007AFF", "运行中"),
        "success": ("#34C759", "完成"),
        "error":   ("#FF3B30", "出错"),
        "waiting": ("#FF9F0A", "等待"),
    }

    def __init__(self, name: str, role: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.role = role
        self._status = "idle"
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(210, 110)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        # Apple 轻投影
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)

        # 白底 + 细边框
        self.setStyleSheet(f"""
            AgentCard {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {dt.RADIUS_LG}px;
            }}
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(14, 12, 14, 12)

        top = QHBoxLayout()
        top.setSpacing(6)

        self.name_label = QLabel(self.name)
        self.name_label.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.name_label.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        top.addWidget(self.name_label)
        top.addStretch()

        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(f"background: {dt.AGENT_IDLE}; border-radius: 4px;")
        top.addWidget(self.dot)
        layout.addLayout(top)

        self.role_label = QLabel(self.role)
        self.role_label.setFont(QFont("Inter", 10))
        self.role_label.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        self.role_label.setFixedHeight(16)
        layout.addWidget(self.role_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(4)
        self.bar.setStyleSheet(self._bar_style(dt.AGENT_IDLE))
        layout.addWidget(self.bar)

        self.status_label = QLabel("空闲")
        self.status_label.setFont(QFont("Inter", 9))
        self.status_label.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        layout.addWidget(self.status_label)

    def _bar_style(self, color: str) -> str:
        return f"""
            QProgressBar {{
                border: none;
                border-radius: 999px;
                background: {dt.BORDER_LIGHT};
            }}
            QProgressBar::chunk {{
                border-radius: 999px;
                background: {color};
            }}
        """

    def set_status(self, status: str):
        self._status = status
        if status in self.STATUS:
            color, text = self.STATUS[status]
            self.dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            self.bar.setStyleSheet(self._bar_style(color))
            self.status_label.setText(text)
            self.status_label.setStyleSheet(f"color: {color};")

    def set_progress(self, value: int):
        self.bar.setValue(max(0, min(100, value)))

    def update_log(self, message: str):
        display = message if len(message) <= 30 else message[:30] + "..."
        self.status_label.setText(display)
        color = self.STATUS.get(self._status, (dt.AGENT_IDLE, ""))[0]
        self.status_label.setStyleSheet(f"color: {color};")

    def reset(self):
        self.set_status("idle")
        self.set_progress(0)
        self.status_label.setText("空闲")
