#!/usr/bin/env python3
"""
下载公开手部关键点数据集

支持的数据集：
1. FreiHAND - 大规模手部数据集
2. RHD (Rendered Hand Dataset) - 渲染手部数据集
3. 自定义示例数据集

Usage:
    python download_dataset.py --source sample --output ../data/hand_keypoints --samples 500
"""

import argparse
import logging
import os
import zipfile
from pathlib import Path
from typing import Tuple

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_dataset(output_dir: str, n_samples: int = 500) -> dict:
    """创建示例数据集（用于测试）

    Args:
        output_dir: 输出目录
        n_samples: 样本数量

    Returns:
        dict: 统计信息
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 创建目录结构
    dirs = [
        "images/train", "images/val",
        "labels/train", "labels/val",
    ]
    for d in dirs:
        (output_path / d).mkdir(parents=True, exist_ok=True)

    stats = {"train": 0, "val": 0}

    logger.info(f"创建示例数据集: {n_samples} 个样本")

    for i in range(n_samples):
        # 90% 训练集，10% 验证集
        if np.random.random() < 0.9:
            split = "train"
        else:
            split = "val"

        # 创建随机图像（模拟手部）
        img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        # 生成随机关键点（21个手部关键点）
        # 模拟手部在图像中心
        cx, cy = 320, 320
        hand_size = np.random.randint(100, 200)

        keypoints = []
        for j in range(21):
            # 生成手部关键点位置（简化版）
            angle = (j / 21) * 2 * np.pi
            radius = hand_size * (0.3 + 0.7 * np.random.random())
            kp_x = cx + radius * np.cos(angle) + np.random.randint(-20, 20)
            kp_y = cy + radius * np.sin(angle) + np.random.randint(-20, 20)
            keypoints.append((kp_x, kp_y, 2))  # visibility=2

        # 计算边界框
        x_coords = [kp[0] for kp in keypoints]
        y_coords = [kp[1] for kp in keypoints]
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # 添加边距
        padding = 20
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(640, x_max + padding)
        y_max = min(640, y_max + padding)

        # 归一化坐标
        cx_norm = ((x_min + x_max) / 2) / 640
        cy_norm = ((y_min + y_max) / 2) / 640
        w_norm = (x_max - x_min) / 640
        h_norm = (y_max - y_min) / 640

        # 生成YOLO格式标签
        label_parts = [f"0 {cx_norm:.6f} {cy_norm:.6f} {w_norm:.6f} {h_norm:.6f}"]
        for kp_x, kp_y, kp_v in keypoints:
            norm_x = kp_x / 640
            norm_y = kp_y / 640
            label_parts.append(f"{norm_x:.6f} {norm_y:.6f} {kp_v}")

        label_str = " ".join(label_parts)

        # 保存图像
        filename = f"hand_{split}_{i:06d}"
        img_path = output_path / "images" / split / f"{filename}.jpg"
        cv2.imwrite(str(img_path), img)

        # 保存标签
        label_path = output_path / "labels" / split / f"{filename}.txt"
        with open(label_path, 'w') as f:
            f.write(label_str + "\n")

        stats[split] += 1

        # 进度显示
        if (i + 1) % 50 == 0:
            logger.info(f"已生成 {i + 1}/{n_samples} 个样本")

    logger.info(f"数据集创建完成: 训练集 {stats['train']}, 验证集 {stats['val']}")
    return stats


def download_freihand(output_dir: str):
    """下载 FreiHAND 数据集

    Args:
        output_dir: 输出目录
    """
    logger.info("FreiHAND 数据集需要手动下载")
    logger.info("下载地址: https://lmb.informatik.uni-freiburg.de/projects/freihand/")
    logger.info("请下载后解压到 data/freihand/ 目录")
    logger.info("然后运行转换脚本: python convert_freihand.py")


def main():
    parser = argparse.ArgumentParser(description="下载手部关键点数据集")
    parser.add_argument(
        "--source",
        type=str,
        default="sample",
        choices=["sample", "freihand", "rhd"],
        help="数据源"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./data/hand_keypoints",
        help="输出目录"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=500,
        help="样本数量（sample模式）"
    )

    args = parser.parse_args()

    if args.source == "sample":
        create_sample_dataset(args.output, args.samples)
    elif args.source == "freihand":
        download_freihand(args.output)
    else:
        logger.error(f"暂不支持 {args.source} 数据源")


if __name__ == "__main__":
    main()
