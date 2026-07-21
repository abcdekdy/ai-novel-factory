"""
毛玻璃辅助 (v7.3) — 已弃用, 保留文件避免 import 错误。
当前版本使用 Apple Light 实心风格, 不依赖任何透明/模糊 API。
"""

def enable_acrylic(widget, tint_abgr=0x01000000):
    return False

def enable_blurbehind(widget):
    return False

def disable_blur_behind(widget):
    pass

def grab_desktop_behind(x, y, w, h):
    return None

def blur_pixmap(pixmap, radius=25):
    return pixmap
