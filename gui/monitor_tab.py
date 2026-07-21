"""
Monitor Tab — Apple Light Style
白底指标卡 · 浅灰流水线面板 · Apple 系统阶段色
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QGridLayout, QPushButton,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt, QTimer
from PyQt6.QtGui import QFont, QCursor, QColor

from assets import design_tokens as dt


class StatTile(QFrame):
    """Apple 风格指标卡 — 白底 + 轻投影。"""

    def __init__(self, label: str, value: str = "—"):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(96)

        # 轻投影
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)

        self.setStyleSheet(f"""
            StatTile {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {dt.RADIUS_LG}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(16, 14, 16, 14)

        self.val_label = QLabel(value)
        self.val_label.setFont(QFont("Inter", 22, QFont.Weight.Bold))
        self.val_label.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; background: transparent; border: none;")
        layout.addWidget(self.val_label)

        lbl = QLabel(label)
        lbl.setFont(QFont("Inter", 11))
        lbl.setStyleSheet(
            f"color: {dt.TEXT_MUTED}; background: transparent; border: none;")
        layout.addWidget(lbl)

    def set_value(self, text: str):
        self.val_label.setText(text)


class MonitorTab(QWidget):
    """Pipeline dashboard — Apple light style, no web engine."""

    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_status)
        self._timer.start(3000)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(36, 32, 36, 28)

        # Header
        header = QHBoxLayout()
        title = QLabel("监控面板")
        title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        header.addWidget(title)
        header.addStretch()
        self.status_badge = QLabel("空闲")
        self.status_badge.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.status_badge.setFixedHeight(28)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setStyleSheet(self._badge_css(False))
        header.addWidget(self.status_badge)
        layout.addLayout(header)

        # Stat tiles
        tiles_grid = QGridLayout()
        tiles_grid.setSpacing(14)
        tiles_grid.setContentsMargins(0, 0, 0, 0)

        self.tile_progress = StatTile("整体进度", "0%")
        self.tile_chapters = StatTile("章节数", "0")
        self.tile_completed = StatTile("已完成", "0")
        self.tile_stage = StatTile("当前阶段", "—")

        tiles_grid.addWidget(self.tile_progress, 0, 0)
        tiles_grid.addWidget(self.tile_chapters, 0, 1)
        tiles_grid.addWidget(self.tile_completed, 0, 2)
        tiles_grid.addWidget(self.tile_stage, 0, 3)
        layout.addLayout(tiles_grid)

        # Progress panel — Apple 白面卡片
        progress_frame = _AppleContainer(radius=14, parent=self)
        pf = progress_frame.inner_layout()
        pf.setSpacing(8)

        prog_header = QHBoxLayout()
        prog_lbl = QLabel("流水线进度")
        prog_lbl.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        prog_lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        prog_header.addWidget(prog_lbl)
        prog_header.addStretch()
        self.prog_text = QLabel("等待启动")
        self.prog_text.setFont(QFont("Inter", 12))
        self.prog_text.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        prog_header.addWidget(self.prog_text)
        pf.addLayout(prog_header)

        self.pipeline_progress = QProgressBar()
        self.pipeline_progress.setRange(0, 100)
        self.pipeline_progress.setValue(0)
        self.pipeline_progress.setTextVisible(False)
        self.pipeline_progress.setFixedHeight(6)
        pf.addWidget(self.pipeline_progress)
        layout.addWidget(progress_frame)

        # Stage indicators — Apple 浅灰凹陷
        stages_frame = _AppleInset(radius=12, parent=self)
        sf = stages_frame.inner_layout()

        stage_title = QLabel("阶段详情")
        stage_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        stage_title.setStyleSheet(
            f"color: {dt.TEXT_SECONDARY}; margin-bottom: 4px;")
        sf.addWidget(stage_title)

        self.stage_indicators = {}
        stages = [
            ("world_building", "世界观构建"),
            ("outline_generation", "大纲生成"),
            ("chapter_generation", "章节生成"),
            ("quality_evaluation", "质量评估"),
            ("revision", "回流修订"),
            ("adaptation", "平台适配"),
        ]
        for key, label in stages:
            row = QHBoxLayout()
            row.setSpacing(10)
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(
                f"background: {dt.BORDER}; border-radius: 5px;")
            row.addWidget(dot)
            lbl = QLabel(label)
            lbl.setFont(QFont("Inter", 12))
            lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
            row.addWidget(lbl)
            row.addStretch()
            status_lbl = QLabel("等待")
            status_lbl.setFont(QFont("Inter", 11))
            status_lbl.setStyleSheet(f"color: {dt.TEXT_DISABLED};")
            row.addWidget(status_lbl)
            sf.addLayout(row)
            self.stage_indicators[key] = (dot, status_lbl)

        layout.addWidget(stages_frame)
        layout.addStretch()

    def _badge_css(self, running: bool):
        if running:
            return (
                f"color: {dt.TEXT_INVERSE};"
                f"background: {dt.ACCENT};"
                f"border-radius: 14px;"
                f"padding: 2px 14px;"
                f"font-weight: 600; font-size: 11px;"
            )
        return (
            f"color: {dt.TEXT_MUTED};"
            f"background: {dt.BG_PRESSED};"
            f"border-radius: 14px;"
            f"padding: 2px 14px;"
            f"font-weight: 600; font-size: 11px;"
        )

    def _poll_status(self):
        import urllib.request, json
        try:
            resp = urllib.request.urlopen(
                "http://127.0.0.1:5000/api/status", timeout=2)
            data = json.loads(resp.read().decode())
            self._update_ui(data)
        except Exception:
            pass

    def _update_ui(self, data: dict):
        progress = data.get("overall_progress", 0)
        self.tile_progress.set_value(f"{progress}%")
        self.tile_chapters.set_value(str(data.get("total_chapters", 0)))
        self.tile_completed.set_value(str(data.get("completed_chapters", 0)))

        stage = data.get("current_stage", "idle")
        stage_names = {
            "idle": "空闲", "world_building": "世界观构建",
            "outline_generation": "大纲生成",
            "chapter_generation": "章节生成",
            "quality_evaluation": "质量评估",
            "revision": "回流修订", "adaptation": "平台适配",
            "completed": "已完成",
        }
        stage_name = stage_names.get(stage, stage)
        self.tile_stage.set_value(stage_name)

        running = data.get("is_running")
        self.status_badge.setText("运行中" if running else "空闲")
        self.status_badge.setStyleSheet(self._badge_css(running))

        self.pipeline_progress.setValue(progress)
        title = data.get("title", "")
        self.prog_text.setText(title if title else "等待启动")

        stage_order = ["world_building", "outline_generation", "chapter_generation",
                       "quality_evaluation", "revision", "adaptation"]
        current_idx = stage_order.index(stage) if stage in stage_order else -1
        for i, key in enumerate(stage_order):
            dot, lbl = self.stage_indicators[key]
            if stage == "completed" or i < current_idx:
                dot.setStyleSheet(
                    f"background: {dt.SUCCESS}; border-radius: 5px;")
                lbl.setText("完成")
                lbl.setStyleSheet(
                    f"color: {dt.SUCCESS}; font-weight: 600;")
            elif i == current_idx:
                dot.setStyleSheet(
                    f"background: {dt.ACCENT}; border-radius: 5px;")
                lbl.setText("进行中")
                lbl.setStyleSheet(
                    f"color: {dt.ACCENT}; font-weight: 600;")
            else:
                dot.setStyleSheet(
                    f"background: {dt.BORDER}; border-radius: 5px;")
                lbl.setText("等待")
                lbl.setStyleSheet(f"color: {dt.TEXT_DISABLED};")


# ---------- helper containers (本地定义避免 import 循环) ----------
class _AppleContainer(QFrame):
    """Apple 风格凸面容器 — 白底 + 轻投影 + inner_layout。"""
    def __init__(self, radius=14, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)
        self.setStyleSheet(f"""
            _AppleContainer {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {radius}px;
            }}
        """)
        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(16, 16, 16, 16)
        self._inner.setSpacing(0)

    def inner_layout(self): return self._inner


class _AppleInset(QFrame):
    """Apple 风格凹陷容器 — 浅灰底 + 细边框 + inner_layout。"""
    def __init__(self, radius=12, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _AppleInset {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER};
                border-radius: {radius}px;
            }}
        """)
        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(16, 16, 16, 16)
        self._inner.setSpacing(0)

    def inner_layout(self): return self._inner
