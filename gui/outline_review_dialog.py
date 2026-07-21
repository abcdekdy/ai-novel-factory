"""
续写大纲审阅对话框
========================================
模态对话框，展示续写大纲的每章详情（标题/剧情/关键事件/伏笔/章尾悬念），
用户可在线编辑；确认后把编辑过的大纲返回给 pipeline.confirm_continuation()。

Apple Design 风格 — 单列滚动卡片 + 凹陷输入区 + Apple Blue 主按钮。
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QScrollArea, QFrame, QDialogButtonBox,
    QGraphicsDropShadowEffect, QSizePolicy, QMessageBox, QApplication,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QCursor, QColor

from assets import design_tokens as dt


class OutlineReviewDialog(QDialog):
    """续写大纲审阅/编辑对话框 — 返回用户确认后的大纲 dict。"""

    def __init__(self, outline: dict, parent=None):
        super().__init__(parent)
        self.outline = outline
        self._chapter_editors = []   # 保存每章的编辑器引用，确认时回读
        self._resolved_editors = []  # 回收伏笔编辑器
        self._new_fs_editors = []    # 新增伏笔编辑器
        self._rules_editors = []     # 规则编辑器

        self.setWindowTitle("审阅续写大纲")
        self.setMinimumSize(880, 700)
        self.resize(980, 800)
        self._setup_ui()
        self._populate(outline)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(28, 24, 28, 20)

        # ---- 标题栏 ----
        header = QHBoxLayout()
        title = QLabel("审阅续写大纲")
        title.setFont(QFont(dt.FONT_SYSTEM, 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()

        # 批次/章节范围信息
        meta = self.outline.get("outline_meta", {})
        range_text = f"第 {meta.get('chapter_start', '?')}-{meta.get('chapter_end', '?')} 章"
        range_lbl = QLabel(range_text)
        range_lbl.setFont(QFont(dt.FONT_SYSTEM, 12))
        range_lbl.setStyleSheet(
            f"color: {dt.TEXT_SECONDARY}; background: {dt.BG_PRESSED};"
            f"border-radius: 10px; padding: 3px 12px;")
        header.addWidget(range_lbl)
        root.addLayout(header)

        # 续写指引（信息展示）
        guidance = self.outline.get("batch_guidance", "")
        if guidance:
            guide_lbl = QLabel(f"续写指引：{guidance}")
            guide_lbl.setFont(QFont(dt.FONT_SYSTEM, 12))
            guide_lbl.setStyleSheet(f"color: {dt.TEXT_MUTED}; padding: 0 2px;")
            guide_lbl.setWordWrap(True)
            root.addWidget(guide_lbl)

        # ---- 滚动区 ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ border: none; background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 6px; border-radius: 3px;
            }}
            QScrollBar::handle:vertical {{
                background: #C7C7CC; border-radius: 3px; min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #AEAEB2; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(14)
        self.cards_layout.setContentsMargins(6, 6, 14, 8)
        self.cards_layout.addStretch()
        self.scroll.setWidget(self.cards_container)
        root.addWidget(self.scroll, 1)

        # ---- 按钮栏 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(120, 40)
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
            QPushButton:hover {{
                background: {dt.BG_PRESSED};
                color: {dt.ACCENT};
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        confirm_btn = QPushButton("开始写章节")
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

    def _populate(self, outline: dict):
        """填充大纲内容到可编辑卡片。"""
        # 一致性规则区（信息 + 可追加）
        rules = outline.get("consistency_rules", [])
        if rules:
            rules_card = _SectionCard("一致性规则（只读旧规则，底部可追加新规则）")
            for i, r in enumerate(rules):
                lbl = QLabel(f"  {i+1}. {r}")
                lbl.setFont(QFont(dt.FONT_SYSTEM, 11))
                lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY};")
                lbl.setWordWrap(True)
                rules_card.add_widget(lbl)
            new_rule_edit = QTextEdit()
            new_rule_edit.setPlaceholderText("追加新规则（可为空）...")
            new_rule_edit.setFixedHeight(50)
            new_rule_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
            new_rule_edit.setStyleSheet(f"""
                QTextEdit {{
                    background: {dt.BG_INPUT};
                    border: 1px solid {dt.BORDER_INPUT};
                    border-radius: {dt.RADIUS_SM}px;
                    padding: 6px 10px;
                    color: {dt.TEXT_PRIMARY};
                }}
            """)
            rules_card.add_widget(new_rule_edit)
            self._rules_editors.append(new_rule_edit)
            self._insert_card(rules_card)

        # 回收伏笔区
        resolved = outline.get("resolved_foreshadowing", [])
        if resolved:
            resolved_card = _SectionCard(f"本次回收伏笔（{len(resolved)} 条）")
            for fs in resolved:
                idx = fs.get("from_chapter", "?")
                text = fs.get("foreshadowing", "")
                resolve_in = fs.get("resolved_in_chapter", "?")
                edit = QTextEdit()
                edit.setPlainText(f"第{idx}章：{text}\n→ 在第{resolve_in}章回收")
                edit.setFixedHeight(55)
                edit.setFont(QFont(dt.FONT_SYSTEM, 11))
                edit.setStyleSheet(f"""
                    QTextEdit {{
                        background: {dt.SUCCESS_SOFT};
                        border: 1px solid {dt.BORDER};
                        border-radius: {dt.RADIUS_SM}px;
                        padding: 6px 10px;
                        color: {dt.TEXT_PRIMARY};
                    }}
                """)
                resolved_card.add_widget(edit)
                self._resolved_editors.append(edit)
            self._insert_card(resolved_card)

        # 新增伏笔区
        new_fs = outline.get("new_foreshadowing", [])
        if new_fs:
            fs_card = _SectionCard(f"新增伏笔（{len(new_fs)} 条，后续批次回收）")
            for fs in new_fs:
                set_in = fs.get("set_in_chapter", "?")
                text = fs.get("foreshadowing", "")
                edit = QTextEdit()
                edit.setPlainText(f"第{set_in}章埋下：{text}")
                edit.setFixedHeight(50)
                edit.setFont(QFont(dt.FONT_SYSTEM, 11))
                edit.setStyleSheet(f"""
                    QTextEdit {{
                        background: {dt.INFO_SOFT};
                        border: 1px solid {dt.BORDER};
                        border-radius: {dt.RADIUS_SM}px;
                        padding: 6px 10px;
                        color: {dt.TEXT_PRIMARY};
                    }}
                """)
                fs_card.add_widget(edit)
                self._new_fs_editors.append(edit)
            self._insert_card(fs_card)

        # 章节卡片
        chapters = outline.get("chapters", [])
        for ch in chapters:
            chapter_card = self._build_chapter_card(ch)
            self._insert_card(chapter_card)

    def _build_chapter_card(self, chapter: dict) -> QFrame:
        """构建单章可编辑卡片。"""
        idx = chapter.get("chapter_index", "?")
        card = _SectionCard(f"第 {idx} 章")
        self._chapter_editors.append({})

        # 标题
        title_edit = QLineEdit(chapter.get("title", ""))
        title_edit.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        title_edit.setStyleSheet(f"""
            QLineEdit {{
                background: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {dt.RADIUS_SM}px;
                padding: 6px 10px;
                color: {dt.TEXT_PRIMARY};
                font-weight: 600;
            }}
        """)
        card.add_widget(title_edit)
        self._chapter_editors[-1]["title"] = title_edit

        # 详细剧情
        card.add_label("详细剧情：")
        plot_edit = QTextEdit()
        plot_edit.setPlainText(chapter.get("plot_detail", ""))
        plot_edit.setFixedHeight(110)
        plot_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
        plot_edit.setStyleSheet(self._editor_style())
        card.add_widget(plot_edit)
        self._chapter_editors[-1]["plot_detail"] = plot_edit

        # 关键事件
        card.add_label("关键事件（每行一个）：")
        events_text = "\n".join(chapter.get("key_events", []))
        events_edit = QTextEdit()
        events_edit.setPlainText(events_text)
        events_edit.setFixedHeight(65)
        events_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
        events_edit.setStyleSheet(self._editor_style())
        card.add_widget(events_edit)
        self._chapter_editors[-1]["key_events"] = events_edit

        # 出场人物
        card.add_label("出场人物（逗号分隔）：")
        chars_edit = QLineEdit("、".join(chapter.get("characters_present", [])))
        chars_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
        chars_edit.setStyleSheet(self._line_edit_style())
        card.add_widget(chars_edit)
        self._chapter_editors[-1]["characters_present"] = chars_edit

        # 章尾悬念
        card.add_label("章尾悬念：")
        cliff_edit = QLineEdit(chapter.get("cliffhanger", ""))
        cliff_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
        cliff_edit.setStyleSheet(self._line_edit_style())
        card.add_widget(cliff_edit)
        self._chapter_editors[-1]["cliffhanger"] = cliff_edit

        # 伏笔
        card.add_label("伏笔（每行一个）：")
        fs_text = "\n".join(chapter.get("foreshadowing", []))
        fs_edit = QTextEdit()
        fs_edit.setPlainText(fs_text)
        fs_edit.setFixedHeight(55)
        fs_edit.setFont(QFont(dt.FONT_SYSTEM, 11))
        fs_edit.setStyleSheet(self._editor_style())
        card.add_widget(fs_edit)
        self._chapter_editors[-1]["foreshadowing"] = fs_edit

        return card

    def _insert_card(self, card: QFrame):
        """把卡片插入 stretch 之前。"""
        self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

    def _on_confirm(self):
        """收集编辑后的数据，更新 self.outline，然后 accept。"""
        # 更新章节字段
        chapters = self.outline.get("chapters", [])
        for i, editors in enumerate(self._chapter_editors):
            if i >= len(chapters):
                break
            ch = chapters[i]
            ch["title"] = editors["title"].text().strip() or ch.get("title", "")
            ch["plot_detail"] = editors["plot_detail"].toPlainText().strip()
            # 关键事件：按行切割
            events_text = editors["key_events"].toPlainText().strip()
            ch["key_events"] = [e.strip() for e in events_text.splitlines() if e.strip()]
            # 出场人物：按中文顿号/逗号切割
            chars_text = editors["characters_present"].text().strip()
            if chars_text:
                import re
                ch["characters_present"] = [
                    c.strip() for c in re.split(r"[、,，]", chars_text) if c.strip()]
            else:
                ch["characters_present"] = []
            ch["cliffhanger"] = editors["cliffhanger"].text().strip()
            # 伏笔：按行切割
            fs_text = editors["foreshadowing"].toPlainText().strip()
            ch["foreshadowing"] = [f.strip() for f in fs_text.splitlines() if f.strip()]

        # 追加新规则
        for editor in self._rules_editors:
            new_rule = editor.toPlainText().strip()
            if new_rule:
                self.outline.setdefault("consistency_rules", [])
                if new_rule not in self.outline["consistency_rules"]:
                    self.outline["consistency_rules"].append(new_rule)

        # 更新 meta
        self.outline["outline_meta"]["total_chapters"] = len(chapters)

        self.accept()

    def get_reviewed_outline(self) -> dict:
        """返回审阅/编辑后的大纲。在 exec() 之后调用。"""
        return self.outline

    @staticmethod
    def _editor_style() -> str:
        return f"""
            QTextEdit {{
                background: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {dt.RADIUS_SM}px;
                padding: 6px 10px;
                color: {dt.TEXT_PRIMARY};
            }}
        """

    @staticmethod
    def _line_edit_style() -> str:
        return f"""
            QLineEdit {{
                background: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {dt.RADIUS_SM}px;
                padding: 6px 10px;
                color: {dt.TEXT_PRIMARY};
            }}
        """


# ----------------------------------------------------------------------
#  辅助 widget
# ----------------------------------------------------------------------
class _SectionCard(QFrame):
    """带标题组的卡片容器。"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(dt.SHADOW_COLOR); c.setAlphaF(dt.SHADOW_ALPHA)
        eff.setColor(c); eff.setOffset(0, dt.SHADOW_Y); eff.setBlurRadius(dt.SHADOW_BLUR)
        self.setGraphicsEffect(eff)
        self.setStyleSheet(f"""
            _SectionCard {{
                background-color: {dt.SURFACE};
                border: 1px solid {dt.BORDER_LIGHT};
                border-radius: {dt.RADIUS_LG}px;
            }}
        """)

        self._root = QVBoxLayout(self)
        self._root.setSpacing(8)
        self._root.setContentsMargins(18, 14, 18, 14)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        self._root.addWidget(title_lbl)

    def add_widget(self, widget):
        self._root.addWidget(widget)

    def add_label(self, text: str):
        lbl = QLabel(text)
        lbl.setFont(QFont(dt.FONT_SYSTEM, 11))
        lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY}; padding-top: 2px;")
        self._root.addWidget(lbl)
