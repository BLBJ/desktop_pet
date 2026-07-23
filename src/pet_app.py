"""
应用程序启动器 - PetApp
负责创建 QApplication、初始化各组件、连接信号。
Application bootstrap: creates QApplication, initializes components, wires signals.
"""

import sys
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from .config_manager import ConfigManager
from .animation_manager import AnimationManager
from .behavior_manager import BehaviorManager
from .pet_window import PetWindow


class PetApp:
    """
    桌面宠物应用程序。
    封装了 QApplication 生命周期管理和组件初始化。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Args:
            config_path: 配置文件路径，None 使用默认路径
        """
        # Qt6 默认启用高 DPI 缩放和 pixmap，无需额外设置
        self._app = QApplication(sys.argv)
        self._app.setApplicationName("DesktopPet")
        self._app.setOrganizationName("DesktopPet")
        self._app.setQuitOnLastWindowClosed(False)  # 托盘时不退出

        # ---- 加载配置 ----
        print("[PetApp] 加载配置文件...")
        self._config = ConfigManager(config_path)

        # ---- 动画管理器 ----
        print("[PetApp] 加载动画素材...")
        self._animation_manager = AnimationManager(self._config)

        # ---- 行为管理器 ----
        print("[PetApp] 初始化行为管理器...")
        self._behavior_manager = BehaviorManager(
            self._config, self._animation_manager
        )

        # ---- 宠物窗口 ----
        print("[PetApp] 创建宠物窗口...")
        self._pet_window = PetWindow(
            self._config,
            self._animation_manager,
            self._behavior_manager,
        )

    # ============================================================
    #  运行
    # ============================================================

    def run(self) -> int:
        """
        启动应用程序主循环。

        Returns:
            退出码（0 = 正常退出）
        """
        print(f"[PetApp] 启动桌面宠物: {self._config.get('pet.name', '小宠物')}")
        print("[PetApp] 提示: 右键点击宠物打开菜单，拖拽宠物移动位置")

        # 显示宠物
        self._pet_window.show()

        # 进入 Qt 事件循环
        exit_code = self._app.exec()

        print("[PetApp] 桌面宠物已退出")
        return exit_code

    # ============================================================
    #  公共属性
    # ============================================================

    @property
    def app(self) -> QApplication:
        return self._app

    @property
    def config(self) -> ConfigManager:
        return self._config

    @property
    def pet_window(self) -> PetWindow:
        return self._pet_window
