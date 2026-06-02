#!/usr/bin/env python3
"""
手部数据采集与自动标注工具

使用MediaPipe检测手部关键点，自动标注并保存为YOLO格式。
可以用电脑摄像头实时采集数据。

Usage:
    python collect_and_label.py --output ./data/hand_keypoints --samples 500

操作说明:
    - 按 's' 保存当前帧
    - 按 'c' 开始/停止连续采集（每0.5秒一帧）
    - 按 'q' 退出
    - 采集时尽量变换手的角度、距离、光照
"""

import argparse
import logging
import os
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class HandDataCollector:
    """手部数据采集器"""

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

        # 初始化MediaPipe
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # 计数器
        self.train_count = len(list((self.output_dir / "labels" / "train").glob("*.txt")))
        self.val_count = len(list((self.output_dir / "labels" / "val").glob("*.txt")))

        # 统计
        self.total_saved = 0
        self.total_failed = 0

    def _create_dirs(self):
        """创建目录结构"""
        dirs = [
            "images/train", "images/val",
            "labels/train", "labels/val",
        ]
        for d in dirs:
            (self.output_dir / d).mkdir(parents=True, exist_ok=True)

    def _mediapipe_to_yolo(self, hand_landmarks, img_width: int, img_height: int) -> str:
        """将MediaPipe关键点转换为YOLO格式

        MediaPipe返回21个关键点，每个有x, y, z（归一化坐标）
        YOLO格式: class_id cx cy w h kp1_x kp1_y kp1_v ...

        Args:
            hand_landmarks: MediaPipe手部关键点
            img_width: 图片宽度
            img_height: 图片高度

        Returns:
            str: YOLO格式标签行
        """
        # 获取所有关键点
        keypoints = []
        x_coords = []
        y_coords = []

        for lm in hand_landmarks.landmark:
            x = lm.x * img_width
            y = lm.y * img_height
            keypoints.append((x, y, 2))  # visibility=2 (可见)
            x_coords.append(x)
            y_coords.append(y)

        # 计算边界框
        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # 添加边距
        padding = 20
        x_min = max(0, x_min - padding)
        y_min = max(0, y_min - padding)
        x_max = min(img_width, x_max + padding)
        y_max = min(img_height, y_max + padding)

        # 归一化
        cx = ((x_min + x_max) / 2) / img_width
        cy = ((y_min + y_max) / 2) / img_height
        w = (x_max - x_min) / img_width
        h = (y_max - y_min) / img_height

        # 构建YOLO格式行
        parts = [f"0 {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"]

        for kp_x, kp_y, kp_v in keypoints:
            norm_x = kp_x / img_width
            norm_y = kp_y / img_height
            parts.append(f"{norm_x:.6f} {norm_y:.6f} {kp_v}")

        return " ".join(parts)

    def process_frame(self, frame: np.ndarray) -> tuple:
        """处理单帧图像

        Args:
            frame: BGR图像

        Returns:
            tuple: (annotated_frame, label_str, success)
        """
        # 转换为RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 检测手部
        results = self.hands.process(rgb)

        annotated = frame.copy()
        label = None
        success = False

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]

            # 绘制关键点
            self.mp_drawing.draw_landmarks(
                annotated,
                hand_landmarks,
                self.mp_hands.HAND_CONNECTIONS,
            )

            # 转换为YOLO格式
            h, w = frame.shape[:2]
            label = self._mediapipe_to_yolo(hand_landmarks, w, h)
            success = True

            # 绘制边界框
            x_coords = [lm.x * w for lm in hand_landmarks.landmark]
            y_coords = [lm.y * h for lm in hand_landmarks.landmark]
            x1, y1 = int(min(x_coords)) - 10, int(min(y_coords)) - 10
            x2, y2 = int(max(x_coords)) + 10, int(max(y_coords)) + 10
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

        return annotated, label, success

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

    def run(self, camera_id: int = 0, target_samples: int = 500):
        """运行采集程序

        Args:
            camera_id: 摄像头ID
            target_samples: 目标样本数量
        """
        logger.info("=" * 50)
        logger.info("手部数据采集工具")
        logger.info("=" * 50)
        logger.info(f"输出目录: {self.output_dir}")
        logger.info(f"目标样本: {target_samples}")
        logger.info(f"当前训练集: {self.train_count} 张")
        logger.info(f"当前验证集: {self.val_count} 张")
        logger.info("")
        logger.info("操作说明:")
        logger.info("  's' - 保存当前帧")
        logger.info("  'c' - 开始/停止连续采集")
        logger.info("  'q' - 退出")
        logger.info("=" * 50)

        # 打开摄像头
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened():
            logger.error(f"无法打开摄像头: {camera_id}")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        continuous_mode = False
        last_save_time = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("摄像头读取失败")
                break

            # 处理帧
            annotated, label, has_hand = self.process_frame(frame)

            # 显示状态
            status_text = f"Saved: {self.total_saved}/{target_samples}"
            cv2.putText(annotated, status_text, (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            mode_text = "Continuous: ON" if continuous_mode else "Continuous: OFF"
            cv2.putText(annotated, mode_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            hand_text = "Hand: Detected" if has_hand else "Hand: Not Found"
            hand_color = (0, 255, 0) if has_hand else (0, 0, 255)
            cv2.putText(annotated, hand_text, (10, 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, hand_color, 2)

            cv2.imshow("Hand Data Collector", annotated)

            # 连续采集模式
            if continuous_mode and has_hand:
                current_time = time.time()
                if current_time - last_save_time >= 0.5:  # 每0.5秒采集一次
                    # 10%概率放入验证集
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
                if has_hand:
                    is_val = np.random.random() < 0.1
                    self.save_sample(frame, label, is_val)
                    logger.info(f"Saved: {self.total_saved}/{target_samples}")
                else:
                    logger.warning("未检测到手部，无法保存")
            elif key == ord('c'):
                continuous_mode = not continuous_mode
                logger.info(f"连续采集模式: {'开启' if continuous_mode else '关闭'}")

        # 清理
        cap.release()
        cv2.destroyAllWindows()
        self.hands.close()

        # 打印统计
        logger.info("=" * 50)
        logger.info("采集完成!")
        logger.info(f"  总保存: {self.total_saved}")
        logger.info(f"  训练集: {self.train_count}")
        logger.info(f"  验证集: {self.val_count}")
        logger.info("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="手部数据采集与自动标注工具")
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
        default=500,
        help="目标样本数量"
    )
    parser.add_argument(
        "--img_size",
        type=int,
        default=640,
        help="图片尺寸"
    )

    args = parser.parse_args()

    collector = HandDataCollector(args.output, args.img_size)
    collector.run(args.camera, args.samples)


if __name__ == "__main__":
    main()
