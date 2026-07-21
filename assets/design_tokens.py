"""
AI小说工厂 — 设计系统 Token v6
风格: Apple Light (macOS / iOS 浅色模式)
核心原则:
  - 极浅灰底色 #F5F5F7 全局统一 (Apple 系统背景)
  - 卡片 / 面板纯白 #FFFFFF + 轻投影
  - 强调色 Apple Blue #007AFF (系统蓝)
  - 文字深灰 #1D1D1F (替代纯黑)
  - 毛玻璃侧边栏 (浅灰半透明 + 细边框)
  - 无 emoji · 中文标签 · 圆角 10-16px
"""

# ===== 全局底色 (Apple 极浅灰) =====
BG_BASE       = "#F5F5F7"   # 页面底色 — 全局唯一背景色
BG_SIDEBAR    = "#EDEDF0"   # 侧边栏 (略深一阶, 毛玻璃感)
BG_RAISED     = "#FFFFFF"   # 浮起面 / 卡片底
BG_PRESSED    = "#E5E5EA"   # 按下/选中底
BG_INPUT      = "#F2F2F7"   # 输入框 / 凹陷面

# ===== 卡片 / 面板 (纯白 + 轻投影) =====
SURFACE       = "#FFFFFF"   # 卡片 / 面板
SURFACE_HOVER = "#FAFAFC"   # 卡片悬停

# ===== 强调色 (Apple System Blue) =====
ACCENT        = "#007AFF"   # Apple 系统蓝
ACCENT_HOVER  = "#0A84FF"   # 悬停亮一阶
ACCENT_DIM    = "#0066D6"   # 按下暗一阶
ACCENT_SOFT   = "#E8F0FE"   # 极浅背景 (标签、次态、选中行)
ACCENT_GLOW   = "#4DA3FF"   # 微辉光

# ===== 文字 (Apple 深灰层级) =====
TEXT_PRIMARY   = "#1D1D1F"   # 深灰黑 (Apple 主文字)
TEXT_SECONDARY = "#6E6E73"   # 中灰 (副标题)
TEXT_MUTED     = "#8E8E93"   # 浅灰 (辅助)
TEXT_DISABLED  = "#AEAEB2"   # 禁用
TEXT_INVERSE   = "#FFFFFF"   # 反白 (用于 accent 按钮)

# ===== 语义色 (Apple 系统色) =====
SUCCESS       = "#34C759"
SUCCESS_SOFT  = "#E8F8EC"
WARNING       = "#FF9F0A"
WARNING_SOFT  = "#FFF4E5"
DANGER        = "#FF3B30"
DANGER_SOFT   = "#FFECEB"
INFO          = "#5AC8FA"
INFO_SOFT     = "#E8F7FD"

# ===== Agent 状态色 =====
AGENT_IDLE     = "#AEAEB2"
AGENT_RUNNING  = "#007AFF"
AGENT_SUCCESS  = "#34C759"
AGENT_ERROR    = "#FF3B30"
AGENT_WAITING  = "#FF9F0A"

# ===== 边框 (Apple 细线分隔) =====
BORDER        = "#D1D1D6"   # 标准边框
BORDER_LIGHT  = "#E5E5EA"   # 浅边框
BORDER_INPUT  = "#C7C7CC"   # 输入框边框

# ===== 阴影 (轻投影 — Apple 卡片风格) =====
SHADOW_COLOR   = "#000000"   # 阴影色
SHADOW_ALPHA   = 0.06        # 很浅的投影
SHADOW_OFFSET  = 0           # 垂直偏移 (Apple 用正下方)
SHADOW_BLUR    = 12           # 模糊半径
SHADOW_Y       = 2            # 垂直偏移量

# 强一点的投影 (弹窗 / 浮层)
SHADOW_STRONG_ALPHA  = 0.12
SHADOW_STRONG_BLUR   = 24
SHADOW_STRONG_Y      = 4

# ===== 间距 (Apple 8pt 网格) =====
XS  = 4
SM  = 8
MD  = 12
LG  = 16
XL  = 24
XXL = 32

# ===== 圆角 (Apple 标准) =====
RADIUS_XS = 4
RADIUS_SM = 8
RADIUS_MD = 10      # 按钮 / 输入框
RADIUS_LG = 14      # 卡片
RADIUS_XL = 20      # 大面板
RADIUS_PILL = 999

# ===== 字体 (Apple 系统字体栈) =====
FONT_SYSTEM = '-apple-system, "SF Pro Display", "SF Pro Text", "Inter", "Segoe UI", "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif'
FONT_MONO   = '"SF Mono", "JetBrains Mono", "Cascadia Code", "Consolas", monospace'


def rgba(hex_color, alpha):
    """辅助: 将 hex 颜色 + alpha 转为 rgba() 字符串。"""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"
