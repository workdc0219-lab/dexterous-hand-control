"""YOLOv8-pose 手部关键点检测模型训练脚本.

使用 ultralytics API 进行训练，支持命令行参数配置，训练完成后自动导出 ONNX 模型。

Usage:
    python train.py --data ../config/hand_keypoints.yaml --epochs 100 --batch_size 16
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from ultralytics import YOLO

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """解析命令行参数.

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="YOLOv8-pose 手部关键点检测模型训练"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="../config/hand_keypoints.yaml",
        help="数据集配置文件路径 (默认: ../config/hand_keypoints.yaml)",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="训练轮数 (默认: 100)",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="批量大小 (默认: 16)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="输入图片尺寸 (默认: 640)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n-pose.pt",
        help="预训练模型路径 (默认: yolov8n-pose.pt)",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="训练设备，如 '0' 或 'cpu' (默认: 自动选择)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="数据加载线程数 (默认: 8)",
    )
    parser.add_argument(
        "--project",
        type=str,
        default="runs/train",
        help="项目保存目录 (默认: runs/train)",
    )
    parser.add_argument(
        "--name",
        type=str,
        default="hand_pose",
        help="实验名称 (默认: hand_pose)",
    )
    parser.add_argument(
        "--no_export",
        action="store_true",
        help="训练后不自动导出ONNX",
    )
    return parser.parse_args()


def train(args: argparse.Namespace) -> str:
    """执行模型训练.

    Args:
        args: 命令行参数

    Returns:
        str: 最佳模型权重路径
    """
    logger.info("=" * 50)
    logger.info("开始训练 YOLOv8-pose 手部关键点检测模型")
    logger.info("=" * 50)

    # 检查数据集配置文件
    data_path = Path(args.data)
    if not data_path.exists():
        logger.error(f"数据集配置文件不存在: {data_path}")
        sys.exit(1)

    # 加载预训练模型
    logger.info(f"加载预训练模型: {args.model}")
    model = YOLO(args.model)

    # 开始训练
    logger.info(f"训练参数:")
    logger.info(f"  - 数据集: {args.data}")
    logger.info(f"  - 轮数: {args.epochs}")
    logger.info(f"  - 批量大小: {args.batch_size}")
    logger.info(f"  - 图片尺寸: {args.imgsz}")
    logger.info(f"  - 设备: {args.device or '自动'}")
    logger.info(f"  - 工作线程: {args.workers}")

    results = model.train(
        data=str(data_path),
        epochs=args.epochs,
        batch=args.batch_size,
        imgsz=args.imgsz,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        exist_ok=True,
        verbose=True,
    )

    # 获取最佳模型路径
    best_model_path = str(Path(results.save_dir) / "weights" / "best.pt")
    logger.info(f"训练完成！最佳模型保存在: {best_model_path}")

    return best_model_path


def export_onnx(model_path: str, imgsz: int = 640) -> str:
    """将训练好的模型导出为 ONNX 格式.

    Args:
        model_path: 模型权重路径
        imgsz: 输入图片尺寸

    Returns:
        str: ONNX 模型文件路径
    """
    logger.info("=" * 50)
    logger.info("开始导出 ONNX 模型")
    logger.info("=" * 50)

    if not Path(model_path).exists():
        logger.error(f"模型文件不存在: {model_path}")
        sys.exit(1)

    # 加载模型
    model = YOLO(model_path)

    # 导出 ONNX
    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=False,
        simplify=True,
        opset=12,
    )

    logger.info(f"ONNX 模型导出成功: {onnx_path}")
    return onnx_path


def main() -> None:
    """主函数."""
    args = parse_args()

    # 训练
    best_model_path = train(args)

    # 导出 ONNX
    if not args.no_export:
        onnx_path = export_onnx(best_model_path, args.imgsz)
        logger.info(f"全流程完成！")
        logger.info(f"  - 最佳模型: {best_model_path}")
        logger.info(f"  - ONNX 模型: {onnx_path}")
    else:
        logger.info(f"训练完成，已跳过 ONNX 导出")
        logger.info(f"  - 最佳模型: {best_model_path}")


if __name__ == "__main__":
    main()
