"""
工具函数模块 - 屏幕边界、平台检测、路径解析等通用辅助函数。
Utility functions: screen bounds, platform detection, path resolution.
"""

import os
import sys
from typing import List, Optional, Tuple

# ---- 平台检测 ----

def is_windows() -> bool:
    """是否为 Windows 系统。"""
    return sys.platform == 'win32'

def is_macos() -> bool:
    """是否为 macOS 系统。"""
    return sys.platform == 'darwin'

def is_linux() -> bool:
    """是否为 Linux 系统。"""
    return sys.platform.startswith('linux')

# ---- 路径解析 ----

def get_asset_path(relative_path: str) -> str:
    """
    解析素材路径，兼容开发环境和 PyInstaller 打包环境。

    Args:
        relative_path: 相对于项目根目录的路径，如 'assets/default_pet'

    Returns:
        绝对路径
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，资源文件解压到 sys._MEIPASS
        base = sys._MEIPASS  # type: ignore
    else:
        # 开发环境：项目根目录
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)


def get_config_dir() -> str:
    """
    获取用户配置目录（用于存放运行时可写文件，如日志、自定义配置）。
    Windows: %APPDATA%/DesktopPet
    macOS:   ~/Library/Application Support/DesktopPet
    """
    if is_windows():
        base = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(base, 'DesktopPet')
    elif is_macos():
        return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'DesktopPet')
    else:
        return os.path.join(os.path.expanduser('~'), '.config', 'DesktopPet')


# ---- 屏幕几何信息 ----

# 延迟导入 PyQt6 避免循环依赖
def _qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance()


def get_screen_rects() -> List[Tuple[int, int, int, int]]:
    """
    获取所有显示器的几何矩形。

    Returns:
        列表，每项为 (x, y, width, height)
    """
    app = _qapp()
    if app is None:
        return [(0, 0, 1920, 1080)]  # 默认回退

    rects = []
    for screen in app.screens():
        geo = screen.geometry()
        rects.append((geo.x(), geo.y(), geo.width(), geo.height()))
    return rects


def get_primary_screen_rect() -> Tuple[int, int, int, int]:
    """获取主显示器几何矩形。"""
    app = _qapp()
    if app is None:
        return (0, 0, 1920, 1080)
    screen = app.primaryScreen()
    if screen is None:
        return (0, 0, 1920, 1080)
    geo = screen.geometry()
    return (geo.x(), geo.y(), geo.width(), geo.height())


def get_screen_containing_point(x: int, y: int) -> Tuple[int, int, int, int]:
    """
    找到包含指定点的显示器几何矩形。
    如果没有找到，返回主显示器。
    """
    rects = get_screen_rects()
    for rx, ry, rw, rh in rects:
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return (rx, ry, rw, rh)
    return get_primary_screen_rect()


def get_available_rect_for_pet(
    pet_x: int, pet_y: int, pet_w: int, pet_h: int
) -> Tuple[int, int, int, int]:
    """
    获取宠物活动的有效矩形区域（考虑多显示器和屏幕边界）。
    返回 (min_x, min_y, max_x, max_y) 代表宠物左上角可移动范围。

    宠物完全在所有屏幕的并集中活动。
    """
    rects = get_screen_rects()
    if not rects:
        return (0, 0, 1920 - pet_w, 1080 - pet_h)

    min_x = min(r[0] for r in rects)
    min_y = min(r[1] for r in rects)
    max_x = max(r[0] + r[2] for r in rects) - pet_w
    max_y = max(r[1] + r[3] for r in rects) - pet_h

    return (min_x, max(0, min_y), max(min_x, max_x), max(min_y, max_y))


# ---- 通用辅助 ----

def clamp(value: int, lo: int, hi: int) -> int:
    """将值限制在 [lo, hi] 范围内。"""
    return max(lo, min(hi, value))
