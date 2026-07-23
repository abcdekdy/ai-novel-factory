"""
Workspace Tab — Apple Light Style
Agent cards grid (白底轻投影) inside a 白面卡片 · live log in 浅灰凹陷.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QGridLayout, QScrollArea,
    QPushButton, QFrame, QSizePolicy
)
from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QFont, QCursor

from gui.widgets.agent_card import AgentCard
from gui.widgets.log_console import LogConsole
from gui.widgets.neumorphism import AppleCard, AppleInset
from assets import design_tokens as dt


class AgentsTab(QWidget):
    """Agent workspace — Apple card grid + live logs."""

    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self._setup_ui()
        self.pipeline.signals.stage_started.connect(self._on_stage_started)
        self.pipeline.signals.pipeline_finished.connect(self._on_pipeline_finished)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(36, 32, 36, 28)

        # ===== Header (title + progress) =====
        header = QHBoxLayout()
        header.setSpacing(16)

        title = QLabel("工作台")
        title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        header.addWidget(title)
        header.addStretch()

        self.pause_btn = QPushButton("暂停并保存")
        self.pause_btn.setFixedSize(112, 36)
        self.pause_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.pause_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.pause_btn.setEnabled(False)
        self.pause_btn.setStyleSheet(f"""
            QPushButton {{
                background: {dt.BG_PRESSED}; color: {dt.TEXT_PRIMARY};
                border: 1px solid {dt.BORDER}; border-radius: 10px; padding: 2px 12px;
            }}
            QPushButton:hover {{ background: {dt.BORDER_LIGHT}; color: {dt.ACCENT}; }}
            QPushButton:disabled {{ background: {dt.BG_INPUT}; color: {dt.TEXT_DISABLED}; border: 1px solid {dt.BORDER_LIGHT}; }}
        """)
        self.pause_btn.clicked.connect(self._request_pause)
        header.addWidget(self.pause_btn)

        prog_box = QVBoxLayout()
        prog_box.setSpacing(4)
        p_top = QHBoxLayout()
        p_top.addWidget(QLabel("进度"))
        self.overall_label = QLabel("0%")
        self.overall_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.overall_label.setStyleSheet(f"color: {dt.ACCENT};")
        p_top.addWidget(self.overall_label)
        p_top.addStretch()
        prog_box.addLayout(p_top)

        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setTextVisible(False)
        self.overall_progress.setFixedHeight(6)
        prog_box.addWidget(self.overall_progress)

        header.addLayout(prog_box)
        header.setStretchFactor(prog_box, 2)
        layout.addLayout(header)

        # ===== Agent Cards — Apple 白面卡片 =====
        cards_frame = AppleCard(radius=14, parent=self)
        cards_layout = cards_frame.content_layout()
        cards_layout.setSpacing(12)

        cards_title = QLabel("Agent 状态")
        cards_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        cards_title.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        cards_layout.addWidget(cards_title)

        # 卡片会随着章节数动态增加。使用固定高度的滚动区，避免卡片区域
        # 把日志挤出界面或让底部卡片被父容器裁切。
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cards_scroll.setMinimumHeight(270)
        self.cards_scroll.setMaximumHeight(390)
        self.cards_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 8px 0;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #C7C7CC; min-height: 40px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover { background: #AEAEB2; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        grid_wrap = QWidget()
        grid_wrap.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Minimum)
        self.cards_grid = QGridLayout(grid_wrap)
        self.cards_grid.setContentsMargins(8, 8, 16, 8)
        self.cards_grid.setHorizontalSpacing(18)
        self.cards_grid.setVerticalSpacing(20)
        self.cards_grid.setAlignment(Qt.AlignmentFlag.AlignTop |
                                     Qt.AlignmentFlag.AlignHCenter)

        self.agent_cards = {}
        fixed = [
            ("大纲生成", "生成统一章节大纲，确保前后一致"),
            ("世界观构建", "构建世界观与人物设定"),
            ("章节生成", "并行生成章节内容"),
            ("质量评估", "评分与问题检测"),
            ("回流修订", "自动修改未达标章节"),
            ("平台适配", "格式转换与导出"),
        ]
        for i, (name, role) in enumerate(fixed):
            card = AgentCard(name, role)
            self.cards_grid.addWidget(card, i // 3, i % 3)
            self.agent_cards[name] = card

        self.cards_scroll.setWidget(grid_wrap)
        cards_layout.addWidget(self.cards_scroll)
        layout.addWidget(cards_frame)

        # ===== Log Stream — Apple 浅灰凹陷内含 LogConsole =====
        log_frame = AppleInset(radius=12, parent=self)
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(14, 14, 14, 14)
        log_layout.setSpacing(0)

        log_header = QHBoxLayout()
        log_title = QLabel("运行日志")
        log_title.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        log_title.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        log_header.addWidget(log_title)
        log_header.addStretch()

        clear_btn = QPushButton("清空")
        clear_btn.clicked.connect(lambda: self.log_console.clear())
        clear_btn.setFixedSize(56, 28)
        clear_btn.setFont(QFont("Inter", 11))
        clear_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        clear_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {dt.TEXT_MUTED};
                border: none;
                border-radius: 8px;
            }}
            QPushButton:hover {{ color: {dt.ACCENT}; background: {dt.BG_RAISED}; }}
        """)
        log_header.addWidget(clear_btn)
        log_layout.addLayout(log_header)

        self.log_console = LogConsole()
        log_layout.addWidget(self.log_console)
        layout.addWidget(log_frame)
        layout.setStretchFactor(log_frame, 1)

    @pyqtSlot(int)
    def update_overall_progress(self, value: int):
        self.overall_progress.setValue(value)
        self.overall_label.setText(f"{value}%")

    @pyqtSlot(str)
    def _on_stage_started(self, _stage: str):
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("暂停并保存")

    @pyqtSlot(dict)
    def _on_pipeline_finished(self, result: dict):
        self.pause_btn.setEnabled(False)
        self.pause_btn.setText("已暂停" if result.get("paused") else "暂停并保存")

    def _request_pause(self):
        if self.pipeline.pause_and_save():
            self.pause_btn.setEnabled(False)
            self.pause_btn.setText("暂停中...")

    @pyqtSlot(str, str)
    def append_log(self, source: str, message: str):
        self.log_console.append_log(source, message)

    @pyqtSlot(str, str)
    def update_agent_log(self, agent_name: str, message: str):
        if agent_name.startswith("章节生成-"):
            if agent_name not in self.agent_cards:
                card = AgentCard(agent_name, "生成章节")
                idx = len(self.agent_cards)
                self.cards_grid.addWidget(card, idx // 3, idx % 3)
                self.agent_cards[agent_name] = card
            card = self.agent_cards[agent_name]
            card.update_log(message)
            self._update_status(card, message)
            return

        for cname, card in self.agent_cards.items():
            if agent_name.startswith(cname) or cname.startswith(agent_name.split("-")[0]):
                card.update_log(message)
                self._update_status(card, message)
                return

    def _update_status(self, card, msg: str):
        if "完成" in msg or "成功" in msg:
            card.set_status("success")
        elif "失败" in msg or "错误" in msg:
            card.set_status("error")
        elif "开始" in msg or "正在" in msg or "调用" in msg:
            card.set_status("running")

    @pyqtSlot(dict)
    def on_world_view_ready(self, world_view: dict):
        card = self.agent_cards.get("世界观构建")
        if card:
            card.set_status("success")
            card.set_progress(100)

    @pyqtSlot(dict)
    def on_chapter_complete(self, chapter_data: dict):
        pass


