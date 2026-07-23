"""
Settings Tab — Apple Light Style
白底设置卡片 · 浅灰输入控件 · Apple Blue 保存按钮
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox,
    QGroupBox, QFormLayout, QSlider, QMessageBox,
    QGraphicsDropShadowEffect, QFrame, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QCursor, QColor, QPainter

from core.config import load_config, save_config
from core.llm_client import test_connection
from gui.widgets.stepper import AppleStepper
from assets import design_tokens as dt


class SettingsTab(QWidget):
    """设置页 — Apple 风格。"""

    config_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        # 顶层布局：滚动区（占满）+ 保存按钮（固定底部）
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(30, 20, 30, 20)

        # ---- 标题（滚动区外，始终可见）----
        title = QLabel("Settings")
        title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        outer.addWidget(title)

        # ---- 滚动区：包含所有设置卡片 ----
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 8px 0;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #C7C7CC; min-height: 40px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover { background: #AEAEB2; }
        """)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 0, 0)
        # 注意：不要在滚动区内容里加 stretch，否则 setWidgetResizable(True)
        # 会导致内容无限撑大。卡片靠上排列，超出视口时滚动条出现。
        self.scroll_area.setWidget(scroll_content)
        outer.addWidget(self.scroll_area, 1)   # 占满剩余空间

        # ===== API配置组 (白面卡片) =====
        api_group = _AppleSettingsPanel(title="API Configuration")
        api_layout = api_group.form_layout()

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("输入 API Key (sk-...)")
        self.api_key_input.setMinimumWidth(400)
        api_layout.addRow("API Key:", self.api_key_input)

        test_btn_layout = QHBoxLayout()
        self.test_btn = QPushButton("测试连接")
        self.test_btn.clicked.connect(self._test_connection)
        self.test_btn.setFixedWidth(120)
        self.test_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.test_btn.setStyleSheet(f"""
            QPushButton {{
                background: {dt.ACCENT};
                color: {dt.TEXT_INVERSE};
                border: none;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }}
            QPushButton:pressed {{ background: {dt.ACCENT_DIM}; }}
            QPushButton:disabled {{ background: {dt.TEXT_DISABLED}; color: {dt.TEXT_INVERSE}; }}
        """)
        self.connection_status = QLabel("")
        test_btn_layout.addWidget(self.test_btn)
        test_btn_layout.addWidget(self.connection_status)
        test_btn_layout.addStretch()
        api_layout.addRow("", test_btn_layout)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["longcat", "deepseek"])
        self.provider_combo.currentTextChanged.connect(
            self._on_provider_changed)
        api_layout.addRow("服务商:", self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["LongCat-Flash-Chat"])
        api_layout.addRow("模型:", self.model_combo)

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText(
            "默认: https://api.longcat.chat/anthropic")
        api_layout.addRow("Base URL:", self.base_url_input)

        api_group.finalize()
        layout.addWidget(api_group)

        # ===== 生成参数组 (白面卡片) =====
        gen_group = _AppleSettingsPanel(title="Generation Parameters")
        gen_layout = gen_group.form_layout()

        temp_layout = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(0, 20)
        self.temp_slider.setValue(8)
        self.temp_value = QLabel("0.8")
        self.temp_slider.valueChanged.connect(
            lambda v: self.temp_value.setText(f"{v/10:.1f}"))
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_value)
        gen_layout.addRow("创意温度:", temp_layout)

        self.concurrency_spin = AppleStepper()
        self.concurrency_spin.setRange(1, 8)
        self.concurrency_spin.setValue(3)
        self.concurrency_spin.setSuffix(" 线程")
        gen_layout.addRow("并发数:", self.concurrency_spin)

        self.revision_spin = AppleStepper()
        self.revision_spin.setRange(1, 5)
        self.revision_spin.setValue(3)
        self.revision_spin.setSuffix(" 轮")
        gen_layout.addRow("最大修订轮数:", self.revision_spin)

        threshold_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(50, 95)
        self.threshold_slider.setValue(70)
        self.threshold_value = QLabel("7.0")
        self.threshold_slider.valueChanged.connect(
            lambda v: self.threshold_value.setText(f"{v/10:.1f}"))
        threshold_layout.addWidget(self.threshold_slider)
        threshold_layout.addWidget(self.threshold_value)
        gen_layout.addRow("通过阈值:", threshold_layout)

        self.chapter_count_spin = AppleStepper()
        self.chapter_count_spin.setRange(1, 50)
        self.chapter_count_spin.setValue(5)
        self.chapter_count_spin.setSuffix(" 章")
        gen_layout.addRow("默认章节数:", self.chapter_count_spin)

        self.chapter_length_spin = AppleStepper()
        self.chapter_length_spin.setRange(1000, 10000)
        self.chapter_length_spin.setSingleStep(500)
        self.chapter_length_spin.setValue(3000)
        self.chapter_length_spin.setSuffix(" 字")
        gen_layout.addRow("默认每章字数:", self.chapter_length_spin)

        gen_group.finalize()
        layout.addWidget(gen_group)

        # ===== Web监控组 (白面卡片) =====
        web_group = _AppleSettingsPanel(title="Web Monitor")
        web_layout = web_group.form_layout()
        self.port_spin = AppleStepper()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(5000)
        web_layout.addRow("监控端口:", self.port_spin)
        web_group.finalize()
        layout.addWidget(web_group)

        # ===== 外观组（主题切换）=====
        appearance_group = _AppleSettingsPanel(title="Appearance")
        appearance_layout = appearance_group.form_layout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        appearance_layout.addRow("Theme:", self.theme_combo)
        appearance_group.finalize()
        layout.addWidget(appearance_group)

        # ===== 保存按钮（滚动区外，固定在底部）=====
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton("Save Settings")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.setFixedWidth(160)
        self.save_btn.clicked.connect(self._save_settings)
        save_layout.addWidget(self.save_btn)
        outer.addLayout(save_layout)

    def _on_provider_changed(self, provider: str):
        if provider == "longcat":
            self.model_combo.clear()
            self.model_combo.addItems(["LongCat-2.0"])
            self.base_url_input.setText(
                "https://api.longcat.chat/anthropic")
        elif provider == "deepseek":
            self.model_combo.clear()
            self.model_combo.addItems(["deepseek-chat", "deepseek-reasoner"])
            self.base_url_input.setText("https://api.deepseek.com/v1")

    def _load_values(self):
        self.api_key_input.setText(self.config.get("api_key", ""))
        self.api_key_input.setCursorPosition(0)

        provider = self.config.get("provider", "longcat")
        idx = self.provider_combo.findText(provider)
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

        model = self.config.get("model", "LongCat-Flash-Chat")
        self._on_provider_changed(provider)
        idx = self.model_combo.findText(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        base_url = self.config.get("base_url", "")
        if base_url:
            self.base_url_input.setText(base_url)
            # 让 URL 尾部可见（方便用户确认完整域名）
            self.base_url_input.setCursorPosition(len(base_url))

        temp = self.config.get("temperature", 0.8)
        self.temp_slider.setValue(int(temp * 10))
        self.temp_value.setText(f"{temp:.1f}")

        self.concurrency_spin.setValue(self.config.get("concurrency", 3))
        self.revision_spin.setValue(
            self.config.get("max_revision_rounds", 3))

        threshold = self.config.get("quality_threshold", 7.0)
        self.threshold_slider.setValue(int(threshold * 10))
        self.threshold_value.setText(f"{threshold:.1f}")

        self.chapter_count_spin.setValue(
            self.config.get("default_chapter_count", 5))
        self.chapter_length_spin.setValue(
            self.config.get("default_chapter_length", 3000))
        self.port_spin.setValue(self.config.get("web_monitor_port", 5000))

        theme = self.config.get("theme", "light")
        idx = self.theme_combo.findText(theme.capitalize())
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)

    def _save_settings(self):
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["provider"] = self.provider_combo.currentText()
        self.config["model"] = self.model_combo.currentText()
        self.config["base_url"] = self.base_url_input.text().strip()
        self.config["temperature"] = self.temp_slider.value() / 10
        self.config["concurrency"] = self.concurrency_spin.value()
        self.config["max_revision_rounds"] = self.revision_spin.value()
        self.config["quality_threshold"] = self.threshold_slider.value() / 10
        self.config["default_chapter_count"] = self.chapter_count_spin.value()
        self.config["default_chapter_length"] = self.chapter_length_spin.value()
        self.config["web_monitor_port"] = self.port_spin.value()
        self.config["theme"] = self.theme_combo.currentText().lower()

        save_config(self.config)
        self.config_changed.emit()
        QMessageBox.information(self, "保存成功", "设置已保存！")

    def _test_connection(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "提示", "请先输入API Key")
            return

        provider = self.provider_combo.currentText()
        base_url = self.base_url_input.text().strip() or None

        self.connection_status.setText("测试中...")
        self.connection_status.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        self.test_btn.setEnabled(False)

        from PyQt6.QtCore import QThread

        class TestThread(QThread):
            result_ready = pyqtSignal(bool, str)

            def __init__(self, key, prov, url):
                super().__init__()
                self.key = key
                self.prov = prov
                self.url = url

            def run(self):
                success, msg = test_connection(
                    self.key, provider=self.prov, base_url=self.url)
                self.result_ready.emit(success, msg)

        self._test_thread = TestThread(api_key, provider, base_url)
        self._test_thread.result_ready.connect(self._on_test_result)
        self._test_thread.start()

    def _on_test_result(self, success: bool, message: str):
        self.test_btn.setEnabled(True)
        if success:
            self.connection_status.setText(message)
            self.connection_status.setStyleSheet(f"color: {dt.SUCCESS};")
        else:
            self.connection_status.setText(message)
            self.connection_status.setStyleSheet(f"color: {dt.DANGER};")


class _AppleSettingsPanel(QFrame):
    """Apple 风格设置面板 — 白底 + 轻投影，替代 QGroupBox。提供 form_layout()。
    由 paintEvent 自绘，不依赖 QSS（兼容主题系统）。"""
    def __init__(self, title: str, radius=14, parent=None):
        super().__init__(parent)
        self._radius = radius
        self._title = title

        # 轻投影
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)

        self._main = QVBoxLayout(self)
        self._main.setContentsMargins(18, 14, 18, 14)
        self._main.setSpacing(0)

        # 标题
        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        self._main.addWidget(title_lbl)

        self._blank = QLabel("")
        self._blank.setFixedHeight(6)
        self._main.addWidget(self._blank)

        self._form = QFormLayout()
        self._form.setSpacing(8)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

    def form_layout(self) -> QFormLayout:
        return self._form

    def finalize(self):
        self._main.addLayout(self._form)

    def paintEvent(self, event):
        try:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = self.rect().adjusted(1, 1, -1, -1)
            p.fillRect(rect, QColor(dt.SURFACE))
            border = QColor(dt.BORDER_LIGHT)
            border.setAlphaF(0.5)
            p.setPen(border)
            p.drawRoundedRect(rect, self._radius, self._radius)
        except Exception as e:
            print(f"[_AppleSettingsPanel paintEvent ERROR] {e}")
