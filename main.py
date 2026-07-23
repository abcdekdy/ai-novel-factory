"""
AI小说工厂 — 主入口
Apple Light UI  |  LongCat-2.0  |  Multi-Agent Pipeline

启动流程: LaunchWindow(入口) → MainWindow(工作台)
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.main_window import MainWindow
from gui.launch_window import LaunchWindow
from core.config import load_config


def start_web_monitor(port: int):
    """启动Web监控服务"""
    try:
        from web_monitor.server import start_server
        start_server(port=port, debug=False)
        print(f"[Monitor] http://localhost:{port}")
    except Exception as e:
        print(f"[Monitor] Error: {e}")


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("AI Novel Factory")
    app.setApplicationVersion("1.0.0")

    # 字体回退链：先西文后中文，确保中文方正
    font = QFont("Segoe UI", 11)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # 样式表由 MainWindow.apply_theme() 根据 config.json 主题动态生成并应用。
    # 不再加载静态 style.qss，避免与主题系统冲突。

    # 启动Web监控
    config = load_config()
    start_web_monitor(config.get("web_monitor_port", 5000))

    # === 启动窗口 → 主窗口 ===
    launch_win = LaunchWindow()
    main_win = MainWindow()

    launch_win.launched.connect(lambda: (launch_win.close(), main_win.show()))
    launch_win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
