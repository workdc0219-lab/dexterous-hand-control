"""ONNX 模型导出与验证脚本.

从 best.pt 导出 ONNX 模型，并验证模型可加载性，打印输入输出 shape。

Usage:
    python export_onnx.py --model runs/train/hand_pose/weights/best.pt
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
import onnx
import onnxruntime as ort
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
        description="YOLOv8-pose ONNX 模型导出与验证"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="输入模型路径 (best.pt)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="输入图片尺寸 (默认: 640)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="输出 ONNX 文件路径 (默认: 与输入模型同目录)",
    )
    parser.add_argument(
        "--simplify",
        action="store_true",
        default=True,
        help="是否简化 ONNX 模型 (默认: True)",
    )
    parser.add_argument(
        "--opset",
        type=int,
        default=12,
        help="ONNX opset 版本 (默认: 12)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="是否验证导出的 ONNX 模型 (默认: True)",
    )
    return parser.parse_args()


def export_to_onnx(
    model_path: str,
    imgsz: int = 640,
    simplify: bool = True,
    opset: int = 12,
) -> str:
    """将 PyTorch 模型导出为 ONNX 格式.

    Args:
        model_path: PyTorch 模型路径
        imgsz: 输入图片尺寸
        simplify: 是否简化模型
        opset: ONNX opset 版本

    Returns:
        str: 导出的 ONNX 文件路径
    """
    logger.info(f"加载模型: {model_path}")

    if not Path(model_path).exists():
        logger.error(f"模型文件不存在: {model_path}")
        sys.exit(1)

    # 加载模型
    model = YOLO(model_path)

    # 导出 ONNX
    logger.info("开始导出 ONNX 模型...")
    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=False,
        simplify=simplify,
        opset=opset,
    )

    logger.info(f"ONNX 模型导出成功: {onnx_path}")
    return str(onnx_path)


def verify_onnx(onnx_path: str) -> bool:
    """验证 ONNX 模型的有效性.

    Args:
        onnx_path: ONNX 模型文件路径

    Returns:
        bool: 验证是否通过
    """
    logger.info("=" * 50)
    logger.info("验证 ONNX 模型")
    logger.info("=" * 50)

    try:
        # 1. 使用 onnx 库验证模型结构
        logger.info("1. 验证模型结构...")
        model = onnx.load(onnx_path)
        onnx.checker.check_model(model)
        logger.info("   模型结构验证通过")

        # 2. 使用 onnxruntime 加载模型
        logger.info("2. 加载 ONNX Runtime 会话...")
        session = ort.InferenceSession(onnx_path)
        logger.info("   ONNX Runtime 加载成功")

        # 3. 打印模型输入信息
        logger.info("3. 模型输入信息:")
        for input_meta in session.get_inputs():
            logger.info(f"   - 名称: {input_meta.name}")
            logger.info(f"     Shape: {input_meta.shape}")
            logger.info(f"     类型: {input_meta.type}")

        # 4. 打印模型输出信息
        logger.info("4. 模型输出信息:")
        for output_meta in session.get_outputs():
            logger.info(f"   - 名称: {output_meta.name}")
            logger.info(f"     Shape: {output_meta.shape}")
            logger.info(f"     类型: {output_meta.type}")

        # 5. 测试推理
        logger.info("5. 测试推理...")
        input_meta = session.get_inputs()[0]
        input_shape = input_meta.shape

        # 创建随机输入
        if isinstance(input_shape[0], str):
            # 动态 batch size
            test_shape = [1] + list(input_shape[1:])
        else:
            test_shape = list(input_shape)

        dummy_input = np.random.randn(*test_shape).astype(np.float32)

        # 执行推理
        outputs = session.run(None, {input_meta.name: dummy_input})

        logger.info(f"   推理测试成功!")
        logger.info(f"   输入 shape: {dummy_input.shape}")
        logger.info(f"   输出数量: {len(outputs)}")
        for i, output in enumerate(outputs):
            logger.info(f"   输出 {i} shape: {output.shape}")

        logger.info("=" * 50)
        logger.info("ONNX 模型验证全部通过!")
        logger.info("=" * 50)

        return True

    except Exception as e:
        logger.error(f"ONNX 模型验证失败: {e}")
        return False


def get_output_path(model_path: str) -> str:
    """获取 ONNX 输出文件路径.

    Args:
        model_path: 输入模型路径

    Returns:
        str: ONNX 输出文件路径
    """
    model_dir = Path(model_path).parent
    return str(model_dir / "best.onnx")


def main() -> None:
    """主函数."""
    args = parse_args()

    # 导出 ONNX
    onnx_path = export_to_onnx(
        model_path=args.model,
        imgsz=args.imgsz,
        simplify=args.simplify,
        opset=args.opset,
    )

    # 验证模型
    if args.verify:
        success = verify_onnx(onnx_path)
        if not success:
            logger.error("ONNX 模型验证失败，请检查模型")
            sys.exit(1)

    logger.info("全部完成!")
    logger.info(f"ONNX 模型路径: {onnx_path}")


if __name__ == "__main__":
    main()
