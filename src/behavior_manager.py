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
    IDLE = "idle"
    WALKING = "walk"
    SLEEPING = "sleep"
    JUMPING = "jump"
    DAZING = "daze"
    LIEDOWN = "liedown"
    SPINNING = "spin"
    WALK_FORWARD = "walk_forward"
    BELLY = "belly"
    INVITE = "invite"             # 邀请玩耍
    WANJU = "wanju"               # 玩小玩具
    INTERACTING = "interacting"


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

        # ---- 头部追踪 ----
        htc = config.config.get('head_track', {})
        self._head_track_enabled = htc.get('enabled', False)
        self._head_track_action = htc.get('action', 'look')
        self._head_track_radius = htc.get('track_radius', 300)
        self._frame_angle_map: list[float] = []  # frame_index → angle(°)
        if self._head_track_enabled and self._anim.has_action(self._head_track_action):
            action_cfg = self._anim.get_action_config(self._head_track_action)
            self._build_angle_map(action_cfg)
        self._mouse_screen_x: int = 0
        self._mouse_screen_y: int = 0
        self._head_tracking_active: bool = False

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
        解析动作名。优先使用 preferred，素材不存在则用第一个可用动作。
        WALKING 状态根据方向自动选 walk_left / walk_right。
        """
        # 走路时根据方向选左/右素材
        if preferred == 'walk':
            import math
            # cos(方向) > 0 → 向右，< 0 → 向左
            action = 'walk_right' if math.cos(self._direction) > 0 else 'walk_left'
            if self._anim.has_action(action):
                return action
            # 素材只有一个方向时降级
            if self._anim.has_action('walk_right'):
                return 'walk_right'
            if self._anim.has_action('walk_left'):
                return 'walk_left'

        if self._anim.has_action(preferred):
            return preferred
        available = self._anim.all_action_names()
        if available:
            return available[0]
        return preferred

    def _on_frame_tick(self) -> None:
        """每帧推进动画帧索引。头部追踪激活时跳过帧推进。"""
        # 头部追踪中 → 帧由鼠标角度决定，跳过时间推进
        if self._head_tracking_active and self._state == PetState.IDLE:
            self._emit_current_frame()
            return

        if self._state == PetState.INTERACTING:
            action = self._interaction_action
        else:
            action = self._resolve_action(self._state.value)

        total = self._anim.frame_count(action)
        if total == 0:
            return

        # 非循环动画：停在最后一帧，不再前进；循环动画：取余继续
        action_cfg = self._anim.get_action_config(action)
        if not action_cfg.get('loop', True) and self._current_frame >= total - 1:
            return  # 已到最后一帧，停止更新

        self._current_frame = (self._current_frame + 1) % total

        self._emit_current_frame()

    def _emit_current_frame(self) -> None:
        """获取当前帧 QPixmap 并发送信号。空闲时若鼠标靠近，用头部追踪帧。"""
        if self._state == PetState.INTERACTING:
            action = self._interaction_action
        elif self._head_tracking_active and self._state == PetState.IDLE:
            # 头部追踪：按鼠标角度选帧
            angle_idx = self._angle_to_frame_index()
            pixmap = self._anim.get_frame(self._head_track_action, angle_idx)
            if pixmap:
                self.frame_changed.emit(pixmap)
            return
        else:
            action = self._resolve_action(self._state.value)

        pixmap = self._anim.get_frame(action, self._current_frame)
        if pixmap:
            self.frame_changed.emit(pixmap)

    def _build_angle_map(self, action_cfg: dict) -> None:
        """
        从关键帧配置构建帧→角度映射表（线性插值，顺时针方向）。
        angle_keyframes: {frame_index: angle_degrees, ...}
        """
        keyframes = action_cfg.get('angle_keyframes', {})
        total = self._anim.frame_count(self._head_track_action)
        if not keyframes:
            for i in range(total):
                self._frame_angle_map.append(i * 360.0 / total)
            return

        keys = sorted(keyframes.items())  # [(frame, angle), ...]

        # 展开角度确保单调递增（跨 0° 边界时加 360）
        unwrapped = {}
        prev_a = float(keys[0][1])
        unwrapped[keys[0][0]] = prev_a
        for f, a in keys[1:]:
            f, a = int(f), float(a)
            while a < prev_a:
                a += 360.0
            unwrapped[f] = a
            prev_a = a

        # 对每帧插值
        self._frame_angle_map = [0.0] * total
        kf = sorted(unwrapped.items())
        for i in range(total):
            if i <= kf[0][0]:
                self._frame_angle_map[i] = kf[0][1] % 360
            elif i >= kf[-1][0]:
                self._frame_angle_map[i] = kf[-1][1] % 360
            else:
                for k in range(len(kf) - 1):
                    f0, a0 = kf[k]
                    f1, a1 = kf[k + 1]
                    if f0 <= i <= f1:
                        t = (i - f0) / (f1 - f0) if f1 != f0 else 0
                        self._frame_angle_map[i] = (a0 + t * (a1 - a0)) % 360
                        break

    def _angle_to_frame_index(self) -> int:
        """根据鼠标角度，找 angle_map 中最接近的帧。"""
        if not self._frame_angle_map:
            return 0
        pet_cx = self._x + self._pet_size[0] // 2
        pet_cy = self._y + self._pet_size[1] // 2
        dx = self._mouse_screen_x - pet_cx
        dy = self._mouse_screen_y - pet_cy
        import math
        angle = math.degrees(math.atan2(-dy, dx))  # 0°=右, 顺时针增大
        if angle < 0:
            angle += 360

        # 找角度最接近的帧
        best_frame = 0
        best_dist = 999.0
        for i, fa in enumerate(self._frame_angle_map):
            dist = min(abs(angle - fa), 360 - abs(angle - fa))
            if dist < best_dist:
                best_dist = dist
                best_frame = i
        return best_frame

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

        if self._state in (PetState.SLEEPING, PetState.INTERACTING,
                            PetState.LIEDOWN, PetState.SPINNING, PetState.BELLY,
                            PetState.INVITE, PetState.WANJU):
            # 正在执行限时动作，跳过随机切换
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
            'idle': PetState.IDLE, 'walk_left': PetState.WALKING,
            'walk_right': PetState.WALKING,
            'sleep': PetState.SLEEPING, 'jump': PetState.JUMPING,
            'daze': PetState.DAZING, 'liedown': PetState.LIEDOWN,
            'spin': PetState.SPINNING, 'walk_forward': PetState.WALK_FORWARD,
            'belly': PetState.BELLY, 'invite': PetState.INVITE,
            'wanju': PetState.WANJU,
        }
        return mapping.get(action, PetState.IDLE)

    def _available_states(self) -> List[PetState]:
        """返回当前有素材可用的 PetState 列表（不含 INTERACTING）。IDLE 始终可用。"""
        available_actions = set(self._anim.all_action_names())
        states = [PetState.IDLE]
        for state in (PetState.WALKING, PetState.SLEEPING, PetState.JUMPING,
                       PetState.DAZING, PetState.SPINNING,
                       PetState.WALK_FORWARD, PetState.BELLY,
                       PetState.INVITE, PetState.WANJU):
            if state == PetState.WALKING:
                # walk_left 或 walk_right 任一存在即可走路
                if 'walk_left' in available_actions or 'walk_right' in available_actions:
                    states.append(state)
            elif state.value in available_actions:
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
            PetState.JUMPING: probs.get('jump', 0.1),
            PetState.DAZING: probs.get('daze', 0.1),
            PetState.LIEDOWN: probs.get('liedown', 0.1),
            PetState.SPINNING: probs.get('spin', 0.1),
            PetState.WALK_FORWARD: probs.get('walk_forward', 0.1),
            PetState.BELLY: probs.get('belly', 0.1),
            PetState.INVITE: probs.get('invite', 0.05),
            PetState.WANJU: probs.get('wanju', 0.05),
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
            # 纯水平方向：0=右, π=左
            self._direction = 0.0 if random.random() > 0.5 else math.pi

        elif new_state == PetState.SLEEPING:
            sleep_cfg = self._anim.get_action_config('sleep')
            duration = sleep_cfg.get('duration', 5)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))

        elif new_state in (PetState.JUMPING, PetState.SPINNING, PetState.BELLY,
                            PetState.INVITE, PetState.WANJU):
            cfg = self._anim.get_action_config(new_state.value)
            duration = cfg.get('duration', 0)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))
            else:
                frames = self._anim.frame_count(new_state.value)
                fps = self._anim.get_fps()
                self._return_timer.start(max(500, int((frames / fps) * 1000)))

        elif new_state == PetState.LIEDOWN:
            # 趴下持续 duration 秒后回 idle
            cfg = self._anim.get_action_config('liedown')
            duration = cfg.get('duration', 4)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))

        self._emit_current_frame()

    def _on_return_from_timed_action(self) -> None:
        """限时动作结束 → 回到 idle，并立即安排下一次动作。"""
        if self._state in (PetState.SLEEPING, PetState.JUMPING, PetState.DAZING,
                            PetState.LIEDOWN, PetState.SPINNING, PetState.BELLY,
                            PetState.INVITE, PetState.WANJU):
            self._transition_to(PetState.IDLE)
            self._schedule_next_action()

    # ============================================================
    #  移动逻辑
    # ============================================================

    def _on_move_tick(self) -> None:
        """水平行走：严格左右移动，不改变高度，碰到边界自动调头。"""
        if self._state != PetState.WALKING:
            return

        any_frame = self._anim.get_frame('idle', 0)
        if any_frame is None:
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
        speed = max(1, self._walk_speed)  # 速度（像素/帧）

        # 纯水平移动：dx = 速度 × 方向（左=-1, 右=+1）
        dx = speed if math.cos(self._direction) > 0 else -speed
        new_x = int(self._x + dx)
        new_y = self._y  # 高度不变

        bounds = get_available_rect_for_pet(new_x, new_y, pw, ph)
        min_x, _, max_x, _ = bounds

        # 碰到左右边界 → 调头 + 立即切换动画
        if new_x <= min_x:
            new_x = min_x
            self._direction = 0.0
            self._current_frame = 0
            self._emit_current_frame()
        elif new_x >= max_x:
            new_x = max_x
            self._direction = math.pi
            self._current_frame = 0
            self._emit_current_frame()

        self._x = new_x
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

        # 已经在互动中 → 只重置帧和动画，不覆盖 prev_state（防止卡死）
        if self._state == PetState.INTERACTING:
            self._interaction_action = action
            self._current_frame = 0
            self._interaction_cooldown_timer.stop()
        else:
            self._prev_state = self._state
            self._state = PetState.INTERACTING
            self._interaction_action = action
            self._current_frame = 0
            self.action_changed.emit(action)
            self._action_timer.stop()
            self._return_timer.stop()  # 停止睡眠/跳跃定时器

        self._emit_current_frame()

        total_frames = self._anim.frame_count(action)
        fps = self._anim.get_fps()
        duration_ms = max(500, int((total_frames / fps) * 1000))
        self._interaction_cooldown_timer.start(duration_ms)

    def _on_interaction_done(self) -> None:
        """互动动画结束 → 恢复到之前的状态。"""
        if self._state != PetState.INTERACTING:
            return
        self._state = self._prev_state
        self._current_frame = 0
        self.action_changed.emit(self._state.value)
        self._emit_current_frame()

        # 如果恢复到了限时状态，重新启动定时器
        if self._state == PetState.SLEEPING:
            sleep_cfg = self._anim.get_action_config('sleep')
            duration = sleep_cfg.get('duration', 5)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))
        elif self._state == PetState.LIEDOWN:
            cfg = self._anim.get_action_config('liedown')
            duration = cfg.get('duration', 4)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))
        elif self._state in (PetState.JUMPING, PetState.SPINNING, PetState.BELLY,
                              PetState.INVITE, PetState.WANJU):
            cfg = self._anim.get_action_config(self._state.value)
            duration = cfg.get('duration', 0)
            if duration > 0:
                self._return_timer.start(int(duration * 1000))
            else:
                frames = self._anim.frame_count(self._state.value)
                self._return_timer.start(max(500, int((frames / self._anim.get_fps()) * 1000)))

        self._schedule_next_action()

    # ============================================================
    #  公共 setter
    # ============================================================

    def set_position(self, x: int, y: int) -> None:
        """手动设置宠物位置。"""
        self._x = x
        self._y = y

    def set_mouse_position(self, screen_x: int, screen_y: int) -> None:
        """更新鼠标屏幕坐标，用于头部追踪。"""
        if not self._head_track_enabled:
            return
        self._mouse_screen_x = screen_x
        self._mouse_screen_y = screen_y
        # 判断鼠标是否在宠物附近
        pet_cx = self._x + self._pet_size[0] // 2
        pet_cy = self._y + self._pet_size[1] // 2
        import math
        dist = math.sqrt((screen_x - pet_cx)**2 + (screen_y - pet_cy)**2)
        was_active = self._head_tracking_active
        self._head_tracking_active = dist < self._head_track_radius
        # 进入或退出追踪时立即刷新帧
        if self._head_tracking_active != was_active:
            self._emit_current_frame()

    def play_action(self, action: str) -> None:
        """右键菜单触发：直接播放指定动作一次，播完回 idle。"""
        if not self._anim.has_action(action):
            return

        state = self._action_to_state(action)
        if state == PetState.IDLE and action not in ('idle',):
            # 非核心动作（如 happy/angry）→ 走互动通道
            self.trigger_interaction(action)
            return

        # 核心动作 → 直接切换
        self._action_timer.stop()
        self._return_timer.stop()
        self._interaction_cooldown_timer.stop()
        self._prev_state = self._state
        self._transition_to(state)

        # 循环动作设置 3 秒后回 idle，非循环动作按帧数
        action_cfg = self._anim.get_action_config(action)
        if action_cfg.get('loop', True):
            self._return_timer.start(3000)
        # 非循环动作的 return_timer 已在 _transition_to 中设置

    def set_walk_speed(self, speed: int) -> None:
        """运行时修改行走速度。"""
        self._walk_speed = max(1, min(speed, 20))

    def current_state(self) -> PetState:
        """返回当前状态（供外部查询）。"""
        return self._state
