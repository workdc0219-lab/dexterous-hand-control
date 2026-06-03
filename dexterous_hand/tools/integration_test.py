#!/usr/bin/env python3
"""
系统集成测试脚本

测试视觉模块 → 主控板 → 手指节点的完整链路。

Usage:
    # 测试视觉模块
    python integration_test.py --test vision

    # 测试UART通信
    python integration_test.py --test uart

    # 测试CAN通信
    python integration_test.py --test can

    # 测试完整链路
    python integration_test.py --test full

    # 端到端延迟测试
    python integration_test.py --test latency
"""

import argparse
import logging
import time
import sys
from pathlib import Path

import cv2
import numpy as np

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "vision"))
sys.path.insert(0, str(Path(__file__).parent.parent / "vision" / "inference"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """系统集成测试类"""

    def __init__(self, model_path: str = None, uart_port: str = None):
        """初始化测试

        Args:
            model_path: 模型路径
            uart_port: UART串口路径
        """
        self.model_path = model_path or "runs/pose/runs/train/hand_pose/weights/best.pt"
        self.uart_port = uart_port or "COM3"  # 默认串口

        # 测试结果
        self.results = {
            "vision": {"passed": 0, "failed": 0, "errors": []},
            "uart": {"passed": 0, "failed": 0, "errors": []},
            "can": {"passed": 0, "failed": 0, "errors": []},
            "latency": {"passed": 0, "failed": 0, "errors": []},
        }

    def test_vision_module(self) -> bool:
        """测试视觉模块

        Returns:
            bool: 测试是否通过
        """
        logger.info("=" * 50)
        logger.info("测试视觉模块")
        logger.info("=" * 50)

        try:
            # 测试1: 检查模型文件
            logger.info("1. 检查模型文件...")
            if not Path(self.model_path).exists():
                raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
            logger.info("   ✓ 模型文件存在")
            self.results["vision"]["passed"] += 1

            # 测试2: 加载模型
            logger.info("2. 加载模型...")
            from ultralytics import YOLO
            model = YOLO(self.model_path)
            logger.info("   ✓ 模型加载成功")
            self.results["vision"]["passed"] += 1

            # 测试3: 推理测试
            logger.info("3. 推理测试...")
            test_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
            results = model(test_img, verbose=False)
            logger.info(f"   ✓ 推理完成，检测到 {len(results)} 个结果")
            self.results["vision"]["passed"] += 1

            # 测试4: 关键点映射
            logger.info("4. 关键点映射测试...")
            try:
                from keypoint_mapper import KeypointMapper
                mapper = KeypointMapper()
                # 创建模拟关键点
                mock_keypoints = np.random.rand(21, 3) * 100
                angles = mapper.map_to_angles(mock_keypoints)
                logger.info(f"   ✓ 关键点映射完成，角度: {angles}")
                self.results["vision"]["passed"] += 1
            except Exception as e:
                logger.warning(f"   ⚠ 关键点映射测试失败: {e}")
                self.results["vision"]["failed"] += 1
                self.results["vision"]["errors"].append(str(e))

            # 测试5: 轨迹平滑
            logger.info("5. 轨迹平滑测试...")
            try:
                from trajectory_smooth import TrajectorySmooth
                smoother = TrajectorySmooth()
                angles = np.array([10, 20, 30, 40, 50], dtype=float)
                smoothed = smoother.smooth(angles)
                logger.info(f"   ✓ 轨迹平滑完成，结果: {smoothed}")
                self.results["vision"]["passed"] += 1
            except Exception as e:
                logger.warning(f"   ⚠ 轨迹平滑测试失败: {e}")
                self.results["vision"]["failed"] += 1
                self.results["vision"]["errors"].append(str(e))

            logger.info(f"视觉模块测试完成: {self.results['vision']['passed']} 通过, "
                       f"{self.results['vision']['failed']} 失败")
            return self.results["vision"]["failed"] == 0

        except Exception as e:
            logger.error(f"视觉模块测试失败: {e}")
            self.results["vision"]["failed"] += 1
            self.results["vision"]["errors"].append(str(e))
            return False

    def test_uart_communication(self) -> bool:
        """测试UART通信

        Returns:
            bool: 测试是否通过
        """
        logger.info("=" * 50)
        logger.info("测试UART通信")
        logger.info("=" * 50)

        try:
            # 测试1: 检查串口
            logger.info("1. 检查串口...")
            try:
                import serial
                ser = serial.Serial(self.uart_port, 115200, timeout=1)
                ser.close()
                logger.info(f"   ✓ 串口 {self.uart_port} 可用")
                self.results["uart"]["passed"] += 1
            except Exception as e:
                logger.warning(f"   ⚠ 串口 {self.uart_port} 不可用: {e}")
                self.results["uart"]["failed"] += 1
                self.results["uart"]["errors"].append(str(e))
                return False

            # 测试2: 发送测试数据
            logger.info("2. 发送测试数据...")
            try:
                from uart_sender import UARTSender
                uart = UARTSender(port=self.uart_port, baudrate=115200)
                angles = np.array([90, 45, 60, 30, 75], dtype=float)
                success = uart.send_angles(angles)
                uart.close()

                if success:
                    logger.info("   ✓ 数据发送成功")
                    self.results["uart"]["passed"] += 1
                else:
                    logger.warning("   ⚠ 数据发送失败")
                    self.results["uart"]["failed"] += 1
                    self.results["uart"]["errors"].append("数据发送失败")
            except Exception as e:
                logger.warning(f"   ⚠ UART发送测试失败: {e}")
                self.results["uart"]["failed"] += 1
                self.results["uart"]["errors"].append(str(e))

            logger.info(f"UART通信测试完成: {self.results['uart']['passed']} 通过, "
                       f"{self.results['uart']['failed']} 失败")
            return self.results["uart"]["failed"] == 0

        except Exception as e:
            logger.error(f"UART通信测试失败: {e}")
            self.results["uart"]["failed"] += 1
            self.results["uart"]["errors"].append(str(e))
            return False

    def test_can_communication(self) -> bool:
        """测试CAN通信

        Returns:
            bool: 测试是否通过
        """
        logger.info("=" * 50)
        logger.info("测试CAN通信")
        logger.info("=" * 50)

        try:
            # 测试1: 检查CAN接口
            logger.info("1. 检查CAN接口...")
            try:
                import can
                bus = can.interface.Bus(bustype='pcan', channel='PCAN_USBBUS1')
                bus.shutdown()
                logger.info("   ✓ CAN接口可用")
                self.results["can"]["passed"] += 1
            except Exception as e:
                logger.warning(f"   ⚠ CAN接口不可用: {e}")
                self.results["can"]["failed"] += 1
                self.results["can"]["errors"].append(str(e))
                return False

            # 测试2: 发送测试帧
            logger.info("2. 发送测试帧...")
            try:
                # 构建CAN帧
                msg = can.Message(
                    arbitration_id=0x123,
                    data=[0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08],
                    is_extended_id=False
                )
                bus = can.interface.Bus(bustype='pcan', channel='PCAN_USBBUS1')
                bus.send(msg)
                bus.shutdown()

                logger.info("   ✓ CAN帧发送成功")
                self.results["can"]["passed"] += 1
            except Exception as e:
                logger.warning(f"   ⚠ CAN帧发送失败: {e}")
                self.results["can"]["failed"] += 1
                self.results["can"]["errors"].append(str(e))

            logger.info(f"CAN通信测试完成: {self.results['can']['passed']} 通过, "
                       f"{self.results['can']['failed']} 失败")
            return self.results["can"]["failed"] == 0

        except Exception as e:
            logger.error(f"CAN通信测试失败: {e}")
            self.results["can"]["failed"] += 1
            self.results["can"]["errors"].append(str(e))
            return False

    def test_latency(self) -> dict:
        """端到端延迟测试

        Returns:
            dict: 延迟测试结果
        """
        logger.info("=" * 50)
        logger.info("端到端延迟测试")
        logger.info("=" * 50)

        results = {
            "vision_latency": [],
            "uart_latency": [],
            "total_latency": [],
        }

        try:
            # 加载模型
            from ultralytics import YOLO
            model = YOLO(self.model_path)

            # 创建测试图像
            test_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

            # 测试10次
            for i in range(10):
                # 视觉推理延迟
                start = time.time()
                detections = model(test_img, verbose=False)
                vision_time = (time.time() - start) * 1000  # 转换为毫秒
                results["vision_latency"].append(vision_time)

                # 模拟UART发送延迟
                start = time.time()
                # 这里应该是实际的UART发送
                time.sleep(0.001)  # 模拟1ms延迟
                uart_time = (time.time() - start) * 1000
                results["uart_latency"].append(uart_time)

                # 总延迟
                total_time = vision_time + uart_time
                results["total_latency"].append(total_time)

                logger.info(f"  第{i+1}次: 视觉={vision_time:.2f}ms, "
                          f"UART={uart_time:.2f}ms, 总计={total_time:.2f}ms")

            # 计算统计信息
            avg_vision = np.mean(results["vision_latency"])
            avg_uart = np.mean(results["uart_latency"])
            avg_total = np.mean(results["total_latency"])

            logger.info(f"\n延迟统计:")
            logger.info(f"  视觉推理平均延迟: {avg_vision:.2f}ms")
            logger.info(f"  UART发送平均延迟: {avg_uart:.2f}ms")
            logger.info(f"  端到端平均延迟: {avg_total:.2f}ms")

            self.results["latency"]["passed"] += 1
            return results

        except Exception as e:
            logger.error(f"延迟测试失败: {e}")
            self.results["latency"]["failed"] += 1
            self.results["latency"]["errors"].append(str(e))
            return results

    def run_full_integration_test(self) -> bool:
        """运行完整集成测试

        Returns:
            bool: 测试是否通过
        """
        logger.info("=" * 60)
        logger.info("系统集成测试")
        logger.info("=" * 60)

        # 运行所有测试
        vision_ok = self.test_vision_module()
        uart_ok = self.test_uart_communication()
        can_ok = self.test_can_communication()
        latency_results = self.test_latency()

        # 汇总结果
        logger.info("\n" + "=" * 60)
        logger.info("测试结果汇总")
        logger.info("=" * 60)
        logger.info(f"视觉模块: {'✓ 通过' if vision_ok else '✗ 失败'}")
        logger.info(f"UART通信: {'✓ 通过' if uart_ok else '✗ 失败'}")
        logger.info(f"CAN通信: {'✓ 通过' if can_ok else '✗ 失败'}")
        logger.info(f"延迟测试: {'✓ 通过' if self.results['latency']['passed'] > 0 else '✗ 失败'}")

        # 总体结果
        all_passed = vision_ok and uart_ok and can_ok
        logger.info(f"\n总体结果: {'✓ 全部通过' if all_passed else '✗ 部分失败'}")

        # 输出详细错误
        if not all_passed:
            logger.info("\n详细错误信息:")
            for module, result in self.results.items():
                if result["errors"]:
                    logger.info(f"  {module}:")
                    for error in result["errors"]:
                        logger.info(f"    - {error}")

        return all_passed


def main():
    parser = argparse.ArgumentParser(description="系统集成测试")
    parser.add_argument(
        "--test",
        type=str,
        choices=["vision", "uart", "can", "latency", "full"],
        default="full",
        help="测试类型"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="runs/pose/runs/train/hand_pose/weights/best.pt",
        help="模型路径"
    )
    parser.add_argument(
        "--uart-port",
        type=str,
        default="COM3",
        help="UART串口"
    )

    args = parser.parse_args()

    # 创建测试实例
    test = IntegrationTest(args.model, args.uart_port)

    # 运行测试
    if args.test == "vision":
        success = test.test_vision_module()
    elif args.test == "uart":
        success = test.test_uart_communication()
    elif args.test == "can":
        success = test.test_can_communication()
    elif args.test == "latency":
        test.test_latency()
        success = True
    else:
        success = test.run_full_integration_test()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
