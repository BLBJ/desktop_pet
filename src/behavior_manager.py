"""
行为管理器 - BehaviorManager
宠物的"大脑"：管理状态机、移动逻辑、动作切换定时器。
The pet's "brain": state machine, movement logic, action-switch timers.
"""

import random
import math
import enum
from typing import List, Optional, Tuple

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .animation_manager import AnimationManager
from .config_manager import ConfigManager
from .utils import get_available_rect_for_pet, clamp


class PetState(enum.Enum):
    """宠物状态枚举。"""
    IDLE = "idle"           # 待机
    WALKING = "walk"        # 走路
    SLEEPING = "sleep"      # 睡觉
    JUMPING = "jump"        # 跳跃
    DAZING = "daze"         # 发呆
    INTERACTING = "interacting"  # 互动（点击触发）


class BehaviorManager(QObject):
    """
    行为管理器。
    - 管理宠物状态机（待机/走路/睡觉/跳跃/发呆/互动）
    - 控制动画帧推进、动作随机切换、位置移动
    - 通过 Qt 信号与 UI 层通信
    """

    # ---- 信号 ----
    frame_changed = pyqtSignal(object)     # 发出当前帧 QPixmap
    position_changed = pyqtSignal(int, int)  # 发出新位置 (x, y)
    action_changed = pyqtSignal(str)       # 发出动作名称

    def __init__(
        self,
        config: ConfigManager,
        animation_manager: AnimationManager,
    ):
        """
        Args:
            config: 配置管理器
            animation_manager: 动画管理器
        """
        super().__init__()

        self._config = config
        self._anim = animation_manager

        # ---- 状态 ----
        self._state: PetState = PetState.IDLE
        self._prev_state: PetState = PetState.IDLE  # 用于互动后恢复
        self._current_action: str = "idle"
        self._current_frame: int = 0

        # ---- 位置 & 移动 ----
        self._x: int = config.get_start_position()[0]
        self._y: int = config.get_start_position()[1]
        self._walk_speed: int = config.get_walk_speed()
        self._direction: float = random.uniform(0, 2 * math.pi)  # 弧度
        self._pet_size: Tuple[int, int] = (128, 128)

        # ---- 暂停标志 ----
        self._paused: bool = False

        # ---- 互动的动作名 ----
        self._interaction_action: str = "happy"

        # ---- 定时器 ----
        self._frame_timer = QTimer(self)
        self._frame_timer.timeout.connect(self._on_frame_tick)

        self._action_timer = QTimer(self)
        self._action_timer.timeout.connect(self._on_action_tick)

        self._move_timer = QTimer(self)
        self._move_timer.timeout.connect(self._on_move_tick)

        # 睡眠/跳跃等有持续时间的动作使用一次性定时器
        self._return_timer = QTimer(self)
        self._return_timer.setSingleShot(True)
        self._return_timer.timeout.connect(self._on_return_from_timed_action)

        # 互动冷却定时器
        self._interaction_cooldown_timer = QTimer(self)
        self._interaction_cooldown_timer.setSingleShot(True)
        self._interaction_cooldown_timer.timeout.connect(self._on_interaction_done)

    # ============================================================
    #  启动 / 停止 / 暂停
    # ============================================================

    def start(self) -> None:
        """启动所有定时器，宠物开始活动。"""
        available = self._anim.all_action_names()
        if not available:
            print("[BehaviorManager] [ERROR] No available sprites! Pet cannot start.")
            return

        # 初始状态：优先 idle，否则用第一个可用动作
        if 'idle' in available:
            self._state = PetState.IDLE
        else:
            # 用第一个可用动作当 idle
            self._state = PetState.IDLE
        self._current_action = self._resolve_action(self._state.value)

        fps = self._anim.get_fps()
        frame_interval = int(1000 / fps)

        self._frame_timer.start(frame_interval)
        self._move_timer.start(16)  # ~60 FPS 平滑移动
        self._schedule_next_action()

        # 发出初始帧
        self._emit_current_frame()

    def stop(self) -> None:
        """停止所有定时器。"""
        self._frame_timer.stop()
        self._action_timer.stop()
        self._move_timer.stop()
        self._return_timer.stop()
        self._interaction_cooldown_timer.stop()

    def pause(self) -> None:
        """暂停宠物活动（隐藏时调用）。"""
        self._paused = True
        self._frame_timer.stop()
        self._action_timer.stop()
        self._move_timer.stop()

    def resume(self) -> None:
        """恢复宠物活动（显示时调用）。"""
        self._paused = False
        self._frame_timer.start(int(1000 / self._anim.get_fps()))
        self._move_timer.start(16)
        self._schedule_next_action()

    # ============================================================
    #  帧推进
    # ============================================================

    def _resolve_action(self, preferred: str) -> str:
        """
        解析动作名。优先使用 preferred，如果素材不存在则用第一个可用动作。
        确保无论如何都有一个能用的动画。
        """
        if self._anim.has_action(preferred):
            return preferred
        available = self._anim.all_action_names()
        if available:
            return available[0]
        return preferred  # 没有任何素材，保持原名（后续 frame_count=0 静默跳过）

    def _on_frame_tick(self) -> None:
        """每帧推进动画帧索引。"""
        if self._state == PetState.INTERACTING:
            action = self._interaction_action
        else:
            action = self._resolve_action(self._state.value)

        total = self._anim.frame_count(action)
        if total == 0:
            return

        self._current_frame = (self._current_frame + 1) % total

        # 非循环动画：播放完最后一帧后停在最后一帧
        action_cfg = self._anim.get_action_config(action)
        if not action_cfg.get('loop', True) and self._current_frame == total - 1:
            pass

        self._emit_current_frame()

    def _emit_current_frame(self) -> None:
        """获取当前帧 QPixmap 并发送信号。"""
        if self._state == PetState.INTERACTING:
            action = self._interaction_action
        else:
            action = self._resolve_action(self._state.value)

        pixmap = self._anim.get_frame(action, self._current_frame)
        if pixmap:
            self.frame_changed.emit(pixmap)

    # ============================================================
    #  动作切换
    # ============================================================

    def _schedule_next_action(self) -> None:
        """安排下一次随机动作切换（随机间隔）。"""
        min_sec, max_sec = self._config.get_action_interval_range()
        delay_ms = random.randint(min_sec * 1000, max_sec * 1000)
        self._action_timer.start(delay_ms)

    def _on_action_tick(self) -> None:
        """定时器触发 → 切换到新的随机动作。"""
        self._action_timer.stop()  # 单次触发后用 _schedule_next_action 重新设定

        if self._state in (PetState.SLEEPING, PetState.INTERACTING):
            # 正在执行无法中断的动作，跳过
            self._schedule_next_action()
            return

        new_state = self._pick_random_state()
        self._transition_to(new_state)
        self._schedule_next_action()

    # ---- 状态 ↔ 动作名 映射 ----

    def _state_to_action(self, state: PetState) -> str:
        """PetState → 动作名称字符串。"""
        return state.value

    def _action_to_state(self, action: str) -> PetState:
        """动作名称字符串 → PetState，未知则返回 IDLE。"""
        mapping = {
            'idle': PetState.IDLE, 'walk': PetState.WALKING,
            'sleep': PetState.SLEEPING, 'jump': PetState.JUMPING,
            'daze': PetState.DAZING,
        }
        return mapping.get(action, PetState.IDLE)

    def _available_states(self) -> List[PetState]:
        """返回当前有素材可用的 PetState 列表（不含 INTERACTING）。"""
        available_actions = set(self._anim.all_action_names())
        states = []
        for state in (PetState.IDLE, PetState.SLEEPING,
                       PetState.JUMPING, PetState.DAZING):
            if state.value in available_actions:
                states.append(state)
        return states

    def _pick_random_state(self) -> PetState:
        """
        从有素材的动作中按配置概率随机选择。
        不存在的动作自动排除，其概率分配给 idle。
        """
        available = self._available_states()
        if not available:
            return PetState.IDLE

        probs = self._config.get_action_probabilities()
        raw = {
            PetState.WALKING: probs.get('walk', 0.35),
            PetState.SLEEPING: probs.get('sleep', 0.1),
            PetState.JUMPING: probs.get('jump', 0.15),
            PetState.DAZING: probs.get('daze', 0.2),
        }

        # 只保留可用动作的权重
        filtered = {s: raw.get(s, 0.0) for s in available if s != PetState.IDLE}
        total = sum(filtered.values())

        # idle 拿剩余概率
        if PetState.IDLE in available:
            filtered[PetState.IDLE] = max(0.0, 1.0 - total)
        else:
            # 没有 idle 素材 → 归一化
            if total > 0:
                filtered = {s: w / total for s, w in filtered.items()}

        # 加权随机
        choice = random.random()
        cumulative = 0.0
        for state, weight in filtered.items():
            cumulative += weight
            if choice < cumulative:
                return state

        # 兜底：返回第一个可用状态
        return available[0]

    def _transition_to(self, new_state: PetState) -> None:
        """
        状态转换：处理旧状态退出 + 新状态进入。
        """
        old_state = self._state

        # 退出旧状态
        self._return_timer.stop()

        # 进入新状态
        self._state = new_state
        self._prev_state = old_state
        self._current_frame = 0  # 重置帧索引

        self.action_changed.emit(new_state.value)

        # ---- 特殊状态处理 ----
        if new_state == PetState.WALKING:
            # 随机选择方向
            self._direction = random.uniform(0, 2 * math.pi)

        elif new_state == PetState.SLEEPING:
            # 睡觉持续固定时间后自动醒来
            sleep_cfg = self._anim.get_action_config('sleep')
            duration = sleep_cfg.get('duration', 5)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))

        elif new_state == PetState.JUMPING:
            # 跳跃结束自动回到待机
            jump_frames = self._anim.frame_count('jump')
            fps = self._anim.get_fps()
            duration_ms = int((jump_frames / fps) * 1000)
            self._return_timer.start(duration_ms)

        self._emit_current_frame()

    def _on_return_from_timed_action(self) -> None:
        """限时动作结束 → 回到 idle。"""
        if self._state in (PetState.SLEEPING, PetState.JUMPING, PetState.DAZING):
            self._transition_to(PetState.IDLE)

    # ============================================================
    #  移动逻辑
    # ============================================================

    def _on_move_tick(self) -> None:
        """每帧更新宠物位置（仅在 WALKING 状态下移动）。"""
        if self._state != PetState.WALKING:
            return

        # 更新宠物尺寸（用于边界检测），用任意可用帧
        any_frame = self._anim.get_frame('idle', 0)
        if any_frame is None:
            # idle 不存在则取第一个可用动作的第一帧
            available = self._anim.all_action_names()
            if available:
                any_frame = self._anim.get_frame(available[0], 0)
        if any_frame:
            scale = self._config.get_pet_scale()
            self._pet_size = (
                int(any_frame.width() * scale),
                int(any_frame.height() * scale),
            )

        pw, ph = self._pet_size

        # 计算移动距离
        speed = self._walk_speed
        dx = speed * math.cos(self._direction)
        dy = speed * math.sin(self._direction)

        new_x = int(self._x + dx)
        new_y = int(self._y + dy)

        # 边界检测与反弹
        bounds = get_available_rect_for_pet(new_x, new_y, pw, ph)
        min_x, min_y, max_x, max_y = bounds

        bounced = False

        if new_x <= min_x:
            new_x = min_x
            self._direction = math.pi - self._direction  # 水平反弹
            bounced = True
        elif new_x >= max_x:
            new_x = max_x
            self._direction = math.pi - self._direction
            bounced = True

        if new_y <= min_y:
            new_y = min_y
            self._direction = -self._direction  # 垂直反弹
            bounced = True
        elif new_y >= max_y:
            new_y = max_y
            self._direction = -self._direction
            bounced = True

        # 随机小幅方向漂移（让行走更自然）
        if not bounced and random.random() < 0.02:
            self._direction += random.uniform(-0.3, 0.3)

        # 确保方向在 [0, 2π)
        self._direction %= (2 * math.pi)

        self._x = new_x
        self._y = new_y
        self.position_changed.emit(new_x, new_y)

    # ============================================================
    #  交互触发
    # ============================================================

    def trigger_interaction(self, action: str = "happy") -> None:
        """
        触发互动动作（由鼠标点击调用）。

        Args:
            action: 要播放的互动动作名称 (happy/jump)
        """
        if not self._anim.has_action(action):
            # 尝试备选：从配置的 click_actions 中找第一个可用的
            available_interact = [
                a for a in self._config.get_interaction_config().get('click_actions', ['happy', 'jump'])
                if self._anim.has_action(a)
            ]
            if available_interact:
                action = available_interact[0]
            else:
                return  # 没有任何可用互动动作，直接忽略点击

        self._prev_state = self._state
        self._state = PetState.INTERACTING
        self._interaction_action = action
        self._current_frame = 0

        self.action_changed.emit(action)
        self._emit_current_frame()

        total_frames = self._anim.frame_count(action)
        fps = self._anim.get_fps()
        duration_ms = max(500, int((total_frames / fps) * 1000))

        self._action_timer.stop()
        self._interaction_cooldown_timer.start(duration_ms)

    def _on_interaction_done(self) -> None:
        """互动动画结束 → 恢复到之前的状态。"""
        self._state = self._prev_state
        self._current_frame = 0
        self.action_changed.emit(self._state.value)
        self._emit_current_frame()
        self._schedule_next_action()

    # ============================================================
    #  公共 setter
    # ============================================================

    def set_position(self, x: int, y: int) -> None:
        """手动设置宠物位置。"""
        self._x = x
        self._y = y

    def set_walk_speed(self, speed: int) -> None:
        """运行时修改行走速度。"""
        self._walk_speed = max(1, min(speed, 20))

    def current_state(self) -> PetState:
        """返回当前状态（供外部查询）。"""
        return self._state
