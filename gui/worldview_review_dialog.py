"""
世界观审阅对话框
========================================
模态对话框，在 pipeline 生成世界观后弹出，让用户审阅 / 编辑后再启动大纲生成。

可编辑字段：
- 书名、类型、简介
- 时代背景、地理环境、世界规则、主要势力、历史背景
- 主要角色列表（增/删/改姓名+身份+描述+能力）

这是第二个 HITL 检查点（第一个是续写大纲审查）。世界观一旦写偏，后面所有
章节与大纲都会废掉；这一步能把大错拦在最前面。

Apple Design 风格：单列滚动卡片 + 凹陷输入区 + Apple Blue 主按钮。
"""

from __future__ import annotations

import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QLineEdit, QPushButton, QScrollArea, QFrame, QMessageBox,
    QGraphicsDropShadowEffect, QSizePolicy, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QCursor, QColor

from assets import design_tokens as dt


class WorldViewReviewDialog(QDialog):
    """世界观审阅 / 编辑对话框 — 返回用户确认后的世界 view dict。"""

    def __init__(self, world_view: dict, parent=None):
        super().__init__(parent)
        # 深拷贝，避免外部在窗口打开期间被修改影响对话框
        self.world_view = self._deep_copy(world_view)
        self._char_editors: list[dict] = []
        self.setWindowTitle("审阅世界观")
        self.setMinimumSize(820, 680)
        self.resize(920, 800)
        self._setup_ui()
        self._populate(self.world_view)

    # ------------------------------------------------------------------
    #  UI
    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(28, 24, 28, 20)

        # ---- 标题栏 ----
        header = QHBoxLayout()
        title = QLabel("审阅世界观")
        title.setFont(QFont(dt.FONT_SYSTEM, 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {dt.TEXT_PRIMARY};")
        header.addWidget(title)
        header.addStretch()
        hint = QLabel("编辑后点击「确认并继续」，或「取消本次生成」")
        hint.setFont(QFont(dt.FONT_SYSTEM, 11))
        hint.setStyleSheet(f"color: {dt.TEXT_MUTED};")
        header.addWidget(hint)
        root.addLayout(header)

        # ---- 滚动区 ----
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 6px; }"
        )

        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(14)
        self.scroll_layout.setContentsMargins(4, 4, 16, 4)
        self.scroll_layout.addStretch()
        self.scroll.setWidget(self.scroll_content)
        root.addWidget(self.scroll, 1)

        # ---- 按钮栏 ----
        btns = QHBoxLayout()
        btns.addStretch()
        cancel_btn = QPushButton("取消本次生成")
        cancel_btn.setFixedSize(140, 38)
        cancel_btn.setFont(QFont(dt.FONT_SYSTEM, 12, QFont.Weight.Bold))
        cancel_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {dt.TEXT_SECONDARY}; "
            f"border: 1px solid {dt.BORDER}; border-radius: 8px; "
            f"padding: 6px 16px; }} "
            f"QPushButton:hover {{ background: {dt.BG_PRESSED}; }}")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        ok_btn = QPushButton("确认并继续")
        ok_btn.setFixedSize(140, 38)
        ok_btn.setFont(QFont(dt.FONT_SYSTEM, 12, QFont.Weight.Bold))
        ok_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        ok_btn.setStyleSheet(
            f"QPushButton {{ background: {dt.ACCENT}; color: white; "
            f"border: none; border-radius: 8px; padding: 6px 16px; }} "
            f"QPushButton:hover {{ background: {dt.ACCENT_HOVER}; }} "
            f"QPushButton:pressed {{ background: {dt.ACCENT_DIM}; }}")
        ok_btn.clicked.connect(self._on_confirm)
        btns.addWidget(ok_btn)
        root.addLayout(btns)

    # ------------------------------------------------------------------
    #  填充字段
    # ------------------------------------------------------------------
    def _populate(self, wv: dict):
        # 清理 stretch 之前的旧 widget
        while self.scroll_layout.count() > 1:
            item = self.scroll_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        # 1. 基本信息
        self._add_section("基本信息")
        self._title_edit = self._add_line_field(
            "书名", wv.get("title", ""))
        self._genre_edit = self._add_line_field(
            "类型", wv.get("genre", ""))
        self._summary_edit = self._add_text_field(
            "简介（200-300 字）", wv.get("summary", ""), min_lines=3)

        # 2. 世界观细节
        wv_detail = wv.get("world_view") or {}
        if not isinstance(wv_detail, dict):
            wv_detail = {}
        self._add_section("世界观细节")
        self._era_edit = self._add_line_field("时代背景", wv_detail.get("era", ""))
        self._location_edit = self._add_line_field(
            "地理环境", wv_detail.get("location", ""))
        self._rules_edit = self._add_text_field(
            "世界规则（绝对不能违反的铁律）",
            wv_detail.get("rules", ""), min_lines=2)
        factions = wv_detail.get("factions", [])
        self._factions_edit = self._add_line_field(
            "主要势力（用 / 分隔）",
            " / ".join(factions) if isinstance(factions, list) else str(factions))
        self._history_edit = self._add_text_field(
            "历史背景", wv_detail.get("history", ""), min_lines=2)

        # 3. 主要角色
        self._add_section("主要角色")
        characters = wv.get("characters", []) or []
        if not isinstance(characters, list):
            characters = []
        if not characters:
            # 角色列表为空时给一个空模板
            characters = [{}]
        chars_container = QFrame()
        chars_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        chars_container.setStyleSheet(
            f"background: {dt.BG_INPUT}; border: 1px solid {dt.BORDER}; "
            f"border-radius: {dt.RADIUS_MD}px;")
        self._chars_layout = QVBoxLayout(chars_container)
        self._chars_layout.setSpacing(8)
        self._chars_layout.setContentsMargins(12, 12, 12, 12)

        for char in characters:
            self._add_character_row(char or {})

        add_char_btn = QPushButton("+ 增加角色")
        add_char_btn.setFixedHeight(30)
        add_char_btn.setFont(QFont(dt.FONT_SYSTEM, 11))
        add_char_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        add_char_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {dt.ACCENT}; "
            f"border: 1px dashed {dt.ACCENT}; border-radius: 6px; }} "
            f"QPushButton:hover {{ background: {dt.ACCENT_SOFT}; }}")
        add_char_btn.clicked.connect(lambda: self._add_character_row({}))
        self._chars_layout.addWidget(add_char_btn)

        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1,
                                        chars_container)

    def _add_character_row(self, char: dict):
        """添加一行角色编辑区。"""
        row = QFrame()
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet(
            f"background: white; border: 1px solid {dt.BORDER_LIGHT}; "
            f"border-radius: {dt.RADIUS_SM}px;")
        lay = QVBoxLayout(row)
        lay.setSpacing(4)
        lay.setContentsMargins(10, 8, 10, 8)

        header = QHBoxLayout()
        header.addWidget(QLabel("角色"))
        header.addStretch()
        remove_btn = QPushButton("移除")
        remove_btn.setFixedSize(56, 24)
        remove_btn.setFont(QFont(dt.FONT_SYSTEM, 10))
        remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        remove_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {dt.DANGER}; "
            f"border: none; }} "
            f"QPushButton:hover {{ text-decoration: underline; }}")

        def _remove():
            self._char_editors.remove(editors)
            row.deleteLater()

        remove_btn.clicked.connect(_remove)
        header.addWidget(remove_btn)
        lay.addLayout(header)

        name_edit = QLineEdit(char.get("name", ""))
        name_edit.setPlaceholderText("姓名")
        name_edit.setStyleSheet(_line_style())
        lay.addWidget(name_edit)

        role_edit = QLineEdit(char.get("role", ""))
        role_edit.setPlaceholderText("身份/角色")
        role_edit.setStyleSheet(_line_style())
        lay.addWidget(role_edit)

        desc_edit = QLineEdit(char.get("desc", ""))
        desc_edit.setPlaceholderText("简短描述")
        desc_edit.setStyleSheet(_line_style())
        lay.addWidget(desc_edit)

        ability_edit = QLineEdit(char.get("ability", ""))
        ability_edit.setPlaceholderText("能力/功法/宝物")
        ability_edit.setStyleSheet(_line_style())
        lay.addWidget(ability_edit)

        editors = {
            "frame": row,
            "name": name_edit,
            "role": role_edit,
            "desc": desc_edit,
            "ability": ability_edit,
        }
        self._char_editors.append(editors)
        self._chars_layout.insertWidget(self._chars_layout.count() - 1, row)

    def _add_section(self, name: str):
        lbl = QLabel(name)
        lbl.setFont(QFont(dt.FONT_SYSTEM, 13, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {dt.TEXT_PRIMARY}; padding: 6px 2px 2px 2px;")
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, lbl)

    def _add_line_field(self, label: str, value: str) -> QLineEdit:
        frame = QFrame()
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(
            f"background: {dt.BG_INPUT}; border: 1px solid {dt.BORDER}; "
            f"border-radius: {dt.RADIUS_MD}px;")
        lay = QHBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lbl = QLabel(label)
        lbl.setFixedWidth(90)
        lbl.setFont(QFont(dt.FONT_SYSTEM, 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY}; border: none;")
        lay.addWidget(lbl)
        edit = QLineEdit(str(value))
        edit.setStyleSheet(_line_style())
        lay.addWidget(edit)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, frame)
        return edit

    def _add_text_field(self, label: str, value: str,
                        min_lines: int = 2) -> QTextEdit:
        frame = QFrame()
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        frame.setStyleSheet(
            f"background: {dt.BG_INPUT}; border: 1px solid {dt.BORDER}; "
            f"border-radius: {dt.RADIUS_MD}px;")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(4)
        lbl = QLabel(label)
        lbl.setFont(QFont(dt.FONT_SYSTEM, 11, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {dt.TEXT_SECONDARY}; border: none;")
        lay.addWidget(lbl)
        edit = QTextEdit()
        edit.setPlainText(str(value))
        line_h = 20
        edit.setMinimumHeight(line_h * min_lines + 24)
        edit.setStyleSheet(_text_style())
        lay.addWidget(edit)
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, frame)
        return edit

    # ------------------------------------------------------------------
    #  确认/取消
    # ------------------------------------------------------------------
    def _on_confirm(self):
        """校验必填字段 → 收集数据 → accept。"""
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "必填项", "请填写书名。")
            return
        summary = self._summary_edit.toPlainText().strip()
        if not summary:
            QMessageBox.warning(self, "必填项", "请填写简介。")
            return
        # 至少一个角色
        has_char = any(
            e["name"].text().strip() for e in self._char_editors)
        if not has_char:
            QMessageBox.warning(self, "必填项", "至少保留一个角色。")
            return

        # 回写数据
        self.world_view["title"] = title
        self.world_view["genre"] = self._genre_edit.text().strip()
        self.world_view["summary"] = summary

        wv_detail = self.world_view.setdefault("world_view", {})
        if not isinstance(wv_detail, dict):
            wv_detail = {}
            self.world_view["world_view"] = wv_detail
        wv_detail["era"] = self._era_edit.text().strip()
        wv_detail["location"] = self._location_edit.text().strip()
        wv_detail["rules"] = self._rules_edit.toPlainText().strip()
        factions_raw = self._factions_edit.text().strip()
        if factions_raw:
            wv_detail["factions"] = [
                f.strip() for f in re.split(r"[/／、,，]", factions_raw)
                if f.strip()
            ]
        else:
            wv_detail["factions"] = []
        wv_detail["history"] = self._history_edit.toPlainText().strip()

        # 角色
        new_chars = []
        for editors in self._char_editors:
            name = editors["name"].text().strip()
            if not name:
                continue
            new_chars.append({
                "name": name,
                "role": editors["role"].text().strip(),
                "desc": editors["desc"].text().strip(),
                "ability": editors["ability"].text().strip(),
            })
        self.world_view["characters"] = new_chars

        self.accept()

    def get_reviewed_world_view(self) -> dict:
        """在 exec() 之后调用，返回审阅 / 编辑后的世界观 dict。"""
        return self.world_view

    # ------------------------------------------------------------------
    #  静态工具
    # ------------------------------------------------------------------
    @staticmethod
    def _deep_copy(d: dict) -> dict:
        import copy
        try:
            return copy.deepcopy(d)
        except Exception:
            return dict(d)


def _line_style() -> str:
    return f"""
        QLineEdit {{
            background: white;
            border: 1px solid {dt.BORDER_INPUT};
            border-radius: {dt.RADIUS_SM}px;
            padding: 6px 10px;
            color: {dt.TEXT_PRIMARY};
            selection-background-color: {dt.ACCENT_SOFT};
        }}
        QLineEdit:focus {{ border: 1px solid {dt.ACCENT}; }}
    """


def _text_style() -> str:
    return f"""
        QTextEdit {{
            background: white;
            border: 1px solid {dt.BORDER_INPUT};
            border-radius: {dt.RADIUS_SM}px;
            padding: 8px 10px;
            color: {dt.TEXT_PRIMARY};
            selection-background-color: {dt.ACCENT_SOFT};
        }}
        QTextEdit:focus {{ border: 1px solid {dt.ACCENT}; }}
    """


def _drop_shadow():
    eff = QGraphicsDropShadowEffect()
    c = QColor(dt.SHADOW_COLOR)
    c.setAlphaF(dt.SHADOW_ALPHA)
    eff.setColor(c)
    eff.setOffset(0, dt.SHADOW_Y)
    eff.setBlurRadius(dt.SHADOW_BLUR)
    return eff
