#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频 → 桌面宠物素材 自动化工具
===============================
一键将视频/动图转换为透明背景 PNG 序列帧，可直接放入 assets/ 使用。

依赖:
    pip install rembg pillow numpy opencv-python

需要 FFmpeg（用于视频解码）:
    Windows: winget install ffmpeg  或  choco install ffmpeg
    macOS:   brew install ffmpeg

用法:
    # 基本用法 — 导出所有帧到指定文件夹
    python tools/video_to_sprite.py cat.mp4 -o assets/my_cat/walk

    # 指定帧率和最大帧数
    python tools/video_to_sprite.py cat.mp4 -o assets/my_cat/idle --fps 12 --max-frames 8

    # 只导帧不抠图（用于绿幕素材）
    python tools/video_to_sprite.py green_cat.mp4 -o frames/ --no-remove-bg

    # 从 GIF 转换
    python tools/video_to_sprite.py cat.gif -o assets/my_cat/walk

    # 批量处理 — 一个视频按时间点切成多个动作
    python tools/video_to_sprite.py full_cat.mp4 -o assets/my_cat --split-actions
        actions:
          idle:  [0:00, 0:03]
          walk:  [0:03, 0:08]
          jump:  [0:08, 0:11]
          sleep: [0:11, 0:16]
"""

import argparse
import os
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


# ============================================================
#  配置
# ============================================================

# rembg 模型选择
# u2net      — 通用，速度快
# u2net_human_seg — 专攻人物
# isnet-general-use — 通用（推荐）
# isnet-anime — 动漫风格
BGM_MODEL = "isnet-general-use"

# 抠图后裁切到统一尺寸（0=保持原始尺寸）
DEFAULT_CROP_SIZE = 256


# ============================================================
#  工具函数
# ============================================================

def _find_ffmpeg() -> str | None:
    """查找 ffmpeg 可执行文件，返回完整路径或 None。"""
    # 1) 先检查 PATH
    path = shutil.which("ffmpeg")
    if path:
        return path

    # 2) Windows: 搜索 winget 安装目录
    if sys.platform == "win32":
        winget_base = os.path.expandvars(
            r"%LOCALAPPDATA%\Microsoft\WinGet\Packages"
        )
        if os.path.isdir(winget_base):
            for root, _dirs, files in os.walk(winget_base):
                if "ffmpeg.exe" in files:
                    return os.path.join(root, "ffmpeg.exe")
        # 3) Windows: 检查常见手动安装路径
        for candidate in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        ]:
            if os.path.isfile(candidate):
                return candidate

    return None


def check_ffmpeg():
    """检查 FFmpeg 是否可用，找不到则给出安装提示。"""
    ffmpeg_path = _find_ffmpeg()
    if ffmpeg_path is None:
        print("[ERROR] FFmpeg not found. Install it first:")
        print("   Windows: winget install ffmpeg")
        print("   macOS:   brew install ffmpeg")
        print("   Linux:   sudo apt install ffmpeg")
        sys.exit(1)

    result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
    version_line = result.stdout.split('\n')[0]
    print(f"[OK] {version_line}")
    return ffmpeg_path


def check_rembg():
    """检查 rembg 是否可用，不可用则安装。"""
    try:
        import rembg
        print(f"✅ rembg {rembg.__version__} 已就绪")
    except ImportError:
        print("⏳ 正在安装 rembg...")
        subprocess.run([sys.executable, "-m", "pip", "install", "rembg[gpu]"], check=True)
        print("✅ rembg 安装完成")


def parse_time(time_str: str) -> float:
    """将 "1:23" 或 "83" 转换为秒数。"""
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(time_str)


# ============================================================
#  视频帧提取
# ============================================================

def extract_frames(
    video_path: str,
    output_dir: str,
    ffmpeg_path: str = "ffmpeg",
    fps: int = 12,
    max_frames: int = 0,
    start_time: float = 0,
    end_time: float = 0,
) -> list[Path]:
    """
    用 FFmpeg 从视频提取帧。

    Args:
        video_path: 视频文件路径
        output_dir: 输出目录
        ffmpeg_path: ffmpeg 可执行文件路径
        fps: 帧率
        max_frames: 最大导出帧数（0=全部）
        start_time: 起始时间（秒）
        end_time: 结束时间（秒，0=到结尾）

    Returns:
        导出的 PNG 文件路径列表
    """
    os.makedirs(output_dir, exist_ok=True)

    output_pattern = os.path.join(output_dir, "raw_%05d.png")

    cmd = [ffmpeg_path, "-y", "-i", video_path]

    if start_time > 0:
        cmd += ["-ss", str(start_time)]
    if end_time > 0:
        cmd += ["-to", str(end_time)]

    vf_parts = [f"fps={fps}"]
    cmd += ["-vf", ",".join(vf_parts)]

    if max_frames > 0:
        cmd += ["-frames:v", str(max_frames)]

    cmd.append(output_pattern)

    print(f"🎬 提取帧: fps={fps}, start={start_time}s, end={end_time}s")
    subprocess.run(cmd, check=True, capture_output=True)

    # 收集导出的文件
    frame_files = sorted(Path(output_dir).glob("raw_*.png"))
    print(f"   导出 {len(frame_files)} 帧 → {output_dir}")
    return frame_files


# ============================================================
#  背景移除
# ============================================================

def remove_background(
    frame_files: list[Path],
    output_dir: str,
    model: str = BGM_MODEL,
) -> list[Path]:
    """
    用 rembg 批量移除背景。

    Args:
        frame_files: 输入帧文件列表
        output_dir: 输出目录
        model: rembg 模型名

    Returns:
        抠图后的 PNG 文件路径列表
    """
    from rembg import remove, new_session

    os.makedirs(output_dir, exist_ok=True)
    session = new_session(model)

    print(f"🖼️  抠图中 (模型: {model})...")
    result_files = []

    for i, f in enumerate(frame_files):
        with open(f, "rb") as f_in:
            input_bytes = f_in.read()
        output_bytes = remove(input_bytes, session=session)

        out_name = f"frame_{i:04d}.png"
        out_path = os.path.join(output_dir, out_name)
        with open(out_path, "wb") as f_out:
            f_out.write(output_bytes)

        result_files.append(Path(out_path))

        if (i + 1) % 10 == 0 or i == len(frame_files) - 1:
            print(f"   {i + 1}/{len(frame_files)} 帧完成", end="\r")

    print(f"\n   抠图完成: {len(result_files)} 帧 → {output_dir}")
    return result_files


# ============================================================
#  裁切 & 统一尺寸
# ============================================================

def crop_and_resize(
    frame_files: list[Path],
    output_dir: str,
    target_size: int = DEFAULT_CROP_SIZE,
    action_name: str = "frame",
):
    """
    裁切透明区域并缩放到统一尺寸。

    对于序列帧动画，这里采取的策略是：
    1. 找到所有帧的最大内容边界
    2. 用统一的边界裁切所有帧
    3. 缩放到 target_size × target_size，居中放置

    Args:
        frame_files: 输入帧列表
        output_dir: 输出目录
        target_size: 目标正方形边长（0=不缩放）
        action_name: 动作名称（用于输出命名）
    """
    from PIL import Image
    import numpy as np

    os.makedirs(output_dir, exist_ok=True)

    print(f"✂️  裁切 & 统一尺寸 (→ {target_size}×{target_size})...")

    # 第一遍：计算所有帧的统一内容边界
    min_left, min_top = float('inf'), float('inf')
    max_right, max_bottom = float('-inf'), float('-inf')

    images = []
    for f in frame_files:
        img = Image.open(f).convert("RGBA")
        images.append(img)

        # 找到不透明像素的边界
        alpha = np.array(img.split()[3])
        rows = np.any(alpha > 10, axis=1)
        cols = np.any(alpha > 10, axis=0)
        if rows.any() and cols.any():
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]
            min_left = min(min_left, cmin)
            min_top = min(min_top, rmin)
            max_right = max(max_right, cmax)
            max_bottom = max(max_bottom, rmax)

    # 添加边距
    margin = 8
    min_left = max(0, min_left - margin)
    min_top = max(0, min_top - margin)
    max_right = min(images[0].width, max_right + margin)
    max_bottom = min(images[0].height, max_bottom + margin)

    crop_w = max_right - min_left
    crop_h = max_bottom - min_top

    # 第二遍：裁切+缩放
    padded_size = max(crop_w, crop_h)

    for i, img in enumerate(images):
        # 裁切
        cropped = img.crop((min_left, min_top, max_right, max_bottom))

        if target_size > 0:
            # 创建正方形画布，居中放置
            canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))

            # 等比缩放
            scale = target_size / padded_size
            new_w = int(crop_w * scale)
            new_h = int(crop_h * scale)
            resized = cropped.resize((new_w, new_h), Image.LANCZOS)

            # 居中粘贴
            offset_x = (target_size - new_w) // 2
            offset_y = (target_size - new_h) // 2
            canvas.paste(resized, (offset_x, offset_y), resized)
            out_img = canvas
        else:
            out_img = cropped

        out_path = os.path.join(output_dir, f"{action_name}_{i:03d}.png")
        out_img.save(out_path, "PNG")
        images[i] = out_img  # 释放原图

    print(f"   裁切完成: {len(frame_files)} 帧 → {output_dir}")
    print(f"   统一裁切区域: ({min_left},{min_top})~({max_right},{max_bottom})")


# ============================================================
#  主流程
# ============================================================

def process_video(
    video_path: str,
    output_dir: str,
    ffmpeg_path: str = "ffmpeg",
    fps: int = 12,
    max_frames: int = 0,
    start_time: float = 0,
    end_time: float = 0,
    target_size: int = DEFAULT_CROP_SIZE,
    remove_bg: bool = True,
    model: str = BGM_MODEL,
    start_index: int = 0,
):
    """
    完整流程：视频 → 帧提取 → 抠图 → 裁切 → 命名输出。
    """
    video_name = Path(video_path).stem
    work_dir = tempfile.mkdtemp(prefix="sprite_work_")

    try:
        # 步骤1: 提取帧
        raw_dir = os.path.join(work_dir, "raw")
        raw_frames = extract_frames(video_path, raw_dir, ffmpeg_path, fps, max_frames, start_time, end_time)
        if not raw_frames:
            print("❌ 未提取到任何帧，请检查视频文件和参数")
            return

        # 步骤2: 抠图（可选）
        if remove_bg:
            nobg_dir = os.path.join(work_dir, "nobg")
            frames = remove_background(raw_frames, nobg_dir, model)
        else:
            frames = raw_frames

        # 步骤3: 裁切缩放 + 重命名
        action_name = Path(output_dir).name
        crop_and_resize(frames, output_dir, target_size, action_name)

        print(f"\n✅ 完成！素材已输出到: {output_dir}")
        print(f"   共 {len(frames)} 帧，可直接放入 assets/ 使用")

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def split_actions_interactive(video_path: str, output_base: str, ffmpeg_path: str, fps: int, size: int, remove_bg: bool, model: str):
    """交互式分段时间轴导出多个动作。"""
    print("""
📋 分段导出模式
===============
输入每个动作的起止时间，格式: "开始-结束 动作名"
  例: 0-3 idle
  例: 3-8 walk
  例: 8-11 jump
  例: 11-16 sleep

输入空行开始处理。
""")

    actions = []
    while True:
        line = input("  → ").strip()
        if not line:
            break
        try:
            time_range, action_name = line.rsplit(maxsplit=1)
            start_str, end_str = time_range.split('-')
            start = parse_time(start_str.strip())
            end = parse_time(end_str.strip())
            actions.append((action_name.strip(), start, end))
            print(f"      ✅ {action_name}: {start}s → {end}s")
        except ValueError:
            print(f"      ❌ 格式错误，请用: 开始-结束 动作名")

    if not actions:
        print("未输入任何动作，退出")
        return

    for action_name, start, end in actions:
        output_dir = os.path.join(output_base, action_name)
        print(f"\n{'='*50}")
        print(f"🐱 处理动作: {action_name} ({start}s → {end}s)")
        print(f"{'='*50}")
        process_video(
            video_path, output_dir,
            ffmpeg_path=ffmpeg_path,
            fps=fps, start_time=start, end_time=end,
            target_size=size, remove_bg=remove_bg, model=model,
        )


# ============================================================
#  命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="视频 → 桌面宠物 PNG 序列帧 自动化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本用法
  python tools/video_to_sprite.py cat.mp4 -o assets/my_cat/walk

  # 指定帧率和最大帧数
  python tools/video_to_sprite.py cat.mp4 -o assets/my_cat/idle --fps 8 --max-frames 8

  # 不抠图（绿幕素材已透明或已抠好）
  python tools/video_to_sprite.py cat.mp4 -o frames/ --no-remove-bg

  # 分段导出多个动作（交互模式）
  python tools/video_to_sprite.py full_cat.mp4 -o assets/my_cat --split-actions

  # 调整输出尺寸
  python tools/video_to_sprite.py cat.mp4 -o assets/my_cat/walk --size 512
        """,
    )
    parser.add_argument("video", help="输入视频文件路径（支持 mp4/mov/gif/webm 等）")
    parser.add_argument("-o", "--output", required=True, help="输出目录")
    parser.add_argument("--fps", type=int, default=12, help="导出帧率 (默认 12)")
    parser.add_argument("--max-frames", type=int, default=0, help="最大导出帧数 (0=全部)")
    parser.add_argument("--start", type=str, default="0", help="起始时间 (秒 或 M:SS)")
    parser.add_argument("--end", type=str, default="0", help="结束时间 (秒 或 M:SS) [0=到结尾]")
    parser.add_argument("--size", type=int, default=DEFAULT_CROP_SIZE, help=f"输出正方形边长 (默认 {DEFAULT_CROP_SIZE}, 0=保持原始)")
    parser.add_argument("--no-remove-bg", action="store_true", help="跳过抠图步骤")
    parser.add_argument("--model", default=BGM_MODEL, help=f"rembg 模型 (默认 {BGM_MODEL})")
    parser.add_argument("--split-actions", action="store_true", help="交互式分段时间轴导出多个动作")

    args = parser.parse_args()

    # 环境检查
    ffmpeg_path = check_ffmpeg()
    if not args.no_remove_bg:
        check_rembg()

    # 解析时间
    start_time = parse_time(args.start)
    end_time = parse_time(args.end) if args.end != "0" else 0

    # 分段模式
    if args.split_actions:
        split_actions_interactive(
            args.video, args.output, ffmpeg_path, args.fps, args.size,
            not args.no_remove_bg, args.model,
        )
        return

    # 单段模式
    process_video(
        args.video, args.output,
        ffmpeg_path=ffmpeg_path,
        fps=args.fps,
        max_frames=args.max_frames,
        start_time=start_time,
        end_time=end_time,
        target_size=args.size,
        remove_bg=not args.no_remove_bg,
        model=args.model,
    )


if __name__ == "__main__":
    main()
