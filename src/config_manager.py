"""
配置管理器 - ConfigManager
负责加载、解析和保存 YAML 配置文件。
Configuration manager for loading, parsing and saving YAML config.
"""

import os
import sys
import yaml
from typing import Any, Dict, Optional


class ConfigManager:
    """配置管理器，负责读取和管理所有配置项。"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器。

        Args:
            config_path: 配置文件路径，为 None 时使用默认路径
        """
        self._config_path = config_path or self._default_config_path()
        self._config: Dict[str, Any] = {}
        self.load()

    # ---- 路径解析 ----

    def _default_config_path(self) -> str:
        """获取默认配置文件路径。
        开发环境：项目根目录的 config.yaml
        打包环境：可执行文件旁边的 config.yaml，回退到 bundle 内部
        """
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包环境：优先同目录，其次 bundle 内
            exe_dir = os.path.dirname(sys.executable)
            external_cfg = os.path.join(exe_dir, 'config.yaml')
            if os.path.exists(external_cfg):
                return external_cfg
            return os.path.join(sys._MEIPASS, 'config.yaml')  # type: ignore
        else:
            # 开发环境：项目根目录
            return os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config.yaml'
            )

    # ---- 加载 / 保存 ----

    def load(self) -> None:
        """从 YAML 文件加载配置。"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"[ConfigManager] 配置文件未找到: {self._config_path}，使用默认值。")
            self._config = self._defaults()

    def save(self) -> None:
        """将当前配置写回 YAML 文件。"""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    @staticmethod
    def _defaults() -> Dict[str, Any]:
        """返回硬编码默认配置（当配置文件加载失败时使用）。"""
        return {
            'pet': {'name': '小宠物', 'scale': 1.0, 'fps': 12},
            'window': {'always_on_top': True, 'start_position': [300, 300]},
            'behavior': {
                'walk_speed': 3,
                'action_interval_min': 5,
                'action_interval_max': 15,
                'sleep_probability': 0.1,
                'daze_probability': 0.2,
                'jump_probability': 0.15,
                'walk_probability': 0.35,
            },
            'animations': {
                'base_path': 'assets/default_pet',
                'actions': {
                    'idle': {'folder': 'idle', 'frame_count': 8, 'loop': True},
                    'walk': {'folder': 'walk', 'frame_count': 12, 'loop': True},
                    'sleep': {'folder': 'sleep', 'frame_count': 8, 'loop': True, 'duration': 5},
                    'jump': {'folder': 'jump', 'frame_count': 12, 'loop': False},
                    'daze': {'folder': 'daze', 'frame_count': 8, 'loop': True},
                    'happy': {'folder': 'happy', 'frame_count': 8, 'loop': False},
                    'angry': {'folder': 'angry', 'frame_count': 8, 'loop': False},
                }
            },
            'interaction': {
                'click_actions': ['happy', 'jump'],
                'click_cooldown': 2,
            }
        }

    # ---- 便捷 getter ----

    def get(self, key: str, default: Any = None) -> Any:
        """通用取值，支持点号分隔的嵌套 key（如 'pet.scale'）。"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """通用设值，支持点号分隔的嵌套 key。"""
        keys = key.split('.')
        target = self._config
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value

    # ---- 类型化 getter ----

    def get_pet_scale(self) -> float:
        return float(self.get('pet.scale', 1.0))

    def get_pet_fps(self) -> int:
        return int(self.get('pet.fps', 12))

    def get_window_always_on_top(self) -> bool:
        return bool(self.get('window.always_on_top', True))

    def get_start_position(self) -> list:
        pos = self.get('window.start_position', [300, 300])
        return [int(pos[0]), int(pos[1])]

    def get_walk_speed(self) -> int:
        return int(self.get('behavior.walk_speed', 3))

    def set_walk_speed(self, speed: int) -> None:
        """运行时修改走路速度并持久化。"""
        self.set('behavior.walk_speed', max(1, min(speed, 20)))
        self.save()

    def get_action_interval_range(self) -> tuple:
        """返回 (min_seconds, max_seconds) 动作切换间隔。"""
        return (
            int(self.get('behavior.action_interval_min', 5)),
            int(self.get('behavior.action_interval_max', 15)),
        )

    def get_action_probabilities(self) -> Dict[str, float]:
        """返回各动作的概率分布（不含 idle，idle 为剩余概率）。"""
        return {
            'walk': float(self.get('behavior.walk_probability', 0.35)),
            'sleep': float(self.get('behavior.sleep_probability', 0.1)),
            'daze': float(self.get('behavior.daze_probability', 0.2)),
            'jump': float(self.get('behavior.jump_probability', 0.15)),
        }

    def get_animation_config(self) -> Dict[str, Any]:
        return self.get('animations', {})

    def get_animation_base_path(self) -> str:
        return str(self.get('animations.base_path', 'assets/default_pet'))

    def set_animation_base_path(self, path: str) -> None:
        self.set('animations.base_path', path)
        self.save()

    def get_interaction_config(self) -> Dict[str, Any]:
        return self.get('interaction', {'click_actions': ['happy', 'jump'], 'click_cooldown': 2})

    @property
    def config(self) -> Dict[str, Any]:
        """直接访问完整配置字典。"""
        return self._config
