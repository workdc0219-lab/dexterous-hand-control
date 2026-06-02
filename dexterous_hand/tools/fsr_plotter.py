#!/usr/bin/env python3
"""
@file    fsr_plotter.py
@brief   FSR力值实时绘图工具
@details 使用matplotlib动态刷新，显示5个手指的力值曲线，从串口读取数据。

用法:
    python fsr_plotter.py --port COM3 --baud 115200
    python fsr_plotter.py --port /dev/ttyUSB0 --baud 115200
"""

import argparse
import logging
import re
import sys
import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
except ImportError:
    logger.error("matplotlib未安装，请运行: pip install matplotlib")
    sys.exit(1)

# 手指名称和颜色
FINGER_NAMES = ["拇指", "食指", "中指", "无名指", "小指"]
FINGER_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]
FINGER_EN = ["thumb", "index", "middle", "ring", "pinky"]

# 数据缓冲区大小
BUFFER_SIZE = 200


class SerialDataReader:
    """串口数据读取器。"""

    def __init__(self, port: str, baudrate: int = 115200) -> None:
        """
        初始化串口读取器。

        Args:
            port: 串口端口
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        self._serial = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 力值缓冲区: [thumb, index, middle, ring, pinky]
        self.force_buffers: List[Deque[float]] = [deque(maxlen=BUFFER_SIZE) for _ in range(5)]
        self.time_buffer: Deque[float] = deque(maxlen=BUFFER_SIZE)
        self._lock = threading.Lock()
        self._start_time = time.time()

    def start(self) -> bool:
        """
        启动串口读取。

        Returns:
            是否成功启动
        """
        try:
            import serial
        except ImportError:
            logger.error("pyserial未安装，请运行: pip install pyserial")
            return False

        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            logger.info("串口已连接: %s @ %d baud", self.port, self.baudrate)
        except Exception as e:
            logger.error("串口连接失败: %s", e)
            return False

        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """停止读取。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._serial:
            self._serial.close()
            self._serial = None

    def _read_loop(self) -> None:
        """读取循环。"""
        # 期望格式: "FSR:thumb:index:middle:ring:pinky" 或 "FSR,1.2,3.4,5.6,7.8,9.0"
        pattern_csv = re.compile(r"FSR[,:\s]+([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)")

        while self._running:
            try:
                if self._serial is None:
                    break
                line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                match = pattern_csv.match(line)
                if match:
                    forces = [float(match.group(i + 1)) for i in range(5)]
                    t = time.time() - self._start_time

                    with self._lock:
                        self.time_buffer.append(t)
                        for i in range(5):
                            self.force_buffers[i].append(forces[i])

            except Exception as e:
                if self._running:
                    logger.warning("读取异常: %s", e)
                time.sleep(0.01)

    def get_data(self) -> tuple:
        """
        获取当前数据。

        Returns:
            (times, forces) 其中forces是5个列表
        """
        with self._lock:
            times = list(self.time_buffer)
            forces = [list(buf) for buf in self.force_buffers]
        return times, forces


class SimulatedDataReader:
    """模拟数据读取器（用于测试）。"""

    def __init__(self) -> None:
        self.force_buffers: List[Deque[float]] = [deque(maxlen=BUFFER_SIZE) for _ in range(5)]
        self.time_buffer: Deque[float] = deque(maxlen=BUFFER_SIZE)
        self._start_time = time.time()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        """启动模拟。"""
        self._running = True
        self._thread = threading.Thread(target=self._simulate_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """停止模拟。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _simulate_loop(self) -> None:
        """模拟数据生成。"""
        import math
        while self._running:
            t = time.time() - self._start_time
            forces = [
                2.0 + 1.5 * math.sin(t * 1.0 + i * 0.5) + 0.3 * math.sin(t * 5.0)
                for i in range(5)
            ]
            self.time_buffer.append(t)
            for i in range(5):
                self.force_buffers[i].append(max(0, forces[i]))
            time.sleep(0.02)

    def get_data(self) -> tuple:
        """获取数据。"""
        times = list(self.time_buffer)
        forces = [list(buf) for buf in self.force_buffers]
        return times, forces


class FsrPlotter:
    """FSR力值实时绘图器。"""

    def __init__(self, data_reader) -> None:
        """
        初始化绘图器。

        Args:
            data_reader: 数据读取器（需要有get_data方法）
        """
        self.data_reader = data_reader
        self.fig, self.ax = plt.subplots(figsize=(12, 6))
        self.lines = []

        # 设置图表
        self.ax.set_xlabel("时间 (s)", fontsize=12)
        self.ax.set_ylabel("力值 (N)", fontsize=12)
        self.ax.set_title("FSR力值实时监控", fontsize=14, fontweight="bold")
        self.ax.set_ylim(0, 10)
        self.ax.grid(True, alpha=0.3)

        # 创建线条
        for i in range(5):
            line, = self.ax.plot([], [], color=FINGER_COLORS[i], linewidth=2, label=FINGER_NAMES[i])
            self.lines.append(line)

        self.ax.legend(loc="upper right", fontsize=10)

        # 力值文本显示
        self.force_texts = []
        for i in range(5):
            text = self.ax.text(
                0.02, 0.95 - i * 0.08, f"{FINGER_NAMES[i]}: 0.0 N",
                transform=self.ax.transAxes, fontsize=10,
                color=FINGER_COLORS[i], fontweight="bold"
            )
            self.force_texts.append(text)

    def update(self, frame: int) -> list:
        """
        更新动画帧。

        Args:
            frame: 帧号

        Returns:
            更新的线条列表
        """
        times, forces = self.data_reader.get_data()

        if not times:
            return self.lines

        for i in range(5):
            if forces[i]:
                self.lines[i].set_data(times[-BUFFER_SIZE:], forces[i][-BUFFER_SIZE:])
                self.force_texts[i].set_text(f"{FINGER_NAMES[i]}: {forces[i][-1]:.2f} N")

        # 自动调整X轴范围
        if len(times) > 1:
            x_min = max(0, times[-1] - 10)  # 显示最近10秒
            x_max = times[-1]
            self.ax.set_xlim(x_min, x_max)

        return self.lines

    def run(self) -> None:
        """运行实时绘图。"""
        ani = animation.FuncAnimation(
            self.fig, self.update, interval=50, blit=False, cache_frame_data=False
        )
        plt.tight_layout()
        plt.show()


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="FSR力值实时绘图工具")
    parser.add_argument("--port", type=str, default=None, help="串口端口 (如 COM3 或 /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=115200, help="波特率 (默认: 115200)")
    parser.add_argument("--sim", action="store_true", help="使用模拟数据（用于测试）")
    args = parser.parse_args()

    # 选择数据源
    if args.sim:
        logger.info("使用模拟数据模式")
        reader = SimulatedDataReader()
    elif args.port:
        reader = SerialDataReader(args.port, args.baud)
    else:
        logger.error("请指定 --port 或 --sim")
        sys.exit(1)

    if not reader.start():
        sys.exit(1)

    try:
        plotter = FsrPlotter(reader)
        plotter.run()
    finally:
        reader.stop()
        logger.info("程序已退出")


if __name__ == "__main__":
    main()
