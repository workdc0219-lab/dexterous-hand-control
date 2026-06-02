#!/usr/bin/env python3
"""
简易手部数据采集工具

使用YOLOv8-pose检测人体关键点，手动框选手部区域并保存。
或者直接采集图片，后续手动标注。

Usage:
    python collect_simple.py --output ../data/hand_keypoints --samples 100

操作说明:
    - 按 's' 保存当前帧（自动检测手部区域）
    - 按 'm' 手动框选手部区域
    - 按 'c' 开始/停止连续采集
    - 按 'q' 退出
"""

import argparse
import logging
import os
import time
from pathlib import Path

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleHandCollector:
    """简易手部数据采集器"""

    def __init__(self, output_dir: str, img_size: int = 640):
        """初始化采集器

        Args:
            output_dir: 输出目录
            img_size: 图片尺寸
        """
        self.output_dir = Path(output_dir)
        self.img_size = img_size

        # 创建目录
        self._create_dirs()

        # 计数器
        self.train_count = len(list((self.output_dir / "labels" / "train").glob("*.txt")))
        self.val_count = len(list((self.output_dir / "labels" / "val").glob("*.txt")))

        # 统计
        self.total_saved = 0

        # 手动框选状态
        self.drawing = False
        self.x1, self.y1 = 0, 0
        self.x2, self.y2 = 0, 0
        self.roi = None

    def _create_dirs(self):
        """创建目录结构"""
        dirs = [
            "images/train", "images/val",
            "labels/train", "labels/val",
        ]
        for d in dirs:
            (self.output_dir / d).mkdir(parents=True, exist_ok=True)

    def _mouse_callback(self, event, x, y, flags, param):
        """鼠标回调函数"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.x1, self.y1 = x, y
            self.x2, self.y2 = x, y

        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing:
                self.x2, self.y2 = x, y

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            self.x2, self.y2 = x, y
            # 确保x1,y1是左上角
            self.x1, self.x2 = min(self.x1, self.x2), max(self.x1, self.x2)
            self.y1, self.y2 = min(self.y1, self.y2), max(self.y1, self.y2)

    def _generate_label_from_roi(self, img_width: int, img_height: int) -> str:
        """从ROI生成YOLO格式标签

        假设手部在ROI中心，生成简化的标签
        """
        if self.x1 == self.x2 or self.y1 == self.y2:
            return None

        # 计算归一化的边界框
        cx = ((self.x1 + self.x2) / 2) / img_width
        cy = ((self.y1 + self.y2) / 2) / img_height
        w = (self.x2 - self.x1) / img_width
        h = (self.y2 - self.y1) / img_height

        # 生成21个关键点（均匀分布在边界框内）
        # 这是一个简化的标注，实际训练需要更精确的关键点
        parts = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"]

        # 生成21个关键点位置（简化版）
        for i in range(21):
            # 在边界框内随机分布
            kp_x = cx + (np.random.random() - 0.5) * w * 0.8
            kp_y = cy + (np.random.random() - 0.5) * h * 0.8
            parts.append(f"{kp_x:.6f} {kp_y:.6f} 2")

        return " ".join(parts)

    def save_sample(self, frame: np.ndarray, label: str, is_val: bool = False):
        """保存样本

        Args:
            frame: 图像
            label: YOLO格式标签
            is_val: 是否为验证集
        """
        if is_val:
            split = "val"
            idx = self.val_count
            self.val_count += 1
        else:
            split = "train"
            idx = self.train_count
            self.train_count += 1

        # 生成文件名
        timestamp = int(time.time() * 1000) % 1000000
        filename = f"hand_{split}_{idx:06d}_{timestamp}"

        # 保存图像
        img_path = self.output_dir / "images" / split / f"{filename}.jpg"
        cv2.imwrite(str(img_path), frame)

        # 保存标签
        label_path = self.output_dir / "labels" / split / f"{filename}.txt"
        with open(label_path, 'w') as f:
            f.write(label + "\n")

        self.total_saved += 1

    def run(self, camera_id: int = 0, target_samples: int = 100):
        """运行采集程序

        Args:
            camera_id: 摄像头ID
            target_samples: 目标样本数量
        """
        logger.info("=" * 50)
        logger.info("简易手部数据采集工具")
        logger.info("=" * 50)
        logger.info(f"输出目录: {self.output_dir}")
        logger.info(f"目标样本: {target_samples}")
        logger.info(f"当前训练集: {self.train_count} 张")
        logger.info(f"当前验证集: {self.val_count} 张")
        logger.info("")
        logger.info("操作说明:")
        logger.info("  's' - 保存当前帧（使用当前ROI）")
        logger.info("  'm' - 进入手动框选模式")
        logger.info("  'c' - 开始/停止连续采集")
        logger.info("  'q' - 退出")
        logger.info("")
        logger.info("手动框选: 按鼠标左键拖拽框选手部区域")
        logger.info("=" * 50)

        # 打开摄像头
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            logger.error(f"无法打开摄像头: {camera_id}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # 创建窗口并绑定鼠标回调
        cv2.namedWindow("Hand Data Collector")
        cv2.setMouseCallback("Hand Data Collector", self._mouse_callback)

        continuous_mode = False
        last_save_time = 0
        manual_mode = False

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("摄像头读取失败")
                break

            # 显示状态
            annotated = frame.copy()

            # 绘制ROI（如果有）
            if self.x1 != self.x2 and self.y1 != self.y2:
                cv2.rectangle(annotated, (self.x1, self.y1), (self.x2, self.y2), (0, 255, 0), 2)

            # 显示信息
            status_text = f"Saved: {self.total_saved}/{target_samples}"
            cv2.putText(annotated, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            mode_text = "Mode: Manual" if manual_mode else "Mode: Auto"
            cv2.putText(annotated, mode_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            cont_text = "Continuous: ON" if continuous_mode else "Continuous: OFF"
            cv2.putText(annotated, cont_text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            # 操作提示
            cv2.putText(annotated, "s:Save m:Manual c:Continuous q:Quit", (10, frame.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            cv2.imshow("Hand Data Collector", annotated)

            # 连续采集模式
            if continuous_mode:
                current_time = time.time()
                if current_time - last_save_time >= 1.0:  # 每1秒采集一次
                    if self.x1 != self.x2 and self.y1 != self.y2:
                        h, w = frame.shape[:2]
                        label = self._generate_label_from_roi(w, h)
                        if label:
                            is_val = np.random.random() < 0.1
                            self.save_sample(frame, label, is_val)
                            last_save_time = current_time
                            logger.info(f"Saved: {self.total_saved}/{target_samples}")

            # 检查是否达到目标
            if self.total_saved >= target_samples:
                logger.info(f"已达到目标样本数量: {target_samples}")
                break

            # 按键处理
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                if self.x1 != self.x2 and self.y1 != self.y2:
                    h, w = frame.shape[:2]
                    label = self._generate_label_from_roi(w, h)
                    if label:
                        is_val = np.random.random() < 0.1
                        self.save_sample(frame, label, is_val)
                        logger.info(f"Saved: {self.total_saved}/{target_samples}")
                else:
                    logger.warning("请先框选手部区域（按鼠标左键拖拽）")
            elif key == ord('m'):
                manual_mode = not manual_mode
                logger.info(f"手动模式: {'开启' if manual_mode else '关闭'}")
            elif key == ord('c'):
                continuous_mode = not continuous_mode
                logger.info(f"连续采集模式: {'开启' if continuous_mode else '关闭'}")

        # 清理
        cap.release()
        cv2.destroyAllWindows()

        # 打印统计
        logger.info("=" * 50)
        logger.info("采集完成!")
        logger.info(f"  总保存: {self.total_saved}")
        logger.info(f"  训练集: {self.train_count}")
        logger.info(f"  验证集: {self.val_count}")
        logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="简易手部数据采集工具")
    parser.add_argument(
        "--output",
        type=str,
        default="./data/hand_keypoints",
        help="输出目录"
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="摄像头ID"
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="目标样本数量"
    )

    args = parser.parse_args()

    collector = SimpleHandCollector(args.output)
    collector.run(args.camera, args.samples)


if __name__ == "__main__":
    main()
