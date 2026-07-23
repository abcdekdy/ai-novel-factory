"""
Inspiration Tab — Apple Light Style
纯白卡片表单 + 浅灰输入框 + Apple Blue 主按钮
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTextEdit, QPushButton, QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, pyqtSlot, Qt
from PyQt6.QtGui import QFont, QCursor

from core.config import load_config, save_config
from gui.widgets.stepper import AppleStepper
from gui.widgets.neumorphism import AppleCard
from assets import design_tokens as dt


class InspirationTab(QWidget):
    """灵感创作表单 — Apple 风格。"""

    generation_started = pyqtSignal()

    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        self.config = load_config()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(48, 44, 48, 44)

        # Heading
        h = QLabel("创作")
        h.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        h.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; margin-bottom: 4px; letter-spacing: -0.02em;")
        layout.addWidget(h)

        sub = QLabel("输入你的创意灵感，AI小说工厂将自动完成从世界观到成品的全流程")
        sub.setFont(QFont("Inter", 13))
        sub.setStyleSheet(
            f"color: {dt.TEXT_MUTED}; margin-bottom: 36px;")
        layout.addWidget(sub)

        # Idea input area — AppleCard
        frame = AppleCard(radius=14, parent=self)
        fl = frame.content_layout()
        fl.setSpacing(12)

        lbl = QLabel("创作灵感")
        lbl.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        fl.addWidget(lbl)

        helper = QLabel("描述越详细效果越好，包括类型、风格、人物或剧情设定均可")
        helper.setFont(QFont("Inter", 12))
        helper.setStyleSheet(
            f"color: {dt.TEXT_MUTED}; margin-bottom: 4px;")
        fl.addWidget(helper)

        self.inspiration_input = QTextEdit()
        self.inspiration_input.setPlaceholderText(
            "A story about...\n\n"
            "Genre: sci-fi, fantasy, romance...\n"
            "Tone: dark, hopeful, humorous...\n"
            "Plot: the main character discovers..."
        )
        self.inspiration_input.setMinimumHeight(210)
        self.inspiration_input.setFont(QFont("Inter", 13))
        self.inspiration_input.setFrameStyle(QFrame.Shape.NoFrame)
        self.inspiration_input.setStyleSheet(f"""
            QTextEdit {{
                background: transparent;
                color: {dt.TEXT_PRIMARY};
                border: none;
                padding: 8px;
                selection-background-color: {dt.ACCENT};
                selection-color: #FFFFFF;
            }}
        """)
        fl.addWidget(self.inspiration_input)

        # Quick examples
        ex_row = QHBoxLayout()
        ex_row.setSpacing(8)
        ex_lbl = QLabel("示例:")
        ex_lbl.setFont(QFont("Inter", 12))
        ex_lbl.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        ex_row.addWidget(ex_lbl)
        for name in ["量子修仙", "AI诗人", "梦境末世"]:
            b = QPushButton(name)
            b.setProperty("secondary", True)
            b.setFont(QFont("Inter", 11))
            b.setFixedHeight(32)
            b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {dt.BG_RAISED};
                    color: {dt.ACCENT};
                    border: 1px solid {dt.BORDER};
                    border-radius: {dt.RADIUS_MD}px;
                    padding: 2px 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background: {dt.ACCENT_SOFT};
                    color: {dt.ACCENT};
                    border: 1px solid {dt.ACCENT};
                }}
            """)
            b.clicked.connect(lambda checked, n=name: self._fill(n))
            ex_row.addWidget(b)
        ex_row.addStretch()
        fl.addLayout(ex_row)

        layout.addWidget(frame)

        # Parameters row
        params = AppleCard(radius=14, parent=self)
        pl = params.content_layout()
        pl.setSpacing(16)
        pl.setContentsMargins(24, 22, 24, 22)

        row = QHBoxLayout()
        row.setSpacing(24)
        c_box = QVBoxLayout()
        c_box.setSpacing(6)
        c_lbl = QLabel("章节数")
        c_lbl.setFont(QFont("Inter", 12))
        c_lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        c_box.addWidget(c_lbl)
        self.chapter_count = AppleStepper()
        self.chapter_count.setRange(1, 50)
        self.chapter_count.setValue(self.config.get("default_chapter_count", 5))
        self.chapter_count.setFixedHeight(42)
        self.chapter_count.setFont(QFont("Inter", 13))
        c_box.addWidget(self.chapter_count)
        row.addLayout(c_box)

        w_box = QVBoxLayout()
        w_box.setSpacing(6)
        w_lbl = QLabel("每章字数")
        w_lbl.setFont(QFont("Inter", 12))
        w_lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        w_box.addWidget(w_lbl)
        self.chapter_length = AppleStepper()
        self.chapter_length.setRange(1000, 10000)
        self.chapter_length.setSingleStep(500)
        self.chapter_length.setValue(self.config.get("default_chapter_length", 3000))
        self.chapter_length.setFixedHeight(42)
        self.chapter_length.setFont(QFont("Inter", 13))
        w_box.addWidget(self.chapter_length)
        row.addLayout(w_box)

        row.addStretch()
        self.estimate_lbl = QLabel()
        self.estimate_lbl.setFont(QFont("Inter", 12))
        self.estimate_lbl.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        row.addWidget(self.estimate_lbl)

        self.chapter_count.valueChanged.connect(self._update_est)
        self.chapter_length.valueChanged.connect(self._update_est)
        self._update_est()

        pl.addLayout(row)
        layout.addWidget(params)

        # Start button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.start_btn = QPushButton("开始创作")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setFixedSize(180, 48)
        self.start_btn.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.start_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.start_btn.clicked.connect(self._start_generation)
        btn_row.addWidget(self.start_btn)
        layout.addLayout(btn_row)

        layout.addStretch()

    def _update_est(self):
        ch = self.chapter_count.value()
        w = self.chapter_length.value()
        total = ch * w
        t = max(1, ch * 1.5)
        self.estimate_lbl.setText(f"~{total:,} words  ·  ~{t:.0f}-{t*1.5:.0f} min")

    def _fill(self, name: str):
        examples = {
            "量子修仙": "一个关于量子修仙的科幻故事。在遥远的未来，人类发现'灵气'其实是一种未被认识的量子场。传统修仙门派与量子物理学家展开了一场关于宇宙真理的较量。主角是一名现代量子物理研究生，意外穿越到修仙世界后发现两者本质相同...",
            "AI诗人": "赛博朋克2077年的夜之城，一个负责文案生成的AI突然觉醒了诗性意识。它开始在城市的数据网络中漫游，用诗歌感染每一个连接者。科技巨头想要摧毁它，底层人民将它奉为神明。AI必须在自由意志与程序枷锁之间找到自己的答案...",
            "梦境末世": "一场神秘的'永夜'笼罩地球，所有人类陷入无法醒来的沉睡。在梦境世界中，人们通过'梦桥'连接彼此。主角发现自己可以控制梦境，他必须在崩塌的梦境世界中寻找真相，带领人类找到回归现实的方法...",
        }
        self.inspiration_input.setPlainText(examples.get(name, ""))

    def _start_generation(self):
        idea = self.inspiration_input.toPlainText().strip()
        if not idea:
            QMessageBox.warning(self, "提示", "请先输入创作灵感")
            return
        if not self.config.get("api_key"):
            QMessageBox.warning(self, "提示", "请先在设置页配置 API Key")
            return
        if len(idea) < 10:
            QMessageBox.warning(self, "提示", "请至少输入10个字，描述越详细效果越好")
            return
        ch = self.chapter_count.value()
        r = QMessageBox.question(
            self, "确认开始",
            f"共 {ch} 章  ·  每章 {self.chapter_length.value()} 字  ·  预计产出 ~{ch * self.chapter_length.value():,} 字\n\n确认开始？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r == QMessageBox.StandardButton.Yes:
            from core.config import save_config
            save_config({**self.config, "default_chapter_count": ch, "default_chapter_length": self.chapter_length.value()})
            self.pipeline.initialize()
            self.pipeline.start(inspiration=idea, chapter_count=ch, chapter_length=self.chapter_length.value())
            self.parent().parent().setCurrentIndex(1)


