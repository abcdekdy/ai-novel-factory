"""
日志控制台 — Apple Light 风格
浅灰底 + 细边框 · 等宽字体 · 彩色来源标签
"""

from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QFrame
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QFont
import time

from assets import design_tokens as dt


# 模块级日志源颜色表
_LOG_COLORS = {
    "Pipeline":   "#007AFF",
    "World":      "#AF52DE",
    "Chapter":    "#34C759",
    "Quality":    "#FF9F0A",
    "Revision":   "#FF3B30",
    "Adaptation": "#6E6E73",
    "DEFAULT":    "#8E8E93",
}


class LogConsole(QFrame):
    """Apple 风格日志控制台 — 浅灰底 + 细边框。"""

    COLORS = {
        "Pipeline":   "#007AFF",
        "World":      "#AF52DE",
        "Chapter":    "#34C759",
        "Quality":    "#FF9F0A",
        "Revision":   "#FF3B30",
        "Adaptation": "#6E6E73",
        "DEFAULT":    "#8E8E93",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            LogConsole {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER};
                border-radius: {dt.RADIUS_MD}px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(0)

        self._edit = _LogTextEdit(self)
        lay.addWidget(self._edit)

    def append_log(self, source: str, message: str):
        self._edit.append_log(source, message)

    def clear(self):
        self._edit.clear()


class _LogTextEdit(QTextEdit):
    """实际可编辑文本内含于 LogConsole。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("SF Mono", 10))
        self.setMinimumHeight(180)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {dt.TEXT_PRIMARY};
                border: none;
                padding: 4px;
            }}
        """)
        self._max_lines = 3000

    def append_log(self, source: str, message: str):
        timestamp = time.strftime("%H:%M:%S")
        color = self._get_color(source)
        html = (
            f'<span style="color:{dt.TEXT_DISABLED};font-size:9px">[{timestamp}]</span> '
            f'<span style="color:{color};font-weight:600;font-size:10px">[{source}]</span> '
            f'<span style="color:{dt.TEXT_SECONDARY};font-size:10px">{self._escape(message)}</span>'
        )
        self.append(html)
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        if self.document().blockCount() > self._max_lines:
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()

    def _get_color(self, source: str) -> str:
        for key, color in _LOG_COLORS.items():
            if key in source:
                return color
        return _LOG_COLORS["DEFAULT"]

    def _escape(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
