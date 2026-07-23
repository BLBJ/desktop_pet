"""
宠物窗口 - PetWindow
无边框、置顶、透明背景的主窗口，可拖动，不抢焦点。
Borderless, always-on-top, transparent main window — draggable, no focus grab.
"""

import sys
from typing import Optional

from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QAction, QCursor
from PyQt6.QtWidgets import (
    QWidget, QMenu, QVBoxLayout, QApplication, QSlider,
    QWidgetAction, QLabel, QHBoxLayout, QSystemTrayIcon,
)

from .pet_widget import PetWidget
from .behavior_manager import BehaviorManager
from .animation_manager import AnimationManager
from .config_manager import ConfigManager
from .utils import is_windows, is_macos, get_available_rect_for_pet, clamp


class PetWindow(QWidget):
    """
    宠物主窗口。
    - 使用 Tool 窗口类型：不出现在任务栏/Alt+Tab
    - FramelessWindowHint：无标题栏和边框
    - WindowStaysOnTopHint：始终置顶
    - WA_TranslucentBackground：背景完全透明
    - 支持鼠标拖动、右键菜单、点击交互
    """

    # ---- 窗口提示消息的最小停留时间 ----
    HIDE_HINT_TIMEOUT = 2000  # 毫秒

    def __init__(
        self,
        config: ConfigManager,
        animation_manager: AnimationManager,
        behavior_manager: BehaviorManager,
    ):
        """
        Args:
            config: 配置管理器
            animation_manager: 动画管理器
            behavior_manager: 行为管理器（状态机+移动逻辑）
        """
        super().__init__(None)

        self._config = config
        self._animation_manager = animation_manager
        self._behavior_manager = behavior_manager
        self._scale = config.get_pet_scale()

        # 拖动状态
        self._dragging = False
        self._drag_offset = QPoint(0, 0)

        # 交互冷却
        self._click_cooldown_active = False

        # 系统托盘（用于隐藏后恢复）
        self._tray_icon: Optional[QSystemTrayIcon] = None

        # ---- 窗口设置 ----
        self._setup_window()

        # ---- 创建控件 ----
        self._pet_widget = PetWidget(scale=self._scale, parent=self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pet_widget)
        self.setLayout(layout)

        # ---- 连线（信号/槽） ----
        self._connect_signals()

        # ---- 初始位置 ----
        start_pos = config.get_start_position()
        self.move(start_pos[0], start_pos[1])

        # ---- 启动行为 ----
        self._behavior_manager.start()

    # ============================================================
    #  窗口设置
    # ============================================================

    def _setup_window(self) -> None:
        """配置无边框、置顶、透明窗口属性。"""
        # 窗口标志
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        # macOS 需要额外处理
        if is_macos():
            # 在 macOS 上，Tool 窗口不接收输入，用 SubWindow 替代但也要防止出现标题栏
            flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.SubWindow
            )

        self.setWindowFlags(flags)

        # 透明背景
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setStyleSheet("background: transparent;")

        # 不抢占焦点
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # 接受鼠标事件（用于拖动和点击）
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

    # ============================================================
    #  信号连接
    # ============================================================

    def _connect_signals(self) -> None:
        """连接 BehaviorManager 的信号到 PetWidget 和窗口。"""
        bm = self._behavior_manager

        # 帧更新 → 重绘
        bm.frame_changed.connect(self._on_frame_changed)

        # 位置更新 → 移动窗口
        bm.position_changed.connect(self._on_position_changed)

        # 动作变更 → 日志（供调试）
        bm.action_changed.connect(self._on_action_changed)

    def _on_frame_changed(self, pixmap) -> None:
        """收到新帧 → 交给 PetWidget 渲染。"""
        self._pet_widget.set_frame(pixmap)

    def _on_position_changed(self, x: int, y: int) -> None:
        """收到新位置 → 移动窗口。"""
        self.move(x, y)

    def _on_action_changed(self, action_name: str) -> None:
        """动作切换回调（可用于日志或额外 UI 反馈）。"""
        pass  # 可在此添加气泡提示等

    # ============================================================
    #  鼠标事件 — 拖动 & 点击交互
    # ============================================================

    def mousePressEvent(self, event) -> None:
        """鼠标按下：开始拖动 或 触发交互。"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 记录拖动起始偏移
            self._dragging = True
            self._drag_offset = event.position().toPoint()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # 右键交给 contextMenuEvent 处理
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        """鼠标移动：如果正在拖动则移动窗口。"""
        if self._dragging:
            # 全局位置 = 鼠标全局位置 - 拖拽偏移
            global_pos = event.globalPosition().toPoint()
            new_pos = global_pos - self._drag_offset
            self.move(new_pos)
            # 同步位置到行为管理器（防止自动移动被覆盖后又弹回）
            self._behavior_manager.set_position(new_pos.x(), new_pos.y())
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        """鼠标释放：如果是轻点（短距离拖动）则触发交互动作。"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 拖动距离很小 → 视为点击
            if self._dragging:
                press_pos = self._drag_offset
                release_pos = event.position().toPoint()
                delta = release_pos - press_pos
                if delta.manhattanLength() < 5:  # 移动小于 5 像素视为点击
                    self._on_click()
            self._dragging = False
            event.accept()

    def _on_click(self) -> None:
        """处理点击宠物：触发随机交互动作（受冷却时间限制）。"""
        if self._click_cooldown_active:
            return

        interaction_config = self._config.get_interaction_config()
        actions = interaction_config.get('click_actions', ['happy', 'jump'])
        cooldown = interaction_config.get('click_cooldown', 2)

        if actions:
            import random
            action = random.choice(actions)
            self._behavior_manager.trigger_interaction(action)

            # 冷却
            self._click_cooldown_active = True
            QTimer.singleShot(
                int(cooldown * 1000),
                self._clear_click_cooldown
            )

    def _clear_click_cooldown(self) -> None:
        """清除点击冷却标志。"""
        self._click_cooldown_active = False

    # ============================================================
    #  右键菜单
    # ============================================================

    def contextMenuEvent(self, event) -> None:
        """右键菜单：隐藏、大小、速度、退出。"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cccccc;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
        """)

        # ---- 隐藏/显示 ----
        hide_action = menu.addAction("隐藏宠物")
        hide_action.triggered.connect(self.hide_pet)

        # ---- 调整大小 ----
        scale_menu = menu.addMenu("调整大小")
        scale_slider_action = self._create_scale_slider()
        scale_menu.addAction(scale_slider_action)

        # ---- 调整速度 ----
        # speed_menu = menu.addMenu("移动速度")
        # speed_slider_action = self._create_speed_slider()
        # speed_menu.addAction(speed_slider_action)

        # ---- 开机自启 ----
        # auto_start_action = menu.addAction("开机自启")

        menu.addSeparator()

        # ---- 退出 ----
        exit_action = menu.addAction("退出")
        exit_action.triggered.connect(self.exit_app)

        menu.exec(event.globalPos())

    def _create_speed_slider(self) -> QWidgetAction:
        """创建速度调节滑块（嵌入菜单中）。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)

        label = QLabel("慢")
        label.setStyleSheet("font-size: 12px;")
        layout.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 20)
        slider.setValue(self._config.get_walk_speed())
        slider.setFixedWidth(120)
        slider.valueChanged.connect(self._on_speed_changed)
        layout.addWidget(slider)

        fast_label = QLabel("快")
        fast_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(fast_label)

        action = QWidgetAction(self)
        action.setDefaultWidget(widget)
        return action

    def _create_scale_slider(self) -> QWidgetAction:
        """创建大小调节滑块（嵌入菜单中）。"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)

        label = QLabel("小")
        label.setStyleSheet("font-size: 12px;")
        layout.addWidget(label)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(3, 30)  # 0.3x ~ 3.0x
        slider.setValue(int(self._scale * 10))
        slider.setFixedWidth(120)
        slider.valueChanged.connect(self._on_scale_changed)
        layout.addWidget(slider)

        big_label = QLabel("大")
        big_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(big_label)

        action = QWidgetAction(self)
        action.setDefaultWidget(widget)
        return action

    def _on_scale_changed(self, value: int) -> None:
        """大小滑块值变化回调。"""
        scale = value / 10.0  # 滑块值 3~30 → 0.3 ~ 3.0
        self._scale = scale
        self._pet_widget.set_scale(scale)
        self.adjustSize()
        self._config.set('pet.scale', scale)
        self._config.save()

    def _on_speed_changed(self, value: int) -> None:
        """速度滑块值变化回调。"""
        self._config.set_walk_speed(value)
        self._behavior_manager.set_walk_speed(value)

    # ============================================================
    #  隐藏 / 显示
    # ============================================================

    def hide_pet(self) -> None:
        """隐藏宠物窗口，创建系统托盘图标供恢复。"""
        if self._tray_icon is None:
            self._setup_tray_icon()
        self.hide()
        self._behavior_manager.pause()

    def show_pet(self) -> None:
        """显示宠物窗口，移除托盘图标。"""
        self.show()
        self._behavior_manager.resume()
        if self._tray_icon:
            self._tray_icon.hide()
            self._tray_icon = None

    def _setup_tray_icon(self) -> None:
        """创建系统托盘图标（最小恢复入口）。"""
        from PyQt6.QtGui import QIcon

        self._tray_icon = QSystemTrayIcon(self)

        # 尝试使用 idle 第一帧作为托盘图标
        idle_frame = self._animation_manager.get_frame('idle', 0)
        if idle_frame:
            self._tray_icon.setIcon(QIcon(idle_frame))
        else:
            self._tray_icon.setIcon(QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_ComputerIcon
            ))

        self._tray_icon.setToolTip("桌面宠物 - 点击恢复")
        self._tray_icon.activated.connect(self._on_tray_activated)

        # 托盘菜单
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示宠物")
        show_action.triggered.connect(self.show_pet)
        exit_action = tray_menu.addAction("退出")
        exit_action.triggered.connect(self.exit_app)
        self._tray_icon.setContextMenu(tray_menu)

        self._tray_icon.show()

    def _on_tray_activated(self, reason) -> None:
        """托盘图标被点击 → 恢复宠物。"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_pet()

    # ============================================================
    #  开机自启
    # ============================================================

    def _is_auto_start_enabled(self) -> bool:
        """检查是否已启用开机自启。"""
        if is_windows():
            return self._check_auto_start_windows()
        elif is_macos():
            return self._check_auto_start_macos()
        return False

    def _toggle_auto_start(self, enabled: bool) -> None:
        """切换开机自启状态。"""
        if is_windows():
            self._set_auto_start_windows(enabled)
        elif is_macos():
            self._set_auto_start_macos(enabled)

    def _check_auto_start_windows(self) -> bool:
        """检查 Windows 注册表中的开机自启项。"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, "DesktopPet")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except Exception:
            return False

    def _set_auto_start_windows(self, enabled: bool) -> None:
        """通过注册表设置 Windows 开机自启。"""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            if enabled:
                # 使用当前运行的 exe 路径
                import sys
                exe_path = sys.executable
                if getattr(sys, 'frozen', False):
                    target = f'"{exe_path}"'
                else:
                    target = f'"{sys.executable}" "{sys.argv[0]}"'
                winreg.SetValueEx(key, "DesktopPet", 0, winreg.REG_SZ, target)
            else:
                try:
                    winreg.DeleteValue(key, "DesktopPet")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[PetWindow] 开机自启设置失败 (Windows): {e}")

    def _check_auto_start_macos(self) -> bool:
        """检查 macOS LaunchAgent plist 是否存在。"""
        import os
        plist_path = os.path.expanduser(
            "~/Library/LaunchAgents/com.desktoppet.app.plist"
        )
        return os.path.exists(plist_path)

    def _set_auto_start_macos(self, enabled: bool) -> None:
        """创建或删除 macOS LaunchAgent plist。"""
        import os
        plist_dir = os.path.expanduser("~/Library/LaunchAgents")
        plist_path = os.path.join(plist_dir, "com.desktoppet.app.plist")

        if enabled:
            import sys
            os.makedirs(plist_dir, exist_ok=True)

            if getattr(sys, 'frozen', False):
                program_path = sys.executable
            else:
                program_path = sys.executable
                program_args = [os.path.abspath(sys.argv[0])]

            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.desktoppet.app</string>
    <key>Program</key>
    <string>{program_path}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>'''
            with open(plist_path, 'w', encoding='utf-8') as f:
                f.write(plist_content)
            print("[PetWindow] macOS 开机自启已启用")
        else:
            if os.path.exists(plist_path):
                os.remove(plist_path)
                print("[PetWindow] macOS 开机自启已禁用")

    # ============================================================
    #  退出
    # ============================================================

    def exit_app(self) -> None:
        """安全退出程序。"""
        self._behavior_manager.stop()
        if self._tray_icon:
            self._tray_icon.hide()
        QApplication.quit()

    # ============================================================
    #  关闭事件
    # ============================================================

    def closeEvent(self, event) -> None:
        """窗口关闭时停止行为管理器。"""
        self._behavior_manager.stop()
        super().closeEvent(event)
