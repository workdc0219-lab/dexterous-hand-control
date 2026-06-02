"""灵巧手视觉推理模块.

本模块提供完整的手部姿态识别和灵巧手控制流程，包括：
- 姿态检测（支持 PyTorch、ONNX Runtime、CANN ACL 后端）
- 关键点到关节角度映射
- 轨迹平滑（EMA + 死区 + 速度限制）
- UART 串口通信
- 完整推理 Pipeline

Usage:
    from inference import PoseDetector, KeypointMapper, TrajectorySmooth, UARTSender
    from inference import InferencePipeline

    # 使用完整 Pipeline
    pipeline = InferencePipeline(model_path="best.pt", uart_port="/dev/ttyAMA0")
    pipeline.run(camera_id=0)

    # 或者单独使用各组件
    detector = PoseDetector(model_path="best.pt")
    mapper = KeypointMapper()
    smoother = TrajectorySmooth()
    uart = UARTSender()
"""

from .keypoint_mapper import KeypointIndex, KeypointMapper, JointLimits
from .pipeline import InferencePipeline
from .pose_detector import Backend, DetectionResult, PoseDetector
from .trajectory_smooth import TrajectorySmooth
from .uart_sender import UARTSender

__version__ = "1.0.0"
__author__ = "Dexterous Hand Project"

__all__ = [
    # 主要类
    "PoseDetector",
    "KeypointMapper",
    "TrajectorySmooth",
    "UARTSender",
    "InferencePipeline",
    # 数据类
    "DetectionResult",
    "JointLimits",
    "KeypointIndex",
    # 枚举
    "Backend",
]

# 版本信息
VERSION_INFO = {
    "version": __version__,
    "components": [
        "pose_detector",
        "keypoint_mapper",
        "trajectory_smooth",
        "uart_sender",
        "pipeline",
    ],
    "supported_backends": ["pytorch", "onnx", "cann"],
    "supported_models": [".pt", ".onnx", ".om"],
}


def get_version() -> str:
    """获取模块版本号.

    Returns:
        str: 版本号
    """
    return __version__


def get_version_info() -> dict:
    """获取详细版本信息.

    Returns:
        dict: 版本信息字典
    """
    return VERSION_INFO.copy()
