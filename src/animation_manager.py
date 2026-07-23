"""
动画管理器 - AnimationManager
负责加载、缓存序列帧 PNG，并提供逐帧访问接口。
只加载磁盘上实际存在的素材文件夹，不存在的动作自动跳过。
Loads existing PNG sequence frames only; missing actions are silently skipped.
"""

import os
from typing import Dict, List, Optional

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap

from .config_manager import ConfigManager
from .utils import get_asset_path


class AnimationManager:
    """
    动画管理器。
    - 扫描素材目录，只加载实际存在的 PNG 序列帧
    - 没有素材的动作用 has_action() 返回 False，由行为管理器自动跳过
    - 提供按动作名和帧索引获取 QPixmap 的接口
    """

    def __init__(self, config: ConfigManager):
        """
        初始化并加载所有存在的动画帧。

        Args:
            config: ConfigManager 实例
        """
        self._config = config
        self._frames: Dict[str, List[QPixmap]] = {}   # {action_name: [QPixmap, ...]}
        self._fps: int = config.get_pet_fps()
        self._actions_config = config.get_animation_config().get('actions', {})

        base_path = get_asset_path(config.get_animation_base_path())
        self._load_all_frames(base_path, self._actions_config)

        if not self._frames:
            print("[AnimationManager] [WARN] No sprites found! Put PNG sequences in assets/ folder.")
        else:
            print(f"[AnimationManager] Loaded {len(self._frames)} actions: {list(self._frames.keys())}")

    # ---- 帧加载 ----

    def _load_all_frames(self, base_path: str, actions_config: dict) -> None:
        """
        加载所有动作的序列帧。
        文件夹不存在或为空 → 静默跳过，不生成占位帧。
        """
        for action_name, action_cfg in actions_config.items():
            folder = action_cfg.get('folder', action_name)
            folder_path = os.path.join(base_path, folder)

            frames = self._load_frames_from_folder(folder_path, action_name)
            if frames:
                self._frames[action_name] = frames

    def _load_frames_from_folder(
        self, folder_path: str, action_name: str
    ) -> List[QPixmap]:
        """
        从文件夹加载 PNG 序列帧。
        支持任意 PNG 文件名，按字母序排列。
        文件夹不存在或为空 → 返回空列表。
        """
        if not os.path.isdir(folder_path):
            print(f"[AnimationManager] [SKIP] '{action_name}' — folder not found: {folder_path}")
            return []

        # 收集所有 PNG 文件，按文件名排序
        png_files = sorted([
            f for f in os.listdir(folder_path)
            if f.lower().endswith('.png')
        ])

        if not png_files:
            print(f"[AnimationManager] [SKIP] '{action_name}' — folder is empty: {folder_path}")
            return []

        frames: List[QPixmap] = []
        for filename in png_files:
            filepath = os.path.join(folder_path, filename)
            pixmap = QPixmap(filepath)
            if pixmap.isNull():
                print(f"[AnimationManager] [WARN] Cannot load: {filepath}")
                continue
            frames.append(pixmap)

        if frames:
            print(f"[AnimationManager] [OK] '{action_name}': {len(frames)} frames <- {folder_path}")
        return frames

    # ---- 公共接口 ----

    def get_frame(self, action: str, index: int) -> Optional[QPixmap]:
        """
        获取指定动作的指定帧。

        Args:
            action: 动作名称
            index: 帧索引（自动循环）

        Returns:
            QPixmap 或 None
        """
        frames = self._frames.get(action)
        if not frames:
            return None
        return frames[index % len(frames)]

    def frame_count(self, action: str) -> int:
        """返回指定动作的总帧数。"""
        return len(self._frames.get(action, []))

    def get_fps(self) -> int:
        """返回动画帧率。"""
        return self._fps

    def get_default_size(self) -> QSize:
        """
        返回宠物默认尺寸。
        优先取 idle 第一帧，其次取第一个可用动作的第一帧，最后回退 128×128。
        """
        for action in ('idle',) + tuple(self._frames.keys()):
            frames = self._frames.get(action)
            if frames:
                return frames[0].size()
        return QSize(128, 128)

    def get_scaled_size(self, scale: float) -> QSize:
        """返回缩放后的宠物尺寸。"""
        base = self.get_default_size()
        return QSize(int(base.width() * scale), int(base.height() * scale))

    def all_action_names(self) -> List[str]:
        """返回所有已加载的动作名称列表。"""
        return list(self._frames.keys())

    def has_action(self, action: str) -> bool:
        """检查是否存在指定动作的动画。"""
        return action in self._frames

    def get_action_config(self, action: str) -> dict:
        """返回指定动作的配置。"""
        return self._actions_config.get(action, {})
