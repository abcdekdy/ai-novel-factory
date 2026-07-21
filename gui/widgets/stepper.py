"""
AppleStepper — Apple 风格数值步进器。

替代 QSpinBox 那个臃肿的上下箭头，改用一体化药丸控件:

    [ − ]   5 章   [ + ]

视觉取自 iOS/macOS 步进器:  浅灰圆角药丸, 中间显示当前值, 左右两个圆形
± 按钮带 hover 高亮。到达上/下限时对应按钮自动置灰。

接口与 QSpinBox 兼容, 可直接替换:
    value() / setValue() / valueChanged / setRange() / setSingleStep() /
    setSuffix() / setMinimum() / setMaximum() / setFixedHeight() / setFont()
"""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

from assets import design_tokens as dt


# 使用标准减号符号与加号 (非 emoji, 是标点/数学符号)
_MINUS_GLYPH = "−"   # U+2212 减号
_PLUS_GLYPH  = "+"    # U+0002B 加号


class AppleStepper(QWidget):
    """Apple 风格步进器 — 药丸容器 + 圆形 ± 按钮 + 居中数值。"""

    valueChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._value = 0
        self._minimum = 0
        self._maximum = 99
        self._step = 1
        self._suffix = ""

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._build_ui()
        self._apply_style()
        self._refresh()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        margin_x = 3
        margin_y = 4
        self._root = QHBoxLayout(self)
        self._root.setContentsMargins(margin_x, margin_y, margin_x, margin_y)
        self._root.setSpacing(0)

        # 减号按钮 (左侧)
        self._btn_minus = QPushButton(_MINUS_GLYPH, self)
        self._btn_minus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_minus.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_minus.clicked.connect(self._step_down)

        # 数值标签 (中间, 自动拉伸)
        self._lbl_value = QLabel(self)
        self._lbl_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction)

        # 加号按钮 (右侧)
        self._btn_plus = QPushButton(_PLUS_GLYPH, self)
        self._btn_plus.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_plus.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._btn_plus.clicked.connect(self._step_up)

        self._root.addWidget(self._btn_minus)
        self._root.addWidget(self._lbl_value, 1)
        self._root.addWidget(self._btn_plus)

    def _apply_style(self):
        # 按钮尺寸: 跟随控件高度, 圆形 ± 按钮
        # 先按最小高度 36 计算, setFixedHeight 之后再刷新一次
        self._btn_size = 30
        self._btn_minus.setFixedSize(self._btn_size, self._btn_size)
        self._btn_plus.setFixedSize(self._btn_size, self._btn_size)

        radius = dt.RADIUS_MD
        btn_r = self._btn_size // 2

        self.setStyleSheet(f"""
            AppleStepper {{
                background-color: {dt.BG_INPUT};
                border: 1px solid {dt.BORDER_INPUT};
                border-radius: {radius}px;
            }}
            AppleStepper:hover {{
                border: 1px solid {dt.BORDER};
            }}
            QPushButton {{
                background-color: transparent;
                color: {dt.TEXT_PRIMARY};
                border: none;
                border-radius: {btn_r}px;
                font-size: 18px;
                font-weight: 600;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: {dt.BG_PRESSED};
                color: {dt.ACCENT};
            }}
            QPushButton:pressed {{
                background-color: {dt.BORDER};
                color: {dt.ACCENT_DIM};
            }}
            QPushButton:disabled {{
                color: {dt.TEXT_DISABLED};
                background-color: transparent;
            }}
        """)

    # 注意：不要在 resizeEvent 里根据 self.height() 动态调整按钮尺寸。
    # 那会制造无限循环：stepper 高度 H → 按钮设为 H-6 → layout 要求 stepper
    # 变高 → 高度变成 2H → 按钮再设为 2H-6 → ∞。
    # 按钮保持 _apply_style 里设定的固定尺寸即可。

    # ----------------------------------------------------------------  内部逻辑
    def _refresh(self):
        self._lbl_value.setText(f"{self._value}{self._suffix}")
        self._btn_minus.setEnabled(self._value > self._minimum)
        self._btn_plus.setEnabled(self._value < self._maximum)

    def _step_up(self):
        new_val = min(self._value + self._step, self._maximum)
        if new_val != self._value:
            self.setValue(new_val)

    def _step_down(self):
        new_val = max(self._value - self._step, self._minimum)
        if new_val != self._value:
            self.setValue(new_val)

    # ----------------------------------------------------------------  公开接口
    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        v = int(v)
        v = max(self._minimum, min(v, self._maximum))
        if v != self._value:
            self._value = v
            self.valueChanged.emit(v)
            self._refresh()

    def setRange(self, minimum: int, maximum: int):
        self._minimum = int(minimum)
        self._maximum = max(self._minimum, int(maximum))
        # 把当前值重新夹进新区间, 并刷新按钮状态
        clamped = max(self._minimum, min(self._value, self._maximum))
        changed = clamped != self._value
        self._value = clamped
        if changed:
            self.valueChanged.emit(self._value)
        self._refresh()

    def setMinimum(self, minimum: int):
        self.setRange(minimum, self._maximum)

    def setMaximum(self, maximum: int):
        self.setRange(self._minimum, maximum)

    def setSingleStep(self, step: int):
        self._step = max(1, int(step))

    def setSuffix(self, suffix: str):
        self._suffix = suffix
        self._refresh()

    def suffix(self) -> str:
        return self._suffix

    def setReadOnly(self, read_only: bool):
        self._btn_minus.setEnabled(not read_only and self._value > self._minimum)
        self._btn_plus.setEnabled(not read_only and self._value < self._maximum)
        self._lbl_value.setEnabled(not read_only)

    # setFont: 只应用到数值标签, 让字号与字重和原来一致
    def setFont(self, font: QFont):
        self._lbl_value.setFont(font)

    def minimum(self) -> int:
        return self._minimum

    def maximum(self) -> int:
        return self._maximum

    def singleStep(self) -> int:
        return self._step
