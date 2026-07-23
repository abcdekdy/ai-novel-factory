"""
项目管理 Tab — Apple Light Style
单列流式卡片 + 滚动，宽度自适应，支持 打开 / 导出 / 删除
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QFileDialog,
    QMessageBox, QGraphicsDropShadowEffect, QSizePolicy,
    QTextEdit, QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QFont, QCursor, QColor
)

from core.project_manager import (
    list_projects, load_world_view, load_all_chapters,
    export_to_txt, export_to_markdown
)
from core.config import load_config
from gui.widgets.stepper import AppleStepper
from assets import design_tokens as dt


class ProjectsTab(QWidget):
    """历史项目管理页 — 单列卡片列表"""

    open_project = pyqtSignal(str)
    resume_requested = pyqtSignal(str)
    continue_requested = pyqtSignal(str, str, int)  # (project_dir, guidance, batch_chapter_count)
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(36, 32, 48, 28)

        # 顶部标题 + 刷新
        header = QHBoxLayout()
        title = QLabel("项目库")
        title.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedSize(84, 36)
        refresh_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        layout.addLayout(header)

        # 卡片滚动区
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #C7C7CC; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #AEAEB2; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self.cards_container = QWidget()
        self.cards_list = QVBoxLayout(self.cards_container)
        self.cards_list.setSpacing(12)
        self.cards_list.setContentsMargins(6, 6, 14, 6)
        self.cards_list.addStretch()  # 卡片顶住上方，下方留白
        self.scroll.setWidget(self.cards_container)

        # 浅灰凹陷容器包裹滚动区
        self.scroll_host = _ScrollHost(self.scroll)
        layout.addWidget(self.scroll_host)

        # 不在 __init__ 里 refresh：此时窗口不可见，且 _switch(3) 首次切换时会
        # 自动 refresh。提前 refresh 会在卡片尚未填充的瞬间被画出来，
        # 表现为一个短暂空白弹窗；同时避免构造期无谓的磁盘 IO。

    def refresh(self):
        """重新加载项目列表。

        核心思路：不在原布局里"先删后建"（这会让旧卡片 widget 短暂无父，
        Qt 会为 81 个子按钮逐个创建原生窗口，表现为空白弹窗闪一下），
        而是新建一个完整的新容器，一次性 setWidget 替换整个 scroll 内容。
        旧容器及其所有子 widget 从未被单独 reparent，随旧容器一起被整体替换。
        """
        # 1. 构建新容器 + 新布局
        new_container = QWidget()
        new_layout = QVBoxLayout(new_container)
        new_layout.setSpacing(12)
        new_layout.setContentsMargins(6, 6, 14, 6)
        new_layout.addStretch()

        projects = list_projects()
        if not projects:
            empty = QLabel("暂无项目 — 前往「创作」页开始你的第一部小说")
            empty.setFont(QFont("Inter", 13))
            empty.setStyleSheet(f"color: {dt.TEXT_MUTED}; padding: 40px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            new_layout.insertWidget(0, empty)
        else:
            for proj in projects:
                card = _ProjectCard(proj)
                card.open_requested.connect(self.open_project.emit)
                card.resume_requested.connect(self.resume_requested.emit)
                card.continue_requested.connect(self.continue_requested.emit)
                card.refresh_requested.connect(self.refresh_requested.emit)
                new_layout.insertWidget(new_layout.count() - 1, card)

        # 2. 一次性替换 scroll area 的内容 widget（原子操作，中间态不可见）。
        #    setWidget 后旧容器会被 Qt 自动 reparent 到内部，无需也不能
        #    deleteLater（否则 RuntimeError: wrapped C/C++ object deleted）。
        #
        # 防止子按钮短暂变成顶级窗口（空白弹窗闪一下）：
        # 替换期间隐藏滚动区，替换完成后再显示。
        # 隐藏状态下 setWidget 触发的 show 链不会创建原生窗口。
        self.scroll.setVisible(False)
        self.scroll.setWidget(new_container)
        self.scroll.setVisible(True)
        self.cards_container = new_container
        self.cards_list = new_layout


class _ProjectCard(QFrame):
    """单个项目卡片 — Apple 风格白底 + 轻投影，单列全宽"""

    open_requested = pyqtSignal(str)
    resume_requested = pyqtSignal(str)
    continue_requested = pyqtSignal(str, str, int)
    refresh_requested = pyqtSignal()

    def __init__(self, project: dict, parent=None):
        super().__init__(parent)
        self.project = project
        self.path = project.get("path", "")
        self.summary = project.get("summary", {})
        self.btn_row = None      # 按钮行布局引用（供 refresh_card 重绘）
        self.btn_row_index = -1  # 按钮行在 root 布局中的位置
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # 轻投影
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)

        self.setStyleSheet(f"""
            _ProjectCard {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {dt.RADIUS_LG}px;
            }}
        """)

        self._build_ui()

    def _build_ui(self):
        # 顶层垂直布局：第一行 标题/状态/按钮，第二行灵感，第三行统计
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(18, 12, 18, 14)

        # ---- 第一行：标题 + 状态徽章 + 按钮（按钮换行跟随） ----
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        title_text = (self.summary.get("title")
                      or self.project.get("name", "未命名"))
        title = QLabel(title_text)
        title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        title.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Preferred)
        row1.addWidget(title)

        # 状态徽章
        status = self.summary.get("status", "generating")
        if status == "generating":
            badge_text, badge_fg, badge_bg = "生成中", dt.WARNING, dt.WARNING_SOFT
        elif status == "paused":
            badge_text, badge_fg, badge_bg = "已暂停", dt.TEXT_SECONDARY, dt.BG_PRESSED
        else:
            badge_text, badge_fg, badge_bg = "已完成", dt.SUCCESS, dt.SUCCESS_SOFT
        badge = QLabel(badge_text)
        badge.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        badge.setFixedHeight(22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color: {badge_fg}; background: {badge_bg};"
            f"border-radius: 11px; padding: 2px 12px;")
        row1.addWidget(badge)
        root.addLayout(row1)

        # ---- 按钮行（横排，被内容区宽度自然约束） ----
        self._build_buttons_row(root)

        # ---- 第二行：灵感 ----
        inspiration = self.summary.get("inspiration", "")
        if inspiration:
            sub = QLabel(inspiration)
            sub.setFont(QFont("Inter", 11))
            sub.setStyleSheet(f"color: {dt.TEXT_MUTED};")
            sub.setWordWrap(True)
            root.addWidget(sub)

        # ---- 第三行：统计气泡 ----
        stats = QHBoxLayout()
        stats.setSpacing(8)
        ch_count = (self.summary.get("chapters_count")
                    or self.summary.get("chapter_count", 0))
        words = self.summary.get("total_words", 0)
        score = self.summary.get("avg_quality_score", 0)
        started = (self.summary.get("started_at")
                   or self.summary.get("completed_at", ""))
        stats.addWidget(self._bubble(f"{ch_count} 章"))
        if words:
            stats.addWidget(self._bubble(f"{words:,} 字"))
        if score:
            stats.addWidget(self._bubble(f"{score} 分"))
        if started:
            date_str = started[:10] if len(started) >= 10 else started
            stats.addWidget(self._bubble(date_str))
        stats.addStretch()
        root.addLayout(stats)

    def _bubble(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Inter", 9))
        lbl.setFixedHeight(20)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {dt.TEXT_SECONDARY}; background: {dt.BG_PRESSED};"
            f"border-radius: 10px; padding: 1px 10px;")
        return lbl

    def _build_buttons_row(self, root):
        """构建按钮行并加入 root 布局。

        四个状态相关按钮在初始化时全部创建并存入 self._btn_* 引用，
        后续 refresh_card() 只切换 visible 属性，不增删布局——
        避免 PyQt6 中 QBoxLayout.takeAt() 不可用的问题。
        """
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.addStretch()

        status = self.summary.get("status", "generating")
        ch_count = (self.summary.get("chapters_count")
                    or self.summary.get("chapter_count", 0))
        enable_series = (ch_count > 0)

        # ---- "继续生成" 按钮（始终创建，按状态显隐） ----
        self._btn_resume = QPushButton("继续生成")
        self._btn_resume.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_resume.setFixedHeight(32)
        self._btn_resume.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._btn_resume.setVisible(status != "completed")
        self._btn_resume.setEnabled(status != "completed")
        self._btn_resume.setStyleSheet(f"""
            QPushButton {{
                background: {dt.ACCENT};
                color: {dt.TEXT_INVERSE};
                border: none;
                border-radius: 10px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }}
            QPushButton:disabled {{ background: {dt.TEXT_DISABLED}; color: {dt.TEXT_INVERSE}; }}
        """)
        self._btn_resume.clicked.connect(
            lambda: self.resume_requested.emit(self.path))
        btn_row.addWidget(self._btn_resume)

        # ---- "续写" 按钮（创建，按状态显隐） ----
        self._btn_continue = QPushButton("续写")
        self._btn_continue.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_continue.setFixedHeight(32)
        self._btn_continue.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._btn_continue.setVisible(
            (status != "completed") and enable_series)
        self._btn_continue.setStyleSheet(f"""
            QPushButton {{
                background: {dt.ACCENT};
                color: {dt.TEXT_INVERSE};
                border: none;
                border-radius: 10px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }}
        """)
        self._btn_continue.clicked.connect(
            lambda: self._on_continue_requested())
        btn_row.addWidget(self._btn_continue)

        # ---- "完结" 按钮（创建，按状态显隐） ----
        self._btn_finish = QPushButton("完结")
        self._btn_finish.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_finish.setFixedHeight(32)
        self._btn_finish.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._btn_finish.setVisible(
            (status != "completed") and enable_series)
        self._btn_finish.setStyleSheet(f"""
            QPushButton {{
                background: {dt.BG_RAISED};
                color: {dt.SUCCESS};
                border: 1px solid {dt.BORDER};
                border-radius: 10px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.SUCCESS_SOFT}; }}
        """)
        self._btn_finish.clicked.connect(lambda: self._on_finish_project())
        btn_row.addWidget(self._btn_finish)

        # ---- "转为续写模式" 按钮（创建，仅 completed + 有章节时显示） ----
        self._btn_reopen = QPushButton("转为续写模式")
        self._btn_reopen.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._btn_reopen.setFixedHeight(32)
        self._btn_reopen.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self._btn_reopen.setVisible(
            (status == "completed") and enable_series)
        self._btn_reopen.setStyleSheet(f"""
            QPushButton {{
                background: {dt.BG_RAISED};
                color: {dt.ACCENT};
                border: 1px solid {dt.BORDER};
                border-radius: 10px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.ACCENT_SOFT}; }}
        """)
        self._btn_reopen.clicked.connect(lambda: self._on_reopen_series())
        btn_row.addWidget(self._btn_reopen)

        # ---- 中性按钮（打开/导出/删除） ----
        small_btn_style = f"""
            QPushButton {{
                background: {dt.BG_RAISED};
                color: {dt.TEXT_PRIMARY};
                border: 1px solid {dt.BORDER};
                border-radius: 10px;
                padding: 2px 14px;
                font-family: {dt.FONT_SYSTEM};
            }}
            QPushButton:hover {{
                color: {dt.ACCENT};
                background: {dt.BG_PRESSED};
                border: 1px solid {dt.BORDER};
            }}
        """

        open_btn = QPushButton("打开")
        open_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        open_btn.setFixedHeight(32)
        open_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        open_btn.setStyleSheet(small_btn_style)
        open_btn.clicked.connect(lambda: self.open_requested.emit(self.path))
        btn_row.addWidget(open_btn)

        export_btn = QPushButton("导出")
        export_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        export_btn.setFixedHeight(32)
        export_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        export_btn.setStyleSheet(small_btn_style)
        export_btn.clicked.connect(self._show_export_menu)
        btn_row.addWidget(export_btn)

        del_btn = QPushButton("删除")
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setFixedHeight(32)
        del_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: {dt.BG_RAISED};
                color: {dt.DANGER};
                border: 1px solid {dt.BORDER};
                border-radius: 9px;
                font-weight: 600;
                padding: 2px 12px;
            }}
            QPushButton:hover {{ background: {dt.DANGER_SOFT}; }}
        """)
        del_btn.clicked.connect(self._confirm_delete)
        btn_row.addWidget(del_btn)

        root.addLayout(btn_row)
        self.btn_row = btn_row

    def refresh_card(self):
        """从磁盘重新加载 summary，切换按钮显隐（不增删布局，避免 PyQt6 takeAt 问题）。"""
        try:
            from core.project_manager import load_project_summary
            self.summary = load_project_summary(self.path)
            status = self.summary.get("status", "generating")
            ch_count = (self.summary.get("chapters_count")
                        or self.summary.get("chapter_count", 0))
            enable_series = (ch_count > 0)

            # 控制 4 个状态按钮的显隐（它们始终存在于布局中，只切换 visible）
            if hasattr(self, "_btn_continue"):
                self._btn_continue.setVisible(
                    (status != "completed") and enable_series)
            if hasattr(self, "_btn_finish"):
                self._btn_finish.setVisible(
                    (status != "completed") and enable_series)
            if hasattr(self, "_btn_reopen"):
                self._btn_reopen.setVisible(
                    (status == "completed") and enable_series)
            if hasattr(self, "_btn_resume"):
                self._btn_resume.setVisible(status != "completed")
        except Exception as e:
            print(f"[refresh_card ERROR] {e}")
            QMessageBox.warning(self, "刷新卡片失败", str(e))

    def _on_continue_requested(self):
        """弹出续写入口对话框，收集续写指引 + 本批章数后发射 continue_requested。"""
        dialog = ContinuationEntryDialog(self.path, self.summary, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            guidance, count = dialog.get_result()
            self.continue_requested.emit(self.path, guidance, count)

    def _on_finish_project(self):
        """把项目标记为完结（completed），完成后立即刷新卡片按钮行。"""
        from core.project_manager import load_project_summary, save_project_summary
        r = QMessageBox.question(
            self, "确认完结",
            "确定要将本项目标记为「已完结」？\n之后仍可通过「转为续写模式」恢复连载。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r == QMessageBox.StandardButton.Yes:
            try:
                updated = load_project_summary(self.path)
                updated["status"] = "completed"
                updated["completed_at"] = __import__("time").strftime(
                    "%Y-%m-%d %H:%M:%S")
                save_project_summary(self.path, updated)
                self.refresh_card()  # 卡片按钮行立即变成"转为续写模式"
            except Exception as e:
                print(f"[finish_project ERROR] {e}")
                QMessageBox.warning(self, "操作失败", str(e))

    def _on_reopen_series(self):
        """把已完结项目恢复为连载中，立即弹续写入口对话框进入续写。"""
        from core.project_manager import load_project_summary, save_project_summary
        print("[reopen_series] 步骤1: 读取 summary")
        updated = load_project_summary(self.path)
        updated["status"] = "generating"
        updated.pop("completed_at", None)
        print("[reopen_series] 步骤2: 写入 status")
        save_project_summary(self.path, updated)
        print("[reopen_series] 步骤3: refresh_card")
        self.refresh_card()  # 只改 visible，无 takeAt
        print("[reopen_series] 步骤4: 打开续写对话框")
        self._on_continue_requested()
        print("[reopen_series] 完成")

    def _show_export_menu(self):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background: {dt.SURFACE};
                border: 1px solid {dt.BORDER};
                border-radius: 12px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px;
                border-radius: 8px;
                color: {dt.TEXT_PRIMARY};
                font-size: 12px;
            }}
            QMenu::item:selected {{ background: {dt.ACCENT_SOFT}; color: {dt.ACCENT}; }}
        """)
        act_txt = menu.addAction("导出为 TXT")
        act_md = menu.addAction("导出为 Markdown")
        btn = self.sender()
        pos = btn.mapToGlobal(btn.rect().bottomLeft())
        action = menu.exec(pos)
        if action == act_txt:
            self._do_export("txt")
        elif action == act_md:
            self._do_export("md")

    def _do_export(self, fmt: str):
        title = self.summary.get("title", "novel")
        default_name = f"{title}.{fmt}"
        if fmt == "txt":
            path, _ = QFileDialog.getSaveFileName(
                self, "导出 TXT", default_name, "Text Files (*.txt)")
            if path and export_to_txt(self.path, path):
                QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "导出 Markdown", default_name, "Markdown Files (*.md)")
            if path and export_to_markdown(self.path, path):
                QMessageBox.information(self, "导出成功", f"已导出到:\n{path}")

    def _confirm_delete(self):
        title = self.summary.get("title") or self.project.get("name", "未命名")
        r = QMessageBox.question(
            self, "确认删除",
            f"确定要删除项目《{title}》？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r == QMessageBox.StandardButton.Yes:
            import shutil
            try:
                shutil.rmtree(self.path, ignore_errors=True)
                self.deleteLater()
            except Exception as e:
                QMessageBox.warning(self, "删除失败", str(e))


# ----------------------------------------------------------------------
#  凹陷滚动区容器 — 浅灰底 + 细边框，包住 QScrollArea 消除底部直角
# ----------------------------------------------------------------------
class _ScrollHost(QFrame):
    def __init__(self, scroll_area: QScrollArea, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _ScrollHost {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER};
                border-radius: {dt.RADIUS_XL}px;
            }}
        """)
        scroll_area.setParent(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(scroll_area)


# ----------------------------------------------------------------------
#  续写入口对话框 — 收集续写指引 + 本批章数
# ----------------------------------------------------------------------
class ContinuationEntryDialog(QDialog):
    """续写入口 — 输入续写方向指引 + 本批章数。"""

    def __init__(self, project_path: str, summary: dict, parent=None):
        super().__init__(parent)
        self.project_path = project_path
        self.summary = summary
        self.config = load_config()

        self.setWindowTitle("续写小说")
        self.setMinimumSize(540, 380)
        self.resize(580, 420)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(28, 24, 28, 20)

        # ---- 标题 + 项目信息 ----
        title = QLabel("续写下一批章节")
        title.setFont(QFont(dt.FONT_SYSTEM, 18, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        root.addWidget(title)

        # 项目名 + 当前章数
        project_name = self.summary.get("title", "未命名")
        current_count = (self.summary.get("chapters_count")
                         or self.summary.get("chapter_count", 0))
        info = QLabel(f"项目：{project_name}  |  已完成：{current_count} 章")
        info.setFont(QFont(dt.FONT_SYSTEM, 12))
        info.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        root.addWidget(info)

        # ---- 续写指引 ----
        guide_lbl = QLabel("续写方向指引")
        guide_lbl.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        guide_lbl.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        root.addWidget(guide_lbl)

        helper = QLabel("描述接下来故事走向，如：进入秘境探险、主角觉醒新能力、某角色身份暴露等")
        helper.setFont(QFont(dt.FONT_SYSTEM, 11))
        helper.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        helper.setWordWrap(True)
        root.addWidget(helper)

        self.guidance_input = QTextEdit()
        self.guidance_input.setPlaceholderText("请输入续写方向指引（至少 10 字）...")
        self.guidance_input.setMinimumHeight(110)
        self.guidance_input.setFont(QFont(dt.FONT_SYSTEM, 12))
        self.guidance_input.setStyleSheet(f"""
            QTextEdit {{
                background: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {dt.RADIUS_MD}px;
                padding: 10px 12px;
                color: {dt.TEXT_PRIMARY};
                selection-background-color: {dt.ACCENT};
                selection-color: #FFFFFF;
            }}
        """)
        root.addWidget(self.guidance_input)

        # ---- 本批章数 ----
        count_row = QHBoxLayout()
        count_lbl = QLabel("本批章数：")
        count_lbl.setFont(QFont(dt.FONT_SYSTEM, 12))
        count_lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        count_row.addWidget(count_lbl)

        self.chapter_stepper = AppleStepper()
        self.chapter_stepper.setRange(1, 50)
        self.chapter_stepper.setValue(self.config.get("default_chapter_count", 10))
        self.chapter_stepper.setFixedHeight(42)
        self.chapter_stepper.setFont(QFont(dt.FONT_SYSTEM, 13))
        count_row.addWidget(self.chapter_stepper)
        count_row.addStretch()
        root.addLayout(count_row)

        root.addStretch()

        # ---- 按钮 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(110, 40)
        cancel_btn.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: {dt.BG_RAISED};
                color: {dt.TEXT_PRIMARY};
                border: 1px solid {dt.BORDER};
                border-radius: {dt.RADIUS_MD}px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.BG_PRESSED}; color: {dt.ACCENT}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("生成续写大纲")
        confirm_btn.setFixedSize(160, 40)
        confirm_btn.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        confirm_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: {dt.ACCENT};
                color: {dt.TEXT_INVERSE};
                border: none;
                border-radius: {dt.RADIUS_MD}px;
                padding: 2px 14px;
            }}
            QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }}
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(confirm_btn)
        root.addLayout(btn_row)

    def _on_confirm(self):
        guidance = self.guidance_input.toPlainText().strip()
        if not guidance:
            QMessageBox.warning(self, "提示", "请输入续写方向指引")
            return
        if len(guidance) < 10:
            QMessageBox.warning(self, "提示", "请至少输入 10 字，描述越详细效果越好")
            return
        self.accept()

    def get_result(self) -> tuple:
        """返回 (guidance, batch_chapter_count)。"""
        guidance = self.guidance_input.toPlainText().strip()
        count = self.chapter_stepper.value()
        return guidance, count
