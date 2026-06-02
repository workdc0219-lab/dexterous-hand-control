"""完整推理 Pipeline 模块.

整合摄像头采集、姿态检测、关键点映射、轨迹平滑和 UART 发送，
提供完整的手部姿态识别到灵巧手控制流程。

Usage:
    python pipeline.py --model best.pt --uart_port /dev/ttyAMA0 --camera 0
"""

import argparse
import logging
import signal
import sys
import time
from typing import Optional

import cv2
import numpy as np

from .pose_detector import DetectionResult, PoseDetector
from .keypoint_mapper import KeypointMapper
from .trajectory_smooth import TrajectorySmooth
from .uart_sender import UARTSender

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class FPSCounter:
    """帧率计数器."""

    def __init__(self, window_size: int = 30) -> None:
        """初始化帧率计数器.

        Args:
            window_size: 计算平均帧率的窗口大小
        """
        self.window_size = window_size
        self._frame_times = []
        self._last_time = time.time()

    def update(self) -> float:
        """更新帧率.

        Returns:
            float: 当前帧率
        """
        current_time = time.time()
        dt = current_time - self._last_time
        self._last_time = current_time

        self._frame_times.append(dt)

        # 保持窗口大小
        if len(self._frame_times) > self.window_size:
            self._frame_times.pop(0)

        return self.fps

    @property
    def fps(self) -> float:
        """获取平均帧率.

        Returns:
            float: 平均帧率
        """
        if len(self._frame_times) == 0:
            return 0.0

        avg_dt = sum(self._frame_times) / len(self._frame_times)

        if avg_dt == 0:
            return 0.0

        return 1.0 / avg_dt


class InferencePipeline:
    """完整推理 Pipeline.

    整合摄像头采集、姿态检测、关键点映射、轨迹平滑和 UART 发送。

    Attributes:
        model_path: 模型文件路径
        uart_port: UART 串口路径
        backend: 推理后端类型
        show_display: 是否显示可视化窗口
        camera_id: 摄像头 ID
    """

    def __init__(
        self,
        model_path: str,
        uart_port: str = "/dev/ttyAMA0",
        uart_baudrate: int = 115200,
        backend: str = "auto",
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        imgsz: int = 640,
        smooth_alpha: float = 0.3,
        smooth_deadband: float = 2.0,
        smooth_max_velocity: float = 180.0,
        show_display: bool = True,
    ) -> None:
        """初始化推理 Pipeline.

        Args:
            model_path: 模型文件路径
            uart_port: UART 串口路径
            uart_baudrate: UART 波特率
            backend: 推理后端类型，可选 'auto', 'pytorch', 'onnx', 'cann'
            conf_threshold: 置信度阈值
            iou_threshold: NMS IoU 阈值
            imgsz: 输入图片尺寸
            smooth_alpha: EMA 平滑系数
            smooth_deadband: 死区阈值（度）
            smooth_max_velocity: 最大角速度（度/秒）
            show_display: 是否显示可视化窗口
        """
        self.model_path = model_path
        self.uart_port = uart_port
        self.backend = backend
        self.show_display = show_display

        # 初始化组件
        logger.info("初始化推理 Pipeline...")

        # 姿态检测器
        logger.info(f"加载模型: {model_path}")
        self.detector = PoseDetector(
            model_path=model_path,
            backend=backend,
            conf_threshold=conf_threshold,
            iou_threshold=iou_threshold,
            imgsz=imgsz,
        )

        # 关键点映射器
        self.mapper = KeypointMapper()

        # 轨迹平滑器
        self.smoother = TrajectorySmooth(
            alpha=smooth_alpha,
            deadband=smooth_deadband,
            max_velocity=smooth_max_velocity,
        )

        # UART 发送器
        self.uart = UARTSender(
            port=uart_port,
            baudrate=uart_baudrate,
        )

        # 帧率计数器
        self.fps_counter = FPSCounter()

        # 运行状态
        self._running = False

        logger.info("推理 Pipeline 初始化完成")

    def _draw_results(
        self,
        frame: np.ndarray,
        detections: list,
        angles: np.ndarray,
        fps: float,
    ) -> np.ndarray:
        """绘制检测结果.

        Args:
            frame: 输入图像
            detections: 检测结果列表
            angles: 关节角度
            fps: 当前帧率

        Returns:
            np.ndarray: 绘制后的图像
        """
        # 绘制检测结果
        for det in detections:
            # 绘制边界框
            x1, y1, x2, y2 = det.bbox.astype(int)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # 绘制置信度
            conf_text = f"{det.confidence:.2f}"
            cv2.putText(
                frame, conf_text, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
            )

            # 绘制关键点
            for kpt in det.keypoints_21:
                x, y = int(kpt[0]), int(kpt[1])
                cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)

            # 绘制骨架连接
            connections = [
                (0, 1), (1, 2), (2, 3), (3, 4),  # 拇指
                (0, 5), (5, 6), (6, 7), (7, 8),  # 食指
                (0, 9), (9, 10), (10, 11), (11, 12),  # 中指
                (0, 13), (13, 14), (14, 15), (15, 16),  # 无名指
                (0, 17), (17, 18), (18, 19), (19, 20),  # 小指
            ]

            for start_idx, end_idx in connections:
                start = det.keypoints_21[start_idx]
                end = det.keypoints_21[end_idx]
                start_point = (int(start[0]), int(start[1]))
                end_point = (int(end[0]), int(end[1]))
                cv2.line(frame, start_point, end_point, (255, 0, 0), 2)

        # 绘制角度信息
        y_offset = 30
        finger_names = ["拇指", "食指", "中指", "无名指", "小指"]
        for i, name in enumerate(finger_names):
            text = f"{name}: {angles[i]:.1f}°"
            cv2.putText(
                frame, text, (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2
            )
            y_offset += 25

        # 绘制帧率
        fps_text = f"FPS: {fps:.1f}"
        cv2.putText(
            frame, fps_text, (10, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

        # 绘制 UART 状态
        uart_status = "UART: OK" if self.uart.is_connected else "UART: FAIL"
        uart_color = (0, 255, 0) if self.uart.is_connected else (0, 0, 255)
        cv2.putText(
            frame, uart_status, (frame.shape[1] - 150, frame.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, uart_color, 2
        )

        return frame

    def _signal_handler(self, sig, frame) -> None:
        """信号处理器（Ctrl+C）.

        Args:
            sig: 信号
            frame: 帧
        """
        logger.info("收到退出信号，正在停止...")
        self._running = False

    def run(self, camera_id: int = 0) -> None:
        """运行推理 Pipeline.

        Args:
            camera_id: 摄像头 ID
        """
        logger.info("=" * 50)
        logger.info("启动推理 Pipeline")
        logger.info("=" * 50)

        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)

        # 打开摄像头
        logger.info(f"打开摄像头: {camera_id}")
        cap = cv2.VideoCapture(camera_id)

        if not cap.isOpened():
            logger.error(f"无法打开摄像头: {camera_id}")
            sys.exit(1)

        # 设置摄像头参数
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        logger.info("按 Ctrl+C 退出")
        logger.info("-" * 50)

        self._running = True
        default_angles = np.zeros(5)

        try:
            while self._running:
                # 采集帧
                ret, frame = cap.read()
                if not ret:
                    logger.warning("摄像头读取失败，尝试重连...")
                    time.sleep(1)
                    cap.release()
                    cap = cv2.VideoCapture(camera_id)
                    if not cap.isOpened():
                        logger.error("摄像头重连失败")
                        break
                    continue

                # 姿态检测
                try:
                    detections = self.detector.detect(frame)
                except Exception as e:
                    logger.error(f"姿态检测失败: {e}")
                    detections = []

                # 处理检测结果
                if detections:
                    # 使用置信度最高的检测结果
                    best_detection = max(detections, key=lambda d: d.confidence)

                    # 关键点映射
                    angles = self.mapper.map_to_angles(best_detection.keypoints_21)
                else:
                    angles = default_angles

                # 轨迹平滑
                smoothed_angles = self.smoother.smooth(angles)

                # UART 发送
                self.uart.send_angles(smoothed_angles)

                # 更新帧率
                fps = self.fps_counter.update()

                # 显示结果
                if self.show_display:
                    display_frame = self._draw_results(
                        frame.copy(), detections, smoothed_angles, fps
                    )
                    cv2.imshow("Hand Pose Control", display_frame)

                    # 检查按键
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        logger.info("用户按下 'q' 退出")
                        break
                    elif key == ord('r'):
                        logger.info("重置轨迹平滑器")
                        self.smoother.reset()

        except Exception as e:
            logger.error(f"Pipeline 运行错误: {e}")

        finally:
            # 清理资源
            logger.info("清理资源...")
            cap.release()

            if self.show_display:
                cv2.destroyAllWindows()

            self.release()

            # 打印统计信息
            uart_stats = self.uart.stats
            logger.info("=" * 50)
            logger.info("运行统计:")
            logger.info(f"  平均帧率: {fps:.1f} FPS")
            logger.info(f"  UART 发送次数: {uart_stats['send_count']}")
            logger.info(f"  UART 错误次数: {uart_stats['error_count']}")
            logger.info("=" * 50)

    def release(self) -> None:
        """释放资源."""
        self.detector.release()
        self.uart.close()
        logger.info("Pipeline 资源已释放")

    def __del__(self) -> None:
        """析构函数."""
        self.release()

    def __enter__(self):
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口."""
        self.release()


def parse_args() -> argparse.Namespace:
    """解析命令行参数.

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="手部姿态识别推理 Pipeline"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="模型文件路径（支持 .pt, .onnx, .om）",
    )
    parser.add_argument(
        "--uart_port",
        type=str,
        default="/dev/ttyAMA0",
        help="UART 串口路径 (默认: /dev/ttyAMA0)",
    )
    parser.add_argument(
        "--uart_baudrate",
        type=int,
        default=115200,
        help="UART 波特率 (默认: 115200)",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=0,
        help="摄像头 ID (默认: 0)",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="auto",
        choices=["auto", "pytorch", "onnx", "cann"],
        help="推理后端 (默认: auto)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="置信度阈值 (默认: 0.5)",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=0.45,
        help="NMS IoU 阈值 (默认: 0.45)",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="输入图片尺寸 (默认: 640)",
    )
    parser.add_argument(
        "--smooth_alpha",
        type=float,
        default=0.3,
        help="EMA 平滑系数 (默认: 0.3)",
    )
    parser.add_argument(
        "--smooth_deadband",
        type=float,
        default=2.0,
        help="死区阈值（度）(默认: 2.0)",
    )
    parser.add_argument(
        "--smooth_max_velocity",
        type=float,
        default=180.0,
        help="最大角速度（度/秒）(默认: 180.0)",
    )
    parser.add_argument(
        "--no_display",
        action="store_true",
        help="不显示可视化窗口",
    )
    return parser.parse_args()


def main() -> None:
    """主函数."""
    args = parse_args()

    # 创建 Pipeline
    pipeline = InferencePipeline(
        model_path=args.model,
        uart_port=args.uart_port,
        uart_baudrate=args.uart_baudrate,
        backend=args.backend,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        imgsz=args.imgsz,
        smooth_alpha=args.smooth_alpha,
        smooth_deadband=args.smooth_deadband,
        smooth_max_velocity=args.smooth_max_velocity,
        show_display=not args.no_display,
    )

    # 运行
    pipeline.run(camera_id=args.camera)


if __name__ == "__main__":
    main()
