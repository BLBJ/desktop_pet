#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌面宠物 - 主入口
Desktop Pet - Main Entry Point

用法:
    python main.py                      # 使用默认配置启动
    python main.py --config myconf.yaml # 使用自定义配置启动

素材说明:
    将 PNG 序列帧放入 assets/default_pet/ 对应动作文件夹即可。
    如果没有素材，程序会自动生成彩色圆形占位动画。
    详见 README.md 中的素材格式说明。

打包命令:
    Windows: pyinstaller --onefile --windowed --add-data "assets;assets" --add-data "config.yaml;." main.py
    macOS:   pyinstaller --onefile --windowed --add-data "assets:assets" --add-data "config.yaml:." main.py
"""

import sys
import os
import argparse


def main():
    """主函数：解析参数并启动应用。"""
    parser = argparse.ArgumentParser(
        description="桌面宠物 - 一只可爱的桌面伙伴",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                       使用默认配置
  python main.py --config my_conf.yaml 使用自定义配置
        """,
    )
    parser.add_argument(
        '--config', '-c',
        type=str,
        default=None,
        help='配置文件路径 (默认: 项目根目录下的 config.yaml)',
    )
    args = parser.parse_args()

    # 确保 src 包在 path 中（防止直接运行时的导入问题）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    # 延迟导入，确保 path 设置正确
    from src.pet_app import PetApp

    app = PetApp(config_path=args.config)
    sys.exit(app.run())


if __name__ == '__main__':
    main()
