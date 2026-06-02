"""UART 串口发送模块.

通过 UART 串口与 STM32 主控通信，发送 5 个手指的关节角度。
帧格式: [0xAA][5×angle(2B, big-endian)][CRC8][0x55]

Usage:
    python uart_sender.py --port /dev/ttyAMA0 --test
"""

import argparse
import logging
import struct
import sys
import time
from typing import Optional

import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 帧格式常量
FRAME_HEADER = 0xAA
FRAME_TAIL = 0x55
NUM_JOINTS = 5
ANGLE_BYTES = 2  # 每个角度 2 字节


def calculate_crc8(data: bytes) -> int:
    """计算 CRC8 校验值.

    使用多项式 0x07 (CRC-8) 进行计算。

    Args:
        data: 输入数据

    Returns:
        int: CRC8 校验值
    """
    crc = 0x00
    polynomial = 0x07

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    return crc


class UARTSender:
    """UART 串口发送器.

    通过 UART 串口发送关节角度到 STM32 主控。
    支持自动重连和错误处理。

    Attributes:
        port: 串口设备路径
        baudrate: 波特率
        timeout: 超时时间（秒）
    """

    def __init__(
        self,
        port: str = "/dev/ttyAMA0",
        baudrate: int = 115200,
        timeout: float = 1.0,
        auto_reconnect: bool = True,
    ) -> None:
        """初始化 UART 发送器.

        Args:
            port: 串口设备路径，默认 /dev/ttyAMA0
            baudrate: 波特率，默认 115200
            timeout: 超时时间（秒），默认 1.0
            auto_reconnect: 是否自动重连，默认 True
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect

        self._serial = None
        self._connected = False
        self._last_send_time = 0.0
        self._send_count = 0
        self._error_count = 0

        # 尝试连接
        self._connect()

    def _connect(self) -> bool:
        """建立串口连接.

        Returns:
            bool: 连接是否成功
        """
        try:
            import serial
        except ImportError:
            logger.error("pyserial 未安装，请执行: pip install pyserial")
            return False

        try:
            # 关闭已有连接
            if self._serial is not None:
                self._serial.close()

            # 打开串口
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )

            self._connected = True
            logger.info(f"UART 连接成功: {self.port} @ {self.baudrate}")
            return True

        except Exception as e:
            logger.error(f"UART 连接失败: {e}")
            self._connected = False
            return False

    def _reconnect(self) -> bool:
        """重新连接串口.

        Returns:
            bool: 重连是否成功
        """
        logger.info("尝试重新连接 UART...")
        return self._connect()

    def _pack_angles(self, angles: np.ndarray) -> bytes:
        """将角度打包为字节流.

        角度范围 [0, 180] 映射为 [0, 18000]（精度 0.01 度）。

        Args:
            angles: 5 个手指角度 [thumb, index, middle, ring, pinky]

        Returns:
            bytes: 打包后的字节流
        """
        # 验证输入
        if len(angles) != NUM_JOINTS:
            raise ValueError(f"角度数量应为 {NUM_JOINTS}，实际为 {len(angles)}")

        # 角度限幅 [0, 180]
        angles = np.clip(angles, 0.0, 180.0)

        # 转换为整数（精度 0.01 度）
        angle_ints = (angles * 100).astype(np.uint16)

        # 打包为 big-endian 字节流
        packed = b""
        for angle in angle_ints:
            packed += struct.pack(">H", angle)

        return packed

    def _build_frame(self, angles: np.ndarray) -> bytes:
        """构建发送帧.

        帧格式: [0xAA][5×angle(2B, big-endian)][CRC8][0x55]

        Args:
            angles: 5 个手指角度

        Returns:
            bytes: 完整的发送帧
        """
        # 打包角度数据
        angle_bytes = self._pack_angles(angles)

        # 计算 CRC8（对角度数据计算）
        crc = calculate_crc8(angle_bytes)

        # 构建帧
        frame = bytearray()
        frame.append(FRAME_HEADER)  # 帧头
        frame.extend(angle_bytes)   # 角度数据 (5 × 2 bytes)
        frame.append(crc)           # CRC8 校验
        frame.append(FRAME_TAIL)    # 帧尾

        return bytes(frame)

    def send_angles(self, angles: np.ndarray) -> bool:
        """发送关节角度.

        Args:
            angles: 5 个手指角度 [thumb, index, middle, ring, pinky]，单位：度

        Returns:
            bool: 发送是否成功
        """
        # 检查连接
        if not self._connected or self._serial is None:
            if self.auto_reconnect:
                if not self._reconnect():
                    return False
            else:
                logger.error("UART 未连接")
                return False

        try:
            # 构建帧
            frame = self._build_frame(angles)

            # 发送数据
            bytes_written = self._serial.write(frame)

            # 等待发送完成
            self._serial.flush()

            # 更新统计
            self._last_send_time = time.time()
            self._send_count += 1

            if bytes_written != len(frame):
                logger.warning(f"发送字节数不匹配: {bytes_written} != {len(frame)}")

            return True

        except Exception as e:
            logger.error(f"UART 发送失败: {e}")
            self._error_count += 1

            # 标记连接断开
            self._connected = False

            # 尝试重连
            if self.auto_reconnect:
                self._reconnect()

            return False

    def close(self) -> None:
        """关闭串口连接."""
        if self._serial is not None:
            try:
                self._serial.close()
                logger.info("UART 连接已关闭")
            except Exception as e:
                logger.warning(f"关闭 UART 连接时出错: {e}")

        self._connected = False
        self._serial = None

    @property
    def is_connected(self) -> bool:
        """检查是否已连接.

        Returns:
            bool: 是否已连接
        """
        return self._connected

    @property
    def stats(self) -> dict:
        """获取发送统计信息.

        Returns:
            dict: 统计信息
        """
        return {
            "connected": self._connected,
            "send_count": self._send_count,
            "error_count": self._error_count,
            "last_send_time": self._last_send_time,
        }

    def __del__(self) -> None:
        """析构函数."""
        self.close()

    def __enter__(self):
        """上下文管理器入口."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口."""
        self.close()


def parse_args() -> argparse.Namespace:
    """解析命令行参数.

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="UART 串口发送器"
    )
    parser.add_argument(
        "--port",
        type=str,
        default="/dev/ttyAMA0",
        help="串口设备路径 (默认: /dev/ttyAMA0)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="波特率 (默认: 115200)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行测试",
    )
    return parser.parse_args()


def test_uart(sender: UARTSender) -> None:
    """测试 UART 发送.

    Args:
        sender: UART 发送器实例
    """
    logger.info("=" * 50)
    logger.info("UART 发送测试")
    logger.info("=" * 50)

    # 测试角度序列
    test_angles = [
        np.array([0.0, 0.0, 0.0, 0.0, 0.0]),      # 完全张开
        np.array([20.0, 20.0, 20.0, 20.0, 20.0]),  # 开始弯曲
        np.array([45.0, 45.0, 45.0, 45.0, 45.0]),  # 中间位置
        np.array([70.0, 70.0, 70.0, 70.0, 70.0]),  # 接近握拳
        np.array([90.0, 90.0, 90.0, 90.0, 90.0]),  # 握拳
        np.array([0.0, 0.0, 0.0, 0.0, 0.0]),       # 张开
    ]

    for i, angles in enumerate(test_angles):
        logger.info(f"发送角度 {i + 1}: {angles}")
        success = sender.send_angles(angles)

        if success:
            logger.info("  发送成功")
        else:
            logger.error("  发送失败")

        time.sleep(0.5)

    # 打印统计信息
    stats = sender.stats
    logger.info("\n发送统计:")
    logger.info(f"  发送次数: {stats['send_count']}")
    logger.info(f"  错误次数: {stats['error_count']}")
    logger.info("=" * 50)


def main() -> None:
    """主函数."""
    args = parse_args()

    # 创建发送器
    sender = UARTSender(
        port=args.port,
        baudrate=args.baudrate,
    )

    if args.test:
        test_uart(sender)
    else:
        logger.info(f"UART 发送器已启动: {args.port} @ {args.baudrate}")
        logger.info("使用 --test 参数运行测试")

    sender.close()


if __name__ == "__main__":
    main()
