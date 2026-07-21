"""
Preview Tab — Apple Light Style
白底三栏布局 · 浅灰章节列表 · Apple Blue 导出按钮
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QTextEdit, QPushButton,
    QSplitter, QGroupBox, QMessageBox, QFileDialog,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QFont, QCursor, QColor

from core.project_manager import (
    load_world_view, load_all_chapters, export_to_txt, export_to_markdown,
    save_chapter, load_chapter
)
from assets import design_tokens as dt


class PreviewTab(QWidget):
    """内容预览 — Apple 风格。"""

    def __init__(self, pipeline):
        super().__init__()
        self.pipeline = pipeline
        # 当前展示的章节状态追踪
        self._current_chapter_index = None   # 当前选中章节号
        self._original_content = ""           # 加载时的原始正文（用于比对改动）
        self._is_dirty = False               # 是否有未保存的修改
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 15, 20, 20)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("预览")
        title.setFont(QFont("Inter", 22, QFont.Weight.Bold))
        title.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; letter-spacing: -0.02em;")
        header.addWidget(title)
        header.addStretch()

        self.export_txt_btn = QPushButton("导出 TXT")
        self.export_txt_btn.setFixedSize(120, 36)
        self.export_txt_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.export_txt_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.export_txt_btn.clicked.connect(self._export_txt)
        self.export_txt_btn.setEnabled(False)
        header.addWidget(self.export_txt_btn)

        self.export_md_btn = QPushButton("导出 Markdown")
        self.export_md_btn.setFixedSize(140, 36)
        self.export_md_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self.export_md_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.export_md_btn.clicked.connect(self._export_markdown)
        self.export_md_btn.setEnabled(False)
        header.addWidget(self.export_md_btn)
        layout.addLayout(header)

        # 三栏布局
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左：世界观 — Apple 浅灰凹陷
        world_widget = _AppleInset(radius=12, parent=self)
        wl = world_widget.inner_layout()
        world_header = QLabel("世界观")
        world_header.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        world_header.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        wl.addWidget(world_header)
        self.world_view_display = QTextEdit()
        self.world_view_display.setReadOnly(True)
        self.world_view_display.setPlaceholderText("世界观信息...")
        self.world_view_display.setStyleSheet(
            "QTextEdit { background: transparent; border: none; }")
        wl.addWidget(self.world_view_display)
        splitter.addWidget(world_widget)

        # 中：章节列表 — Apple 浅灰凹陷
        chapter_widget = _AppleInset(radius=12, parent=self)
        cl = chapter_widget.inner_layout()
        chapter_header = QLabel("章节目录")
        chapter_header.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        chapter_header.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        cl.addWidget(chapter_header)
        self.chapter_list = QListWidget()
        self.chapter_list.itemClicked.connect(self._on_chapter_selected)
        self.chapter_list.setFont(QFont("Inter", 11))
        self.chapter_list.setStyleSheet("QListWidget { background: transparent; }")
        cl.addWidget(self.chapter_list)
        splitter.addWidget(chapter_widget)

        # 右：章节内容预览 — Apple 浅灰凹陷
        content_widget = _AppleInset(radius=12, parent=self)
        cl2 = content_widget.inner_layout()
        content_header_layout = QHBoxLayout()
        content_header_layout.setSpacing(8)
        content_header = QLabel("章节内容")
        content_header.setFont(QFont("Inter", 12, QFont.Weight.Bold))
        content_header.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
        content_header_layout.addWidget(content_header)
        content_header_layout.addStretch()
        # 已编辑标记
        self.edited_badge = QLabel("")
        self.edited_badge.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.edited_badge.setStyleSheet(
            f"color: {dt.ACCENT}; padding: 2px 8px;")
        self.edited_badge.setVisible(False)
        content_header_layout.addWidget(self.edited_badge)
        # 保存按钮
        self.save_btn = QPushButton("保存修改")
        self.save_btn.setFixedSize(96, 28)
        self.save_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        self.save_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.save_btn.setStyleSheet(
            f"QPushButton {{ background: {dt.ACCENT}; color: white; "
            f"border: none; border-radius: 6px; padding: 2px 12px; }} "
            f"QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }} "
            f"QPushButton:pressed {{ background: {dt.ACCENT_DIM}; }} "
            f"QPushButton:disabled {{ background: {dt.BORDER}; color: {dt.TEXT_MUTED}; }}")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_current_chapter)
        content_header_layout.addWidget(self.save_btn)
        cl2.addLayout(content_header_layout)
        self.content_display = QTextEdit()
        self.content_display.setReadOnly(False)   # 默认可编辑
        self.content_display.setPlaceholderText("选择章节查看内容...")
        self.content_display.setFont(QFont("Microsoft YaHei", 11))
        self.content_display.setStyleSheet(
            "QTextEdit { background: transparent; border: none; }")
        self.content_display.textChanged.connect(self._on_content_changed)
        cl2.addWidget(self.content_display)
        splitter.addWidget(content_widget)

        splitter.setChildrenCollapsible(False)
        splitter.setSizes([300, 200, 500])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 5)

        # 让三栏面板使用统计信息上方的全部可用空间，避免预览页底部留白。
        layout.addWidget(splitter, 1)

        # 统计信息
        self.stats_label = QLabel("暂无数据")
        self.stats_label.setStyleSheet(
            f"color: {dt.TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self.stats_label)

    @pyqtSlot(dict)
    def on_world_view_ready(self, world_view: dict):
        if not world_view or not isinstance(world_view, dict):
            return
        self.world_view_display.setPlainText(
            self._format_world_view(world_view_data=world_view))
        self.export_txt_btn.setEnabled(True)
        self.export_md_btn.setEnabled(True)

    @pyqtSlot(dict)
    def on_outline_ready(self, outline: dict):
        """大纲数据就绪 — 在预览页展示"""
        if not outline or not isinstance(outline, dict):
            return
        current = self.world_view_display.toPlainText()
        outline_text = self._format_outline(outline)
        if current:
            self.world_view_display.setPlainText(
                current + "\n\n" + "=" * 40 + "\n\n" + outline_text)
        else:
            self.world_view_display.setPlainText(outline_text)

    def _format_outline(self, outline: dict) -> str:
        """格式化大纲显示"""
        lines = []
        lines.append("【详细大纲】")
        meta = outline.get("outline_meta", {})
        if meta:
            lines.append(f"共 {meta.get('total_chapters', '?')} 章")

        global_arc = outline.get("global_arc", {})
        if global_arc:
            acts = global_arc.get("three_act_structure", {}) or global_arc.get("acts", {})
            if isinstance(acts, dict):
                for name in ("setup", "confrontation", "resolution"):
                    if name in acts:
                        a = acts[name]
                        ch = a.get("chapters", [])
                        ch_str = f"第{ch[0]}-{ch[-1]}章" if ch else ""
                        lines.append(f"  · {name} {ch_str}：{a.get('purpose', '')}")
            elif isinstance(acts, list):
                for a in acts:
                    ch = a.get("chapters", [])
                    ch_str = f"第{ch[0]}-{ch[-1]}章" if ch else ""
                    lines.append(f"  · {a.get('name', '')} {ch_str}：{a.get('purpose', '')}")
            thread = global_arc.get("core_thread", "")
            if thread:
                lines.append(f"  核心线索：{thread}")
            lines.append("")

        rules = outline.get("consistency_rules", [])
        if rules:
            lines.append("一致性规则（绝对不能违反）：")
            for i, r in enumerate(rules):
                lines.append(f"  {i+1}. {r}")
            lines.append("")

        for ch in outline.get("chapters", []):
            idx = ch.get("chapter_index", "?")
            title = ch.get("title", "")
            lines.append(f"── 第{idx}章「{title}」 ──")
            plot = ch.get("plot_detail", "")
            if plot:
                short = plot if len(plot) <= 120 else plot[:120] + "..."
                lines.append(f"  情节：{short}")
            events = ch.get("key_events", [])
            if events:
                lines.append(f"  关键事件：{' / '.join(events)}")
            devs = ch.get("character_developments", {})
            if devs:
                lines.append(f"  人物变化：{'; '.join(f'{k}→{v}' for k, v in devs.items())}")
            fs = ch.get("foreshadowing", [])
            if fs:
                lines.append(f"  伏笔：{' / '.join(fs)}")
            cliff = ch.get("cliffhanger", "")
            if cliff:
                lines.append(f"  章尾：{cliff}")
            lines.append("")

        return "\n".join(lines)

    @pyqtSlot(dict)
    def on_chapter_ready(self, chapter_data: dict):
        if not chapter_data or not isinstance(chapter_data, dict):
            return
        title = chapter_data.get("title", "未知")
        index = chapter_data.get("chapter_index") or chapter_data.get("chapter") or 0
        word_count = chapter_data.get("word_count", 0)

        # 并行生成时章节完成顺序不固定，目录必须按章节号而非完成时间排列。
        for row in range(self.chapter_list.count()):
            existing = self.chapter_list.item(row)
            if self._chapter_sort_key(existing.data(Qt.ItemDataRole.UserRole)) \
                    == self._chapter_sort_key(index):
                existing.setText(f"第{index}章 - {title} ({word_count}字)")
                existing.setData(Qt.ItemDataRole.UserRole, index)
                self._update_stats()
                return

        item = QListWidgetItem(f"第{index}章 - {title} ({word_count}字)")
        item.setData(Qt.ItemDataRole.UserRole, index)
        insert_row = self.chapter_list.count()
        new_key = self._chapter_sort_key(index)
        for row in range(self.chapter_list.count()):
            existing_key = self._chapter_sort_key(
                self.chapter_list.item(row).data(Qt.ItemDataRole.UserRole))
            if new_key < existing_key:
                insert_row = row
                break
        self.chapter_list.insertItem(insert_row, item)
        self._update_stats()

    @staticmethod
    def _chapter_sort_key(index):
        """章节号优先按数字排序，兼容旧项目中的字符串编号。"""
        try:
            return 0, int(index)
        except (TypeError, ValueError):
            return 1, str(index)

    def _on_content_changed(self):
        """正文区被编辑时触发 —— 标记脏状态并启用保存按钮。"""
        if self._current_chapter_index is None:
            return
        new_text = self.content_display.toPlainText()
        self._is_dirty = (new_text != self._original_content)
        self.save_btn.setEnabled(self._is_dirty)
        self.edited_badge.setVisible(self._is_dirty)
        if self._is_dirty:
            self.edited_badge.setText("未保存")

    def _on_chapter_selected(self, item: QListWidgetItem):
        # 切换前：如果有未保存改动，弹确认
        if not self._maybe_prompt_save("切换章节"):
            return

        index = item.data(Qt.ItemDataRole.UserRole)
        self._current_chapter_index = index
        self._is_dirty = False
        self.save_btn.setEnabled(False)
        self.edited_badge.setVisible(False)

        if self.pipeline.project_dir:
            # 优先加载磁盘上的最新内容（含手动编辑后的版本）
            ch = load_chapter(self.pipeline.project_dir, index)
            if not ch:
                chapters = sorted(
                    load_all_chapters(self.pipeline.project_dir),
                    key=lambda c: self._chapter_sort_key(
                        c.get("chapter_index", c.get("chapter", 0))))
                for c in chapters:
                    if c.get("chapter_index") == index:
                        ch = c
                        break
            if ch:
                title = ch.get("title", "")
                content = ch.get("content", "")
                self.content_display.setPlainText(
                    f"【{title}】\n\n{content}"
                )
                # 记录原始正文部分（去掉标题行），用于脏比对
                self._original_content = f"【{title}】\n\n{content}"
                # 如果之前被手动过，显示一个已编辑徽标
                if ch.get("manually_edited"):
                    self.edited_badge.setText("已手动编辑")
                    self.edited_badge.setVisible(True)
                return

        # 回退到内存中的 pipeline.chapters
        for ch in self.pipeline.chapters:
            if ch.get("chapter_index") == index:
                title = ch.get("title", "")
                content = ch.get("content", "")
                self.content_display.setPlainText(
                    f"【{title}】\n\n{content}"
                )
                self._original_content = f"【{title}】\n\n{content}"
                return

    def _save_current_chapter(self):
        """把当前编辑后的正文写回磁盘（chapter_NNN_meta.json + .txt）。"""
        if self._current_chapter_index is None or not self._is_dirty:
            return
        try:
            new_full_text = self.content_display.toPlainText().strip()
            # 解析标题行 + 正文
            title, content = self._split_title_content(new_full_text)

            idx = self._current_chapter_index

            # 加载原有 meta，保留其它字段（评估、大纲 等）
            meta = {}
            if self.pipeline.project_dir:
                meta = load_chapter(self.pipeline.project_dir, idx) or {}

            meta["chapter_index"] = idx
            meta["title"] = title or meta.get("title", f"第{idx}章")
            meta["content"] = content
            meta["word_count"] = len(content)
            meta["manually_edited"] = True          # 标记：后续修订应保留
            meta["manually_edited_at"] = __import__("time").strftime(
                "%Y-%m-%d %H:%M:%S")

            if self.pipeline.project_dir:
                save_chapter(self.pipeline.project_dir, idx, meta)

            # 同步更新内存中的 pipeline.chapters（让统计/导出生效）
            for ch in self.pipeline.chapters:
                if ch.get("chapter_index") == idx:
                    ch.update(meta)
                    break
            else:
                self.pipeline.chapters.append(meta)

            # 重置脏状态
            self._original_content = f"【{meta['title']}】\n\n{content}"
            self._is_dirty = False
            self.save_btn.setEnabled(False)
            self.edited_badge.setText("已手动编辑")
            self.edited_badge.setVisible(True)

            # 章节列表里加个 (已编辑) 提示
            self._update_chapter_list_edited_flag(idx, edited=True)

            QMessageBox.information(
                self, "保存成功",
                f"第 {idx} 章已保存（{len(content):,} 字）。\n"
                "导出时会使用修订后的正文；后续 AI 修订也将跳过此章。"
            )
        except Exception as e:
            QMessageBox.warning(self, "保存失败", f"保存出错：{e}")

    @staticmethod
    def _split_title_content(full_text: str):
        """从 '【标题】\n\n正文' 里拆出 (title, body)。"""
        text = full_text.lstrip()
        if text.startswith("【"):
            end = text.find("】")
            if 0 < end < 40:
                title = text[1:end].strip()
                body = text[end + 1:].lstrip("\n")
                return title, body
        # 没有标题行：沿用原标题
        return "", text

    def _maybe_prompt_save(self, action_name: str) -> bool:
        """如果有未保存的改动，弹确认。返回 True 表示可以继续。"""
        if not self._is_dirty or self._current_chapter_index is None:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("未保存的修改")
        box.setText(
            f"第 {self._current_chapter_index} 章有尚未保存的修改。"
            f"要{a_name := action_name}吗？")
        box.setInformativeText("选择「保存」后再切换，或直接「丢弃」。")
        save_btn = box.addButton("保存", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("丢弃", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            self._save_current_chapter()
            return True
        if clicked == discard_btn:
            return True
        return False

    def _update_chapter_list_edited_flag(self, index, edited: bool):
        """在章节列表对应项后追加 '(已编辑)' 标记。"""
        for row in range(self.chapter_list.count()):
            item = self.chapter_list.item(row)
            if self._chapter_sort_key(
                    item.data(Qt.ItemDataRole.UserRole)) == \
                    self._chapter_sort_key(index):
                text = item.text()
                marker = "（已编辑）"
                has_marker = marker in text
                if edited and not has_marker:
                    item.setText(text + marker)
                elif not edited and has_marker:
                    item.setText(text[: -len(marker)])
                return

    def clear_all(self):
        """清空上一项目的残留显示（切换项目前调用）"""
        if self._is_dirty and self._current_chapter_index is not None:
            if not self._maybe_prompt_save("清空项目"):
                return
        self.world_view_display.clear()
        self.chapter_list.clear()
        self.content_display.clear()
        self.export_txt_btn.setEnabled(False)
        self.export_md_btn.setEnabled(False)
        self.stats_label.setText("暂无数据")
        self._current_chapter_index = None
        self._original_content = ""
        self._is_dirty = False
        self.save_btn.setEnabled(False)
        self.edited_badge.setVisible(False)

    def refresh_all(self):
        if self.pipeline.project_dir:
            world_view = load_world_view(self.pipeline.project_dir)
            if world_view:
                self.world_view_display.setPlainText(
                    self._format_world_view(world_view))
                self.export_txt_btn.setEnabled(True)
                self.export_md_btn.setEnabled(True)

            chapters = load_all_chapters(self.pipeline.project_dir)
            self.chapter_list.clear()
            for ch in chapters:
                title = ch.get("title", "")
                index = ch.get("chapter_index", 0)
                word_count = ch.get("word_count", 0)
                item = QListWidgetItem(
                    f"第{index}章 - {title} ({word_count}字)")
                item.setData(Qt.ItemDataRole.UserRole, index)
                self.chapter_list.addItem(item)
            self._update_stats()

    def _update_stats(self):
        count = self.chapter_list.count()
        total_words = 0
        if self.pipeline.chapters:
            total_words = sum(c.get("word_count", 0)
                              for c in self.pipeline.chapters)
        self.stats_label.setText(f"共 {count} 章 | 总计 {total_words:,} 字")

    def _format_world_view(self, world_view_data=None, **kwargs) -> str:
        wv = world_view_data or kwargs.get('world_view', {})
        if not wv:
            return ""

        lines = []
        lines.append(f"《{wv.get('title', '未命名')}》")
        lines.append(f"类型: {wv.get('genre', '未知')}")
        lines.append("")
        lines.append("【简介】")
        lines.append(wv.get("summary", ""))
        lines.append("")

        wv_detail = wv.get("world_view", {})
        if wv_detail:
            lines.append(f"【时代背景】{wv_detail.get('era', '')}")
            lines.append(f"【地理环境】{wv_detail.get('location', '')}")
            lines.append(f"【世界规则】{wv_detail.get('rules', '')}")
            lines.append(
                f"【主要势力】{', '.join(wv_detail.get('factions', []))}")
            lines.append(f"【历史背景】{wv_detail.get('history', '')}")
            lines.append("")

        characters = wv.get("characters", [])
        if characters:
            lines.append("【主要角色】")
            for char in characters:
                lines.append(
                    f"  • {char.get('name', '')}（{char.get('role', '')}）：{char.get('desc', '')}"
                )
            lines.append("")

        story = wv.get("story_framework", {})
        if story:
            lines.append("【故事框架】")
            lines.append(f"  开端: {story.get('premise', '')}")
            lines.append(f"  冲突: {story.get('conflict', '')}")
            lines.append(f"  高潮: {story.get('climax', '')}")
            lines.append(f"  结局: {story.get('ending_type', '')}")

        return "\n".join(lines)

    def _export_txt(self):
        if not self.pipeline.project_dir:
            QMessageBox.warning(self, "提示", "暂无可导出的内容")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出TXT", "novel.txt", "Text Files (*.txt)"
        )
        if path:
            if export_to_txt(self.pipeline.project_dir, path):
                QMessageBox.information(
                    self, "导出成功", f"已导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "内容为空或导出出错")

    def _export_markdown(self):
        if not self.pipeline.project_dir:
            QMessageBox.warning(self, "提示", "暂无可导出的内容")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出Markdown", "novel.md", "Markdown Files (*.md)"
        )
        if path:
            if export_to_markdown(self.pipeline.project_dir, path):
                QMessageBox.information(
                    self, "导出成功", f"已导出到:\n{path}")
            else:
                QMessageBox.warning(self, "导出失败", "内容为空或导出出错")


class _AppleInset(QWidget):
    """Apple 风格凹陷容器 — 浅灰底 + 细边框，内含 inner_layout。"""
    def __init__(self, radius=12, parent=None):
        super().__init__(parent)
        self._radius = radius
        self.setMinimumWidth(160)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            _AppleInset {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER};
                border-radius: {radius}px;
            }}
        """)
        self._inner = QVBoxLayout(self)
        self._inner.setContentsMargins(14, 14, 14, 14)
        self._inner.setSpacing(0)

    def inner_layout(self):
        return self._inner
