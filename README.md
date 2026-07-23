# 🐾 桌面宠物 (Desktop Pet)

一款跨平台桌面宠物程序，支持 **Windows** 和 **macOS**。可爱的小动物在你的桌面上自由行走、睡觉、跳跃，点击它还会和你互动！

---

## ✨ 功能特性

| 功能 | 说明 |
|------|------|
| 🪟 无边框透明窗口 | 只显示宠物形象，背景完全透明 |
| 📌 窗口置顶 | 宠物始终在桌面最上层可见 |
| 🖱️ 不抢焦点 | 不会打断你的打字和正常工作 |
| ✋ 自由拖动 | 鼠标按住宠物可拖到桌面任意位置 |
| 🚶 随机游走 | 宠物自动在屏幕范围内行走，碰到边缘自动转向 |
| 🎭 多种动画 | 待机、走路、发呆、睡觉、跳跃，随机切换 |
| 🎯 点击互动 | 点击宠物触发撒娇/跳跃反应 |
| 📋 右键菜单 | 隐藏宠物、调整速度、开机自启、退出 |
| 🖥️ 多显示器 | 支持多屏幕自由跨越 |
| 📦 独立打包 | Windows 打包为 .exe，macOS 打包为 .app，无需安装 Python |

---

## 📁 项目结构

```
desktop_pet/
├── main.py                      # 程序入口
├── config.yaml                  # 配置文件（动画、行为、窗口参数）
├── requirements.txt             # Python 依赖
├── README.md                    # 本说明文档
│
├── src/                         # 源代码
│   ├── __init__.py
│   ├── pet_app.py               # 应用程序启动器
│   ├── pet_window.py            # 宠物窗口（无边框/透明/置顶/可拖动）
│   ├── pet_widget.py            # 宠物渲染控件（绘制动画帧）
│   ├── animation_manager.py     # 动画管理器（加载帧、缓存、帧切换）
│   ├── behavior_manager.py      # 行为管理器（状态机、移动AI、定时器）
│   ├── config_manager.py        # 配置管理器（YAML加载/保存）
│   └── utils.py                 # 工具函数（屏幕边界、路径、平台检测）
│
├── assets/                      # 素材目录
│   └── default_pet/             # 默认宠物素材
│       ├── idle/                # 待机动画帧 (idle_000.png ~ idle_007.png)
│       ├── walk/                # 走路动画帧 (walk_000.png ~ walk_011.png)
│       ├── sleep/               # 睡眠动画帧 (sleep_000.png ~ sleep_007.png)
│       ├── jump/                # 跳跃动画帧 (jump_000.png ~ jump_011.png)
│       ├── daze/                # 发呆动画帧 (daze_000.png ~ daze_007.png)
│       ├── happy/               # 开心动画帧 (happy_000.png ~ happy_007.png)
│       └── angry/               # 生气动画帧 (angry_000.png ~ angry_007.png)
│
└── build/                       # 打包脚本
    ├── build.bat                # Windows 打包脚本
    └── build.sh                 # macOS 打包脚本
```

---

## 🚀 快速开始

### 环境要求

- **Python 3.10+**
- **pip**（Python 包管理器）

### 1. 安装依赖

```bash
cd desktop_pet
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python main.py
```

> **提示：** 如果没有真实 PNG 素材，程序会自动生成彩色圆形占位动画，所有功能都能正常工作。

### 3. 操作说明

| 操作 | 效果 |
|------|------|
| **左键拖动** | 移动宠物到任意位置 |
| **左键点击** | 触发互动动画（撒娇/跳跃） |
| **右键点击** | 打开菜单（隐藏、速度、自启、退出） |
| **托盘双击** | 恢复隐藏的宠物 |

---

## ⚙️ 配置说明

编辑 `config.yaml` 即可自定义所有行为。主要配置项：

```yaml
pet:
  scale: 1.0               # 缩放比例 (0.5 = 一半大小, 2.0 = 两倍大)
  fps: 12                  # 动画帧率

behavior:
  walk_speed: 3            # 走路速度 (1=慢, 10=快)
  action_interval_min: 5   # 动作切换最短间隔 (秒)
  action_interval_max: 15  # 动作切换最长间隔 (秒)
  walk_probability: 0.35   # 走路概率
  sleep_probability: 0.4   # 睡觉概率
  daze_probability: 0.2    # 发呆概率
  jump_probability: 0.15   # 跳跃概率

interaction:
  click_actions: ["happy", "jump"]   # 点击时随机选择
  click_cooldown: 2                  # 点击冷却 (秒)
```

---

## 🎨 自定义宠物素材

### 素材格式规范

| 属性 | 要求 |
|------|------|
| **格式** | PNG（RGBA，带透明通道） |
| **命名** | `{动作名}_{帧号:03d}.png`（如 `walk_000.png`, `walk_001.png`） |
| **尺寸** | 建议 128×128 ~ 256×256 像素 |
| **帧数** | 每个动作 8~16 帧，走路建议 12+ 帧 |
| **一致性** | 同一动作的所有帧尺寸必须一致 |

### 添加新宠物

1. 在 `assets/` 下创建新文件夹（如 `assets/my_cat/`）
2. 在其中按动作创建子文件夹并放入 PNG 序列帧
3. 在 `config.yaml` 中修改 `animations.base_path`：

```yaml
animations:
  base_path: "assets/my_cat"   # 指向你的新宠物素材
```

### 动作文件夹对照

| 文件夹 | 动作说明 | 循环播放 | 备注 |
|--------|---------|----------|------|
| `idle/` | 待机（原地小动作） | ✅ | 呼吸起伏等 |
| `walk/` | 走路 | ✅ | 帧数多一些更自然 |
| `sleep/` | 睡觉 | ✅ | 自动5秒后醒来 |
| `jump/` | 跳跃 | ❌ | 播放完自动回到待机 |
| `daze/` | 发呆 | ✅ | 目光呆滞 |
| `happy/` | 开心（点击触发） | ❌ | 播放完恢复原状态 |
| `angry/` | 生气（点击触发） | ❌ | 可选，可删除 |

---

## 📦 打包发布

### Windows 打包

```bash
cd build
build.bat
```

输出：`dist/DesktopPet.exe`（单文件，无需 Python 环境）

### macOS 打包

```bash
cd build
chmod +x build.sh
./build.sh
```

输出：`dist/DesktopPet.app`（独立应用程序包）

### 手动打包命令

**Windows:**
```bash
pyinstaller --onefile --windowed ^
  --add-data "assets;assets" ^
  --add-data "config.yaml;." ^
  --name "DesktopPet" ^
  --clean --noconfirm ^
  main.py
```

**macOS:**
```bash
pyinstaller --onefile --windowed \
  --add-data "assets:assets" \
  --add-data "config.yaml:." \
  --name "DesktopPet" \
  --osx-bundle-identifier "com.desktoppet.app" \
  --clean --noconfirm \
  main.py
```

> ⚠️ **macOS 注意：** 打包完成后需手动在 `dist/DesktopPet.app/Contents/Info.plist` 中添加 `LSUIElement = YES` 来隐藏 Dock 图标。

---

## 🔧 开机自启

### Windows
- 右键宠物 → 勾选「开机自启」
- 通过注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 实现

### macOS
- 右键宠物 → 勾选「开机自启」
- 通过 `~/Library/LaunchAgents/com.desktoppet.app.plist` 实现
- 也可手动：系统设置 → 通用 → 登录项 → 添加 DesktopPet.app

---

## 🧪 开发说明

### 核心架构

```
用户交互 (拖动/点击/右键)
       │
       ▼
  PetWindow ──→ BehaviorManager (状态机 + 移动AI)
       │              │
       │         ┌────┴────┐
       │         │  Timers  │
       │         │ frame    │──→ 推进动画帧
       │         │ action   │──→ 随机切换动作
       │         │ move     │──→ 更新位置
       │         └─────────┘
       │              │
       ▼              ▼
  PetWidget  ←── AnimationManager
  (渲染帧)       (帧缓存)
```

### 状态机流转

```
IDLE ←→ WALK ←→ DAZE
  │       │
  ├──→ SLEEP (5s后)→ IDLE
  └──→ JUMP (播完)→ IDLE

任意状态 ──[点击]──→ INTERACTING (播完)→ 恢复原状态
```

### 没有素材时的行为

程序内置了占位帧生成器——每个动作会渲染为不同颜色的圆形+表情+文字标签。这让你可以在没有美工素材的情况下开发和测试所有功能。

---

## ❓ 常见问题

**Q: 宠物窗口不显示？**
A: 检查是否被其他窗口遮挡。宠物默认显示在屏幕 (300, 300) 位置。可修改 `config.yaml` 中 `window.start_position`。

**Q: 点击宠物没反应？**
A: 有 2 秒的点击冷却时间，连续快速点击只响应一次。

**Q: 如何更换宠物形象？**
A: 准备新的 PNG 序列帧素材，修改 `config.yaml` 中的 `animations.base_path` 指向新素材目录。

**Q: macOS 上宠物出现在 Dock 中？**
A: 确保 `Info.plist` 中包含 `LSUIElement = YES`。打包脚本已自动处理。

**Q: Windows 上宠物出现在任务栏？**
A: 使用 `Qt.Tool` 标志应该已隐藏。如果仍有问题，尝试以管理员权限运行。

---

## 📄 许可

本项目仅供个人学习和娱乐使用。

---

## 🙏 致谢

- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — 跨平台 GUI 框架
- [PyInstaller](https://pyinstaller.org/) — Python 打包工具
- [PyYAML](https://pyyaml.org/) — YAML 解析库
