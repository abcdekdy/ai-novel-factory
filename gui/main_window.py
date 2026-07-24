"""
Main Window — Apple Light Style
Sidebar uses CLASS-based selectors. Apple Blue accent on light gray.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QStatusBar, QMessageBox, QDialog
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QFont, QCursor, QColor, QPainter
from pathlib import Path

from gui.inspiration_tab import InspirationTab
from gui.agents_tab import AgentsTab
from gui.preview_tab import PreviewTab
from gui.settings_tab import SettingsTab
from gui.projects_tab import ProjectsTab
from core.pipeline import NovelPipeline
from core.config import load_config
from assets import design_tokens as dt


class AppleNavButton(QPushButton):
    """侧边栏导航按钮 — 选中态左侧白色活动竖条。"""
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(40)
        self.setFont(QFont("Inter", 13))
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def paintEvent(self, event):
        try:
            super().paintEvent(event)
            if self.isChecked():
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                # 选中态在蓝色背景上画白色竖条，形成对比
                p.fillRect(0, 8, 3, 24, QColor("#FFFFFF"))
        except Exception as e:
            print(f"[AppleNavButton paintEvent ERROR] {e}")


class Sidebar(QFrame):
    """Sidebar container — QSS targets `Sidebar {}`. Apple light gray."""
    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        rect = self.rect()
        c = QColor(dt.BG_SIDEBAR); p.fillRect(rect, c)
        super().paintEvent(event)


class MainWindow(QMainWindow):
    """Apple light-style sidebar layout."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Novel Factory")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self.config = load_config()
        self.pipeline = NovelPipeline()
        self._setup_ui()
        self._setup_pipeline_signals()
        # 应用主题（light / dark）
        self.apply_theme(self.config.get("theme", "light"))

    def apply_theme(self, theme_name: str):
        """根据主题名生成 QSS 并应用到全局。"""
        theme = dt.THEMES.get(theme_name, dt.THEMES["light"])
        qss = self._generate_qss(theme)
        self.setStyleSheet(qss)
        # 同步更新 Sidebar 背景色
        for w in self.findChildren(Sidebar):
            w.update()

    def _generate_qss(self, theme: dict) -> str:
        """根据主题 token 字典生成完整 QSS 字符串。"""
        a = theme  # 简写
        return f"""
QMainWindow, QDialog {{
    background-color: {a["BG_BASE"]};
    color: {a["TEXT_PRIMARY"]};
    font-family: {dt.FONT_SYSTEM};
}}
* {{ outline: none; }}

Sidebar {{
    background-color: {a["BG_SIDEBAR"]};
    border-right: 1px solid {a["BORDER"]};
}}

AppleNavButton {{
    background: transparent;
    color: {a["TEXT_MUTED"]};
    border: none;
    border-radius: 10px;
    padding: 8px 14px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    margin: 2px 10px;
}}
AppleNavButton:hover {{
    color: {a["TEXT_PRIMARY"]};
    background: {dt.rgba(a["TEXT_PRIMARY"], 0.06)};
    font-weight: 600;
}}
AppleNavButton:checked {{
    color: #FFFFFF;
    font-weight: 600;
    background: {a["ACCENT"]};
}}

QPushButton {{
    background-color: {a["BG_INPUT"]};
    color: {a["TEXT_PRIMARY"]};
    border: 1px solid {a["BORDER"]};
    padding: 6px 16px;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    border-color: {a["ACCENT"]};
    background-color: {dt.rgba(a["ACCENT"], 0.08)};
}}
QPushButton:pressed {{ background-color: {dt.rgba(a["ACCENT"], 0.15)}; }}
QPushButton:disabled {{ color: {a["TEXT_DISABLED"]}; background-color: {a["BG_INPUT"]}; border-color: {a["BORDER"]}; }}

QPushButton#primaryButton {{
    background-color: {a["ACCENT"]};
    color: #FFFFFF;
    border: none;
    padding: 12px 30px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{ background-color: {a["ACCENT_HOVER"]}; }}
QPushButton#primaryButton:pressed {{ background-color: {a["ACCENT_DIM"]}; }}
QPushButton#primaryButton:disabled {{ background-color: {a["BORDER"]}; color: #FFFFFF; }}

QPushButton[secondary="true"] {{
    background-color: {a["BG_INPUT"]};
    color: {a["ACCENT"]};
    border: 1px solid {a["BORDER"]};
    padding: 4px 14px;
    font-weight: 600;
}}
QPushButton[secondary="true"]:hover {{
    background-color: {a["ACCENT_SOFT"]};
    border: 1px solid {a["ACCENT"]};
}}

QTextEdit, QPlainTextEdit, QLineEdit {{
    background-color: {a["SURFACE"]};
    color: {a["TEXT_PRIMARY"]};
    border: 1px solid {a["BORDER"]};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: {a["ACCENT"]};
    selection-color: #FFFFFF;
}}
QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus {{
    border: 1px solid {a["ACCENT"]};
    background-color: {a["SURFACE"]};
}}

QLabel {{ color: {a["TEXT_MUTED"]}; font-size: 13px; }}
QLabel#heading {{ color: {a["TEXT_PRIMARY"]}; font-size: 28px; font-weight: 700; letter-spacing: -0.02em; }}
QLabel#subheading {{ color: {a["TEXT_MUTED"]}; font-size: 13px; }}
QLabel#section {{ color: {a["TEXT_PRIMARY"]}; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }}
QLabel#muted {{ color: {a["TEXT_MUTED"]}; font-size: 12px; }}

QProgressBar {{
    border: none;
    background: {a["BG_INPUT"]};
    border-radius: 999px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {a["ACCENT"]};
    border-radius: 999px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {a["BORDER"]};
    border-radius: 3px;
    min-height: 40px;
}}
QScrollBar::handle:vertical:hover {{ background: {a["TEXT_MUTED"]}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background: transparent;
    height: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:horizontal {{
    background: {a["BORDER"]};
    border-radius: 3px;
    min-width: 40px;
}}
QScrollBar::handle:horizontal:hover {{ background: {a["TEXT_MUTED"]}; }}

QComboBox, QSpinBox {{
    background-color: {a["SURFACE"]};
    color: {a["TEXT_PRIMARY"]};
    border: 1px solid {a["BORDER"]};
    border-radius: 10px;
    padding: 8px 14px;
    font-size: 13px;
}}
QComboBox:hover, QSpinBox:hover {{ border: 1px solid {a["TEXT_MUTED"]}; }}
QComboBox:focus, QSpinBox:focus {{ border: 1px solid {a["ACCENT"]}; }}
QComboBox QAbstractItemView {{
    background: {a["SURFACE"]};
    color: {a["TEXT_PRIMARY"]};
    border: 1px solid {a["BORDER"]};
    border-radius: 10px;
    selection-background-color: {a["ACCENT_SOFT"]};
    selection-color: {a["ACCENT"]};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}

QSlider::groove:horizontal {{
    height: 4px;
    background: {a["BG_INPUT"]};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {a["SURFACE"]};
    width: 18px; height: 18px;
    margin: -7px 0;
    border-radius: 9px;
    border: 1px solid {a["BORDER"]};
}}
QSlider::sub-page:horizontal {{ background: {a["ACCENT"]}; border-radius: 2px; }}

QToolTip {{
    background: {a["TEXT_PRIMARY"]};
    color: {a["BG_BASE"]};
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    font-size: 12px;
}}

QStatusBar {{
    background: {a["BG_BASE"]};
    color: {a["TEXT_MUTED"]};
    font-size: 12px;
}}

QGroupBox {{
    background-color: {a["SURFACE"]};
    border: 1px solid {a["BORDER"]};
    border-radius: 14px;
    margin-top: 20px;
    padding: 28px 22px 22px 22px;
    font-weight: 600;
    color: {a["TEXT_PRIMARY"]};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 18px; top: 16px;
    padding: 0 6px;
    color: {a["TEXT_MUTED"]};
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

QListWidget {{
    background: transparent;
    border: none;
    font-size: 13px;
    color: {a["TEXT_PRIMARY"]};
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 4px;
}}
QListWidget::item:selected {{
    background: {a["ACCENT_SOFT"]};
    color: {a["ACCENT"]};
}}
QListWidget::item:hover {{
    background: {dt.rgba(a["TEXT_PRIMARY"], 0.04)};
}}

QSplitter::handle {{ background: {a["BG_BASE"]}; }}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical {{ height: 2px; }}

QMenu {{
    background: {a["SURFACE"]};
    border: 1px solid {a["BORDER"]};
    border-radius: 12px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 24px;
    border-radius: 8px;
    color: {a["TEXT_PRIMARY"]};
    font-size: 12px;
}}
QMenu::item:selected {{ background: {a["ACCENT_SOFT"]}; color: {a["ACCENT"]}; }}
"""

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # ===== Sidebar =====
        sidebar = Sidebar()
        sidebar.setFixedWidth(210)
        sb = QVBoxLayout(sidebar)
        sb.setSpacing(6)
        sb.setContentsMargins(0, 30, 0, 30)

        logo = QLabel("AI Novel\nFactory")
        logo.setFont(QFont("Inter", 17, QFont.Weight.Bold))
        logo.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; padding: 0 0 0 14px; line-height: 1.3;")
        sb.addWidget(logo)

        ver = QLabel("v1.0 · Apple")
        ver.setFont(QFont("Inter", 10))
        ver.setStyleSheet(
            f"color: {dt.TEXT_MUTED}; padding: 2px 0 22px 14px;")
        sb.addWidget(ver)

        self.nav_buttons = []
        self.nav_stack = QStackedWidget()

        for i, name in enumerate(["创作", "工作台", "预览", "项目库", "设置"]):
            btn = AppleNavButton(name)
            btn.clicked.connect(lambda checked, idx=i: self._switch(idx))
            sb.addWidget(btn)
            self.nav_buttons.append(btn)

        sb.addStretch()

        api_text = "API 已连接" if self.config.get("api_key") else "API 未配置"
        api_color = dt.SUCCESS if self.config.get("api_key") else dt.DANGER
        api_status = QLabel(api_text)
        api_status.setFont(QFont("Inter", 10))
        api_status.setStyleSheet(f"color: {api_color}; padding-left: 14px;")
        sb.addWidget(api_status)

        layout.addWidget(sidebar)

        # ===== Content =====
        self.nav_stack.addWidget(InspirationTab(self.pipeline))
        self.nav_stack.addWidget(AgentsTab(self.pipeline))
        self.nav_stack.addWidget(PreviewTab(self.pipeline))
        self.projects_tab = ProjectsTab()
        self.nav_stack.addWidget(self.projects_tab)
        self.nav_stack.addWidget(SettingsTab())
        # 把「打开项目」信号接到预览页 / 继续生成 信号接到流水线恢复
        self.projects_tab.open_project.connect(
            self._safe(self._open_project_in_preview))
        self.projects_tab.resume_requested.connect(
            self._safe(self._start_resumed_pipeline))
        self.projects_tab.continue_requested.connect(
            self._safe(self._start_continuation))
        self.projects_tab.refresh_requested.connect(
            self._safe(self.projects_tab.refresh))
        layout.addWidget(self.nav_stack)

        self.nav_buttons[0].setChecked(True)
        self.statusBar().setFixedHeight(32)
        self.statusBar().showMessage("Ready")

    @property
    def projects_tab_widget(self):
        return self.nav_stack.widget(3)  # 项目库在第 4 个位置

    def _switch(self, index: int):
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)
        self.nav_stack.setCurrentIndex(index)
        # 进入项目库页时自动刷新。
        # 延迟 50ms 让 QStackedWidget.setCurrentIndex 触发的 show 链先完成。
        # 如果 refresh 在 show 链进行中就执行，QScrollArea viewport 的 show
        # 会让新卡片里的子按钮短暂变成顶级窗口，表现为约 90 个空白弹窗闪一下。
        if index == 3 and hasattr(self, 'projects_tab'):
            QTimer.singleShot(50, self.projects_tab.refresh)
        # API 配置变化时同步更新状态栏（设置页在 index 4）

    def _open_project_in_preview(self, project_path: str):
        """从项目库打开已有项目到预览页"""
        from core.project_manager import load_world_view, load_all_chapters
        # 先清空上一项目的残留，让用户看到最新内容
        self.preview_tab.clear_all()
        wv = load_world_view(project_path)
        chapters = load_all_chapters(project_path)
        if wv:
            self.preview_tab.on_world_view_ready(wv)
        for ch in chapters:
            self.preview_tab.on_chapter_ready(ch)
        # 在状态栏提示当前打开的项目
        title = (wv.get("title")
                 if isinstance(wv, dict) else "") or Path(project_path).name
        ch_count = len(chapters) if chapters else 0
        pw = (self.preview_tab.export_txt_btn.isEnabled()
              or self.preview_tab.export_md_btn.isEnabled())
        self.statusBar().showMessage(
            f"已打开项目：{title}  |  {ch_count} 章" +
            ("" if pw else "  （尚无内容可导出）"))
        # 切到预览页
        self._switch(2)

    def _start_resumed_pipeline(self, project_dir: str):
        """从历史项目断点继续 — 由 projects_tab.resume_requested 触发"""
        from core.project_manager import load_world_view
        wv = load_world_view(project_dir)
        title = ((wv.get("title")
                  if isinstance(wv, dict) else None)
                 or Path(project_dir).name)
        # 是否 API 没配置 -> 引导去设置页
        if not self.config.get("api_key"):
            self.statusBar().showMessage(
                f"项目《{title}》：请到「设置」页配置 API Key")
            self._switch(4)
            return

        # 初始化流水线并启动后台恢复
        if self.pipeline.is_running:
            self.statusBar().showMessage(
                f"当前有任务进行中，请等待完成或先停止")
            return

        self.pipeline.initialize()
        self.statusBar().showMessage(f"已加载项目《{title}》，正在检测进度...")

        # resume_from_project 会在内部生成新线程跑 worker
        try:
            self.pipeline.resume_from_project(project_dir)
        except Exception as e:
            self.statusBar().showMessage(f"恢复失败：{e}")
            return

        # 切到工作台
        self._switch(1)

    def _start_continuation(self, project_dir: str, guidance: str,
                            batch_chapter_count: int):
        """从项目库"续写"入口启动 — 仅生成新大纲，弹出审阅对话框。"""
        from core.project_manager import load_world_view
        wv = load_world_view(project_dir)
        title = ((wv.get("title")
                  if isinstance(wv, dict) else None)
                 or Path(project_dir).name)

        # API key 校验
        if not self.config.get("api_key"):
            self.statusBar().showMessage(
                f"项目《{title}》：请到「设置」页配置 API Key")
            self._switch(4)
            return

        # 校验流水线是否空闲
        if self.pipeline.is_running:
            self.statusBar().showMessage(
                f"当前有任务进行中，请等待完成或先停止")
            return

        # 校验续写指引
        if not guidance or len(guidance.strip()) < 10:
            QMessageBox.warning(self, "续写指引过短",
                                "续写指引至少 10 字，请补充更多内容。")
            return

        self.pipeline.initialize()
        self.statusBar().showMessage(
            f"已加载《{title}》，正在生成续写大纲（第 {batch_chapter_count} 章）...")

        # 切到工作台，用户可看到进度
        self._switch(1)

        try:
            self.pipeline.continue_from_project(
                project_dir,
                guidance=guidance,
                batch_chapter_count=batch_chapter_count,
            )
        except Exception as e:
            self.statusBar().showMessage(f"续写启动失败：{e}")
            return

    def _on_continuation_outline_ready(self, outline: dict):
        """续写大纲生成完成 — 弹出审阅对话框。"""
        from gui.outline_review_dialog import OutlineReviewDialog
        meta = outline.get("outline_meta", {})
        start = meta.get("chapter_start", "?")
        end = meta.get("chapter_end", "?")
        title = self.pipeline.world_view.get("title", "未命名")

        self.statusBar().showMessage(
            f"《{title}》续写大纲已生成（第 {start}-{end} 章），请审阅确认")

        # 暂停流水线线程（实际在 waiting 状态）
        dialog = OutlineReviewDialog(outline, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            reviewed = dialog.get_reviewed_outline()
            self.statusBar().showMessage(
                f"审阅确认，开始生成第 {start}-{end} 章...")
            self.pipeline.confirm_continuation(reviewed)
        else:
            # 用户取消：清理状态
            self.pipeline.discard_continuation()
            self.statusBar().showMessage("续写已取消")
            # 刷新项目库（新大纲文件已保存，但状态恢复）
            if hasattr(self, 'projects_tab'):
                self.projects_tab.refresh()

    def _on_continuation_progress(self, stage_text: str, progress: int):
        """续写大纲生成中的进度更新。"""
        self.statusBar().showMessage(f"《续写大纲》{stage_text} {progress}%")

    def _on_world_view_review_ready(self, world_view: dict):
        """世界观生成完成 — 弹出审阅对话框。"""
        from gui.worldview_review_dialog import WorldViewReviewDialog
        title = world_view.get("title", "未命名")
        chars = world_view.get("characters", [])
        char_summary = "、".join(c.get("name", "?") for c in (chars or [])[:5])
        self.statusBar().showMessage(
            f"世界观《{title}》已生成，角色：{char_summary or '（无）'} — 请审阅")

        dialog = WorldViewReviewDialog(world_view, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            reviewed = dialog.get_reviewed_world_view()
            self.statusBar().showMessage(
                f"世界观审阅确认《{reviewed.get('title', '')}》，启动大纲生成...")
            # 工作台 tab 已显示世界观；预览页也会看到
            self.pipeline.confirm_world_view(reviewed)
        else:
            self.pipeline.discard_world_view()
            self.statusBar().showMessage("世界观审阅已取消，本次生成已中止")
            if hasattr(self, 'projects_tab'):
                self.projects_tab.refresh()

    def _safe(self, fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                import traceback
                print(f"[UI Error] {fn.__name__}: {e}")
                traceback.print_exc()
                # 同步信号回调里抛出的异常会被 Qt 静默吞掉，这里主动弹框提示。
                # 注意：不能传 self 作 parent（C++ 对象可能已销毁），用无父方式弹框。
                try:
                    box = QMessageBox()
                    box.setIcon(QMessageBox.Icon.Critical)
                    box.setWindowTitle("操作失败")
                    box.setText(f"{fn.__name__} 出错：{e}")
                    box.setInformativeText("请查看控制台获取详细 traceback。")
                    box.exec()
                except Exception:
                    pass
        return wrapper

    def _setup_pipeline_signals(self):
        signals = self.pipeline.signals
        signals.log_signal.connect(self._safe(self.agents_tab.append_log))
        signals.overall_progress.connect(self._safe(self.agents_tab.update_overall_progress))
        signals.world_view_ready.connect(self._safe(self.preview_tab.on_world_view_ready))
        signals.world_view_ready.connect(self._safe(self.agents_tab.on_world_view_ready))
        signals.outline_ready.connect(self._safe(self.preview_tab.on_outline_ready))
        signals.chapter_ready.connect(self._safe(self.preview_tab.on_chapter_ready))
        signals.chapter_ready.connect(self._safe(self.agents_tab.on_chapter_complete))
        signals.pipeline_finished.connect(self._on_finished)
        signals.log_signal.connect(lambda n, m: self.agents_tab.update_agent_log(n, m))
        # ---- 续写信号 ----
        signals.continuation_outline_ready.connect(
            self._safe(self._on_continuation_outline_ready))
        signals.continuation_progress.connect(
            self._safe(self._on_continuation_progress))
        # ---- 世界观审查信号 ----
        signals.world_view_review_ready.connect(
            self._safe(self._on_world_view_review_ready))

    @property
    def agents_tab(self): return self.nav_stack.widget(1)
    @property
    def preview_tab(self): return self.nav_stack.widget(2)

    @pyqtSlot(dict)
    def _on_finished(self, result: dict):
        if result.get("paused"):
            title = result.get("title", "未命名项目")
            self.statusBar().showMessage(f"《{title}》已暂停并保存，可在项目库继续生成")
            if hasattr(self, 'projects_tab'):
                self.projects_tab.refresh()
            return
        if "error" in result:
            self.statusBar().showMessage(f"Error: {result['error']}")
        else:
            title = result.get("title", "")
            ch = result.get("chapters_count", 0)
            w = result.get("total_words", 0)
            self.statusBar().showMessage(f"{title}  |  {ch} ch  |  {w:,} words")
            self.preview_tab.refresh_all()
            # 流水线完成时自动刷新项目库
            if hasattr(self, 'projects_tab'):
                self.projects_tab.refresh()
            QMessageBox.information(self, "完成",
                f"《{title}》\n\n共 {ch} 章，{w:,} 字\n\n可前往「预览」页导出。")

    def closeEvent(self, event):
        if self.pipeline.is_running:
            r = QMessageBox.question(self, "Confirm", "Pipeline running. Exit anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.pipeline.stop()
        event.accept()
