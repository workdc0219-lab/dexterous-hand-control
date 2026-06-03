#!/usr/bin/env python3
"""
手部关键点检测模型训练脚本

使用YOLOv8-pose训练手部关键点检测模型。

Usage:
    # 1. 先采集数据
    python collect_and_label.py --output ./data/hand_keypoints --samples 500

    # 2. 训练模型
    python train_hand_model.py --data ./data/hand_keypoints --epochs 100

    # 3. 导出ONNX
    python train_hand_model.py --export --weights runs/train/hand_pose/weights/best.pt
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_dataset_yaml(data_dir: str, output_path: str = None) -> str:
    """创建数据集YAML配置文件

    Args:
        data_dir: 数据集目录
        output_path: 输出路径（默认在数据集目录下）

    Returns:
        str: YAML文件路径
    """
    data_path = Path(data_dir)

    if output_path is None:
        output_path = str(data_path / "dataset.yaml")

    yaml_content = f"""# Hand Keypoints Dataset Configuration
# 由collect_and_label.py自动生成

# 数据集路径
path: {data_path.absolute()}
train: images/train
val: images/val

# 关键点配置
kpt_shape: [21, 3]  # 21个关键点, 每个(x, y, visibility)
flip_idx: [0, 4, 3, 2, 1, 8, 7, 6, 5, 12, 11, 10, 9, 16, 15, 14, 13, 20, 19, 18, 17]

# 类别
nc: 1
names:
  0: hand
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)

    logger.info(f"数据集配置已保存: {output_path}")
    return output_path


def train(args):
    """训练模型

    Args:
        args: 命令行参数
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("请先安装ultralytics: pip install ultralytics")
        sys.exit(1)

    # 检查数据集
    data_path = Path(args.data)
    if not data_path.exists():
        logger.error(f"数据集目录不存在: {data_path}")
        sys.exit(1)

    # 检查是否有图片
    train_images = list((data_path / "images" / "train").glob("*.jpg"))
    if len(train_images) == 0:
        logger.error(f"训练集为空，请先运行collect_and_label.py采集数据")
        sys.exit(1)

    logger.info(f"训练集图片数量: {len(train_images)}")

    # 创建数据集配置
    yaml_path = create_dataset_yaml(args.data)

    # 加载预训练模型
    logger.info(f"加载预训练模型: {args.model}")
    model = YOLO(args.model)

    # 开始训练
    logger.info("=" * 50)
    logger.info("开始训练")
    logger.info("=" * 50)

    results = model.train(
        data=yaml_path,
        epochs=args.epochs,
        batch=args.batch_size,
        imgsz=args.imgsz,
        device=args.device,
        workers=args.workers,
        project=args.project,
        name=args.name,
        exist_ok=True,
        verbose=True,
        # 数据增强参数
        augment=True,
        hsv_h=0.015,      # 色调增强
        hsv_s=0.7,        # 饱和度增强
        hsv_v=0.4,        # 亮度增强
        degrees=10.0,     # 旋转角度
        translate=0.1,    # 平移
        scale=0.5,        # 缩放
        fliplr=0.5,       # 水平翻转
    )

    # 获取最佳模型路径
    best_model_path = str(Path(results.save_dir) / "weights" / "best.pt")
    logger.info(f"训练完成！最佳模型: {best_model_path}")

    return best_model_path


def export_onnx(args):
    """导出ONNX模型

    Args:
        args: 命令行参数
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("请先安装ultralytics: pip install ultralytics")
        sys.exit(1)

    if not Path(args.weights).exists():
        logger.error(f"模型文件不存在: {args.weights}")
        sys.exit(1)

    logger.info(f"加载模型: {args.weights}")
    model = YOLO(args.weights)

    logger.info("导出ONNX格式...")
    onnx_path = model.export(
        format="onnx",
        imgsz=args.imgsz,
        simplify=True,
        opset=12,
    )

    logger.info(f"ONNX模型已导出: {onnx_path}")
    return onnx_path


def main():
    parser = argparse.ArgumentParser(description="手部关键点检测模型训练")

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # 训练命令
    train_parser = subparsers.add_parser("train", help="训练模型")
    train_parser.add_argument("--data", type=str, default="./data/hand_keypoints", help="数据集目录")
    train_parser.add_argument("--model", type=str, default="yolov8n-pose.pt", help="预训练模型")
    train_parser.add_argument("--epochs", type=int, default=100, help="训练轮数")
    train_parser.add_argument("--batch_size", type=int, default=16, help="批量大小")
    train_parser.add_argument("--imgsz", type=int, default=640, help="图片尺寸")
    train_parser.add_argument("--device", type=str, default=None, help="设备 (0/cpu)")
    train_parser.add_argument("--workers", type=int, default=4, help="数据加载线程数")
    train_parser.add_argument("--project", type=str, default="runs/train", help="项目目录")
    train_parser.add_argument("--name", type=str, default="hand_pose", help="实验名称")

    # 导出命令
    export_parser = subparsers.add_parser("export", help="导出ONNX模型")
    export_parser.add_argument("--weights", type=str, required=True, help="模型权重路径")
    export_parser.add_argument("--imgsz", type=int, default=640, help="图片尺寸")

    args = parser.parse_args()

    # 根据子命令执行相应操作
    if args.command == "train":
        train(args)
    elif args.command == "export":
        export_onnx(args)
    else:
        # 如果没有指定子命令，默认执行训练（兼容旧用法）
        if not args.command:
            args.command = "train"
            train(args)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
