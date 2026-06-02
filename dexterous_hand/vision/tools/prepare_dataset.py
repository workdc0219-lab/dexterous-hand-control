#!/usr/bin/env python3
"""
数据集准备脚本 - 从公开数据集下载并转换为YOLO格式

支持的数据集:
1. FreiHAND - 大规模手部数据集
2. RHD (Rendered Handpose Dataset) - 渲染手部姿态数据集
3. 自定义数据集

Usage:
    python prepare_dataset.py --source freihand --output ./data/hand_keypoints
"""

import argparse
import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatasetConverter:
    """数据集格式转换器"""

    def __init__(self, output_dir: str, img_size: int = 640):
        """初始化转换器

        Args:
            output_dir: 输出目录
            img_size: 图片尺寸
        """
        self.output_dir = Path(output_dir)
        self.img_size = img_size

        # 创建目录结构
        self._create_dirs()

    def _create_dirs(self):
        """创建目录结构"""
        dirs = [
            "images/train", "images/val", "images/test",
            "labels/train", "labels/val", "labels/test",
        ]
        for d in dirs:
            (self.output_dir / d).mkdir(parents=True, exist_ok=True)

    def convert_freiburg_format(
        self,
        images: np.ndarray,
        keypoints: np.ndarray,
        split_ratio: Tuple[float, float, float] = (0.7, 0.2, 0.1)
    ) -> dict:
        """转换 FreiHAND 数据集格式

        Args:
            images: 图像数组 [N, H, W, 3]
            keypoints: 关键点数组 [N, 21, 3]
            split_ratio: 划分比例 (train, val, test)

        Returns:
            dict: 转换统计信息
        """
        n_samples = len(images)
        n_train = int(n_samples * split_ratio[0])
        n_val = int(n_samples * split_ratio[1])

        stats = {"train": 0, "val": 0, "test": 0}

        for i in range(n_samples):
            # 确定划分
            if i < n_train:
                split = "train"
            elif i < n_train + n_val:
                split = "val"
            else:
                split = "test"

            # 保存图像
            img_name = f"hand_{i:06d}.jpg"
            img_path = self.output_dir / "images" / split / img_name
            cv2.imwrite(str(img_path), images[i])

            # 转换关键点为YOLO格式
            h, w = images[i].shape[:2]
            label_path = self.output_dir / "labels" / split / f"hand_{i:06d}.txt"

            self._write_yolo_label(label_path, keypoints[i], w, h)
            stats[split] += 1

        return stats

    def _write_yolo_label(
        self,
        label_path: Path,
        keypoints: np.ndarray,
        img_width: int,
        img_height: int
    ):
        """写入YOLO格式标签

        格式: class_id cx cy w h kp1_x kp1_y kp1_v kp2_x kp2_y kp2_v ...
        """
        # 计算边界框
        kpts = keypoints[:, :2]
        x_min, y_min = kpts.min(axis=0)
        x_max, y_max = kpts.max(axis=0)

        # 归一化
        cx = ((x_min + x_max) / 2) / img_width
        cy = ((y_min + y_max) / 2) / img_height
        w = (x_max - x_min) / img_width
        h = (y_max - y_min) / img_height

        # 关键点归一化
        kpts_normalized = []
        for kp in keypoints:
            kp_x = kp[0] / img_width
            kp_y = kp[1] / img_height
            kp_v = 2 if kp[2] > 0.5 else 0  # visibility
            kpts_normalized.extend([kp_x, kp_y, kp_v])

        # 写入文件
        with open(label_path, 'w') as f:
            line_parts = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"]
            line_parts.extend([f"{v:.6f}" for v in kpts_normalized])
            f.write(" ".join(line_parts) + "\n")

    def convert_from_images(
        self,
        image_dir: str,
        annotation_file: str = None,
        split: str = "train"
    ) -> dict:
        """从图像目录转换

        Args:
            image_dir: 图像目录
            annotation_file: 标注文件路径
            split: 数据划分

        Returns:
            dict: 转换统计信息
        """
        image_dir = Path(image_dir)
        image_files = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))

        stats = {split: 0}

        for img_path in image_files:
            # 复制图像
            dst_img = self.output_dir / "images" / split / img_path.name
            shutil.copy2(img_path, dst_img)

            stats[split] += 1

        logger.info(f"转换完成: {stats}")
        return stats


def download_freihand(output_dir: str):
    """下载 FreiHAND 数据集 (示例函数)

    实际使用时需要从官方地址下载:
    https://lmb.informatik.uni-freiburg.de/projects/freihand/
    """
    logger.info("FreiHAND 数据集需要从官方网站下载")
    logger.info("下载地址: https://lmb.informatik.uni-freiburg.de/projects/freihand/")
    logger.info("请下载后解压到 data/freihand/ 目录")


def create_sample_dataset(output_dir: str, n_samples: int = 100):
    """创建示例数据集（用于测试）

    Args:
        output_dir: 输出目录
        n_samples: 样本数量
    """
    converter = DatasetConverter(output_dir)

    logger.info(f"创建示例数据集: {n_samples} 个样本")

    # 生成模拟数据
    images = []
    keypoints = []

    for i in range(n_samples):
        # 创建随机图像
        img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

        # 生成随机关键点 (21个)
        kpts = np.random.rand(21, 3) * 400 + 100
        kpts[:, 2] = 0.9  # 高置信度

        images.append(img)
        keypoints.append(kpts)

    images = np.array(images)
    keypoints = np.array(keypoints)

    # 转换
    stats = converter.convert_freiburg_format(images, keypoints)
    logger.info(f"数据集创建完成: {stats}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="数据集准备工具")
    parser.add_argument(
        "--source",
        type=str,
        default="sample",
        choices=["freihand", "rhd", "custom", "sample"],
        help="数据源"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./data/hand_keypoints",
        help="输出目录"
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        default=None,
        help="输入图像目录（custom模式）"
    )
    parser.add_argument(
        "--n_samples",
        type=int,
        default=100,
        help="样本数量（sample模式）"
    )

    args = parser.parse_args()

    if args.source == "freihand":
        download_freihand(args.output)
    elif args.source == "sample":
        create_sample_dataset(args.output, args.n_samples)
    elif args.source == "custom" and args.input_dir:
        converter = DatasetConverter(args.output)
        converter.convert_from_images(args.input_dir)
    else:
        logger.error("请指定有效的数据源")


if __name__ == "__main__":
    main()
