#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单张图片 → 桌面宠物全套动作素材
===============================
通过 ComfyUI / Stable Diffusion API 批量生成各动作的序列帧。

工作流程:
  1. 准备一张宠物参考图（正面、全身、透明背景最佳）
  2. 配置 ComfyUI 或 SD WebUI 的 API 地址
  3. 运行此脚本 → 自动生成全部 7 个动作的 PNG 序列帧

前提:
  - 本机或远程运行 ComfyUI (https://github.com/comfyanonymous/ComfyUI)
  - 安装 ComfyUI Manager + ControlNet + IP-Adapter 插件

用法:
  # 1) 先用参考图生成各动作关键帧
  python tools/image_to_sprites.py --image cat.png --mode keyframes

  # 2) 再在关键帧之间插帧补全
  python tools/image_to_sprites.py --image cat.png --mode interpolate
"""

# ============================================================
# 这个脚本是一个框架/指南，因为 AI 生成需要 GPU 和复杂环境。
# 实际的 AI 调用通过 ComfyUI API 完成。
# 下面给出三种不同成本/质量等级的方案。
# ============================================================

import argparse
import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


# ============================================================
#  方案一：ComfyUI API（最推荐，质量最高）
# ============================================================

COMFYUI_URL = "http://127.0.0.1:8188"

# 各动作的提示词（以猫为例，替换为你的宠物类型）
ACTION_PROMPTS = {
    "idle":  "cute cat sitting, looking forward, gentle breathing, slight body movement, "
             "same character as reference image, 2D game sprite style, "
             "transparent background, full body, consistent style",
    "walk":  "cute cat walking cycle, side view, step by step, "
             "same character as reference image, 2D game sprite animation style, "
             "transparent background, full body, consistent style",
    "sleep": "cute cat sleeping, lying down curled up, peaceful, eyes closed, "
             "gentle breathing, same character as reference image, "
             "transparent background, full body, consistent style",
    "jump":  "cute cat jumping up, dynamic pose, paws in air, "
             "same character as reference image, 2D game sprite style, "
             "transparent background, full body, consistent style",
    "daze":  "cute cat sitting still, dazed expression, staring blankly, "
             "same character as reference image, 2D game sprite style, "
             "transparent background, full body, consistent style",
    "happy": "cute cat happy reaction, excited, bouncing slightly, cheerful expression, "
             "same character as reference image, 2D game sprite style, "
             "transparent background, full body, consistent style",
    "angry": "cute cat angry reaction, annoyed expression, pouting, "
             "same character as reference image, 2D game sprite style, "
             "transparent background, full body, consistent style",
}


def comfyui_queue_prompt(prompt_workflow: dict) -> str:
    """向 ComfyUI 提交工作流，返回 prompt_id。"""
    data = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data)
    result = json.loads(urllib.request.urlopen(req).read())
    return result["prompt_id"]


def comfyui_wait_for_result(prompt_id: str, timeout: int = 300) -> list:
    """等待 ComfyUI 生成完成，返回输出图片列表。"""
    start = time.time()
    while time.time() - start < timeout:
        req = urllib.request.Request(f"{COMFYUI_URL}/history/{prompt_id}")
        history = json.loads(urllib.request.urlopen(req).read())
        if prompt_id in history:
            outputs = history[prompt_id]["outputs"]
            images = []
            for node_id, node_output in outputs.items():
                for img in node_output.get("images", []):
                    images.append(img)
            return images
        time.sleep(2)
    raise TimeoutError("ComfyUI generation timed out")


def build_ipadapter_workflow(reference_image_base64: str, prompt: str,
                              num_frames: int = 8) -> dict:
    """
    构建 IP-Adapter + AnimateDiff 工作流。
    这需要一个预先配置好的 ComfyUI workflow JSON。
    用户可以在 ComfyUI 中手动搭建好，导出为 API 格式。
    """
    # 这个工作流需要根据你的 ComfyUI 配置定制
    # 这里给出结构框架，实际使用需要在 ComfyUI 里搭好并导出 JSON
    return {
        "3": {  # KS sampler
            "class_type": "KSampler",
            "inputs": {
                "seed": int(time.time()),
                "steps": 20,
                "cfg": 7.0,
                "sampler_name": "euler_ancestral",
                "scheduler": "normal",
                "denoise": 0.75,
                "model": ["4", 0],
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            }
        },
        # ... 更多节点 ...
    }


# ============================================================
#  方案二：Runway / Pika / Kling API（云端，免 GPU）
# ============================================================

def runway_generate(image_path: str, prompt: str) -> str:
    """
    使用 Runway Gen-3 API 生成视频。
    需要设置 RUNWAY_API_KEY 环境变量。
    https://docs.runwayml.com/
    """
    api_key = os.environ.get("RUNWAY_API_KEY")
    if not api_key:
        raise RuntimeError("请设置 RUNWAY_API_KEY 环境变量")

    # Runway API 调用（伪代码，需要按实际 API 文档调整）
    print(f"[Runway] 提交任务: {prompt[:50]}...")
    print(f"[Runway] 参考图: {image_path}")
    print("[Runway] API 集成请参考 https://docs.runwayml.com/")
    return ""


# ============================================================
#  方案三：纯本地 — 不用 AI，手动画骨骼（Live2D 思路）
# ============================================================

def print_manual_guide():
    """打印手工/半自动制作素材的指南。"""
    print("""
╔══════════════════════════════════════════════════════════╗
║     不用 AI 生成素材的方法（零成本，质量可控）            ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  工具: DragonBones (免费) 或 Spine ($69)                 ║
║                                                          ║
║  步骤:                                                   ║
║  1. 用 Photoshop/Krita 把参考图分层:                     ║
║     - 头 (head)                                          ║
║     - 身体 (body)                                        ║
║     - 前腿 x2 (front_leg_l, front_leg_r)                 ║
║     - 后腿 x2 (back_leg_l, back_leg_r)                   ║
║     - 尾巴 (tail)                                        ║
║     - 面部表情 x3 (normal, happy, angry)                 ║
║                                                          ║
║  2. 导入 DragonBones，绑定骨骼                           ║
║  3. 为每个动作创建动画曲线:                               ║
║     idle:  身体微呼吸起伏，尾巴轻摆                      ║
║     walk:  腿交替摆动，身体前倾                          ║
║     sleep: 身体缩成一团，呼吸变慢                        ║
║     jump:  下蹲→弹起→落地→回弹                           ║
║     daze:  头微晃，眼神涣散                              ║
║     happy: 蹦跳，尾巴高频摇摆                            ║
║     angry: 跺脚，眉毛下压                                ║
║                                                          ║
║  4. 导出 PNG 序列 → 放入 assets/ 对应文件夹              ║
║                                                          ║
║  这个方法画一次分层，所有动作都能生成，                   ║
║  比 AI 逐帧生成稳定可控。                                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")


# ============================================================
#  CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="单张参考图 → 桌面宠物全套动作素材"
    )
    parser.add_argument("--image", help="参考图路径")
    parser.add_argument("--mode", choices=["keyframes", "interpolate", "guide"],
                        default="guide", help="模式")
    parser.add_argument("--comfyui-url", default=COMFYUI_URL, help="ComfyUI API 地址")
    parser.add_argument("--frames", type=int, default=8, help="每个动作生成帧数")
    parser.add_argument("--output", default="assets/my_pet", help="输出目录")

    args = parser.parse_args()

    if args.mode == "guide" or not args.image:
        print_manual_guide()
        print("\n" + "=" * 60)
        print("推荐优先级: 骨骼动画 > ComfyUI > Runway API")
        print("=" * 60)
        return

    # 创建输出目录结构
    for action in ["idle", "walk", "sleep", "jump", "daze", "happy", "angry"]:
        Path(args.output, action).mkdir(parents=True, exist_ok=True)
    print(f"[OK] 输出目录已创建: {args.output}")


if __name__ == "__main__":
    main()
