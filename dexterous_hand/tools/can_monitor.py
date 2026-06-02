#!/usr/bin/env python3
"""
@file    can_monitor.py
@brief   CAN总线监控工具
@details 使用python-can库监听所有CAN帧，解析CMD和DATA，彩色输出，支持保存到CSV。

用法:
    python can_monitor.py --interface pcan --channel PCAN_USBBUS1
    python can_monitor.py --interface socketcan --channel can0
    python can_monitor.py --interface pcan --channel PCAN_USBBUS1 --save output.csv
"""

import argparse
import csv
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, TextIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ──────────────── CAN协议常量（与can_protocol_defs.h对齐）────────────────

# ID编码位域
CAN_ID_PRIORITY_POS = 9
CAN_ID_DST_POS = 4
CAN_ID_SRC_POS = 0
CAN_ID_PRIORITY_MASK = 0x03 << CAN_ID_PRIORITY_POS
CAN_ID_DST_MASK = 0x1F << CAN_ID_DST_POS
CAN_ID_SRC_MASK = 0x0F << CAN_ID_SRC_POS

# 节点ID
NODE_ID_MASTER = 0x00
NODE_ID_THUMB = 0x01
NODE_ID_INDEX = 0x02
NODE_ID_MIDDLE = 0x03
NODE_ID_RING = 0x04
NODE_ID_PINKY = 0x05
NODE_ID_BROADCAST = 0x1F

# 命令定义
CMD_SET_ANGLE = 0x01
CMD_QUERY_FORCE = 0x02
CMD_SET_PID = 0x03
CMD_SET_MODE = 0x10
CMD_SET_TARGET_FORCE = 0x11
CMD_HEARTBEAT = 0xFE
CMD_EMERGENCY_STOP = 0xFF
CMD_ANGLE_REPORT = 0x81
CMD_FORCE_REPORT = 0x82
CMD_PID_REPORT = 0x83
CMD_ESTOP_ACK = 0x84
CMD_ERROR_REPORT = 0x85

CMD_NAMES: Dict[int, str] = {
    CMD_SET_ANGLE: "SET_ANGLE",
    CMD_QUERY_FORCE: "QUERY_FORCE",
    CMD_SET_PID: "SET_PID",
    CMD_SET_MODE: "SET_MODE",
    CMD_SET_TARGET_FORCE: "SET_TARGET_FORCE",
    CMD_HEARTBEAT: "HEARTBEAT",
    CMD_EMERGENCY_STOP: "EMERGENCY_STOP",
    CMD_ANGLE_REPORT: "ANGLE_REPORT",
    CMD_FORCE_REPORT: "FORCE_REPORT",
    CMD_PID_REPORT: "PID_REPORT",
    CMD_ESTOP_ACK: "ESTOP_ACK",
    CMD_ERROR_REPORT: "ERROR_REPORT",
}

NODE_NAMES: Dict[int, str] = {
    NODE_ID_MASTER: "MASTER",
    NODE_ID_THUMB: "THUMB",
    NODE_ID_INDEX: "INDEX",
    NODE_ID_MIDDLE: "MIDDLE",
    NODE_ID_RING: "RING",
    NODE_ID_PINKY: "PINKY",
    NODE_ID_BROADCAST: "BROADCAST",
}

# 错误码
ERROR_NAMES: Dict[int, str] = {
    0x00: "NONE",
    0x01: "OVERCURRENT",
    0x02: "STALL",
    0x03: "COMM_TIMEOUT",
    0x04: "FSR_OVERLOAD",
    0x05: "ANGLE_LIMIT",
}

# ──────────────── ANSI颜色 ────────────────

class Colors:
    """ANSI终端颜色。"""
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BOLD = "\033[1m"


# ──────────────── CAN帧解析 ────────────────

def parse_can_id(can_id: int) -> tuple:
    """
    解析CAN ID。

    Args:
        can_id: 11位CAN ID

    Returns:
        (priority, dst, src)
    """
    priority = (can_id >> CAN_ID_PRIORITY_POS) & 0x03
    dst = (can_id >> CAN_ID_DST_POS) & 0x1F
    src = (can_id >> CAN_ID_SRC_POS) & 0x0F
    return priority, dst, src


def parse_can_data(data: bytes) -> tuple:
    """
    解析CAN数据字段。

    Args:
        data: 8字节数据

    Returns:
        (cmd, seq, payload)
    """
    if len(data) < 2:
        return 0, 0, b""
    cmd = data[0]
    seq = data[1]
    payload = data[2:]
    return cmd, seq, payload


def format_can_frame(can_id: int, data: bytes, timestamp: float) -> str:
    """
    格式化CAN帧为彩色字符串。

    Args:
        can_id: CAN ID
        data: 数据
        timestamp: 时间戳

    Returns:
        格式化的字符串
    """
    priority, dst, src = parse_can_id(can_id)
    cmd, seq, payload = parse_can_data(data)

    # 节点名称
    dst_name = NODE_NAMES.get(dst, f"UNK({dst:#04x})")
    src_name = NODE_NAMES.get(src, f"UNK({src:#04x})")
    cmd_name = CMD_NAMES.get(cmd, f"UNK({cmd:#04x})")

    # 颜色选择
    if cmd in (CMD_EMERGENCY_STOP, CMD_ERROR_REPORT):
        color = Colors.RED
    elif cmd in (CMD_HEARTBEAT,):
        color = Colors.GREEN
    elif cmd & 0x80:  # 从→主
        color = Colors.CYAN
    else:  # 主→从
        color = Colors.YELLOW

    # 时间戳
    time_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]

    # 数据字段
    data_hex = " ".join(f"{b:02X}" for b in data)

    # 解析特定命令数据
    detail = ""
    if cmd == CMD_SET_ANGLE and len(payload) >= 4:
        angle = int.from_bytes(payload[0:2], "little") / 10.0
        speed = int.from_bytes(payload[2:4], "little") / 10.0
        detail = f" angle={angle:.1f}° speed={speed:.1f}°/s"
    elif cmd == CMD_ANGLE_REPORT and len(payload) >= 5:
        angle = int.from_bytes(payload[0:2], "little") / 10.0
        encoder = int.from_bytes(payload[2:4], "little")
        status = payload[4]
        detail = f" angle={angle:.1f}° enc={encoder} status={status:#04x}"
    elif cmd == CMD_FORCE_REPORT and len(payload) >= 5:
        force = int.from_bytes(payload[0:2], "little") / 100.0
        adc = int.from_bytes(payload[2:4], "little")
        status = payload[4]
        detail = f" force={force:.2f}N adc={adc} contact={'Y' if status & 0x01 else 'N'}"
    elif cmd == CMD_ERROR_REPORT and len(payload) >= 1:
        err_code = payload[0]
        err_name = ERROR_NAMES.get(err_code, f"UNK({err_code:#04x})")
        detail = f" error={err_name}"
    elif cmd == CMD_HEARTBEAT and len(payload) >= 1:
        status = payload[0]
        flags = []
        if status & 0x01:
            flags.append("RUN")
        if status & 0x02:
            flags.append("ESTOP")
        if status & 0x04:
            flags.append("COMM_ERR")
        detail = f" status=[{'|'.join(flags)}]"

    # 组装输出
    line = (
        f"{Colors.WHITE}{time_str}{Colors.RESET} "
        f"{color}{Colors.BOLD}{cmd_name:<16}{Colors.RESET} "
        f"P={priority} {src_name:>8} -> {dst_name:<8} "
        f"SEQ={seq:03d} [{data_hex}]"
        f"{color}{detail}{Colors.RESET}"
    )

    return line


# ──────────────── CSV记录 ────────────────

class CsvLogger:
    """CSV记录器。"""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._file: Optional[TextIO] = None
        self._writer: Optional[csv.writer] = None

    def open(self) -> None:
        """打开CSV文件。"""
        self._file = open(self.filepath, "w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow([
            "timestamp", "can_id", "priority", "src", "dst",
            "cmd", "cmd_name", "seq", "data_hex", "detail"
        ])

    def log(self, can_id: int, data: bytes, timestamp: float) -> None:
        """记录一帧。"""
        if self._writer is None:
            return

        priority, dst, src = parse_can_id(can_id)
        cmd, seq, payload = parse_can_data(data)
        cmd_name = CMD_NAMES.get(cmd, f"UNK({cmd:#04x})")
        data_hex = " ".join(f"{b:02X}" for b in data)

        self._writer.writerow([
            f"{timestamp:.6f}", f"{can_id:#06x}", priority,
            f"{src:#04x}", f"{dst:#04x}", f"{cmd:#04x}",
            cmd_name, seq, data_hex, ""
        ])
        if self._file:
            self._file.flush()

    def close(self) -> None:
        """关闭CSV文件。"""
        if self._file:
            self._file.close()
            self._file = None


# ──────────────── 主监控逻辑 ────────────────

class CanMonitor:
    """CAN总线监控器。"""

    def __init__(self, interface: str, channel: str, bitrate: int = 1000000) -> None:
        """
        初始化监控器。

        Args:
            interface: CAN接口类型 (pcan, socketcan, virtual等)
            channel: 通道名称
            bitrate: 波特率
        """
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self._running = False
        self._bus = None
        self._csv_logger: Optional[CsvLogger] = None
        self._frame_count = 0

    def start(self, csv_path: Optional[str] = None) -> None:
        """
        启动监控。

        Args:
            csv_path: 可选的CSV保存路径
        """
        try:
            import can
        except ImportError:
            logger.error("python-can未安装，请运行: pip install python-can")
            sys.exit(1)

        # 创建CAN总线
        try:
            self._bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
            logger.info("CAN总线已连接: %s %s @ %d bps", self.interface, self.channel, self.bitrate)
        except Exception as e:
            logger.error("CAN总线连接失败: %s", e)
            sys.exit(1)

        # CSV记录
        if csv_path:
            self._csv_logger = CsvLogger(csv_path)
            self._csv_logger.open()
            logger.info("CSV记录已启用: %s", csv_path)

        # 信号处理
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)

        print(f"\n{Colors.BOLD}CAN总线监控中... (Ctrl+C 退出){Colors.RESET}\n")
        print(f"{'时间':<14} {'命令':<18} {'路径':<20} {'SEQ':<6} {'数据':<26} {'详情'}")
        print("-" * 100)

        # 主循环
        try:
            while self._running:
                msg = self._bus.recv(timeout=1.0)
                if msg is None:
                    continue

                self._frame_count += 1

                # 打印
                line = format_can_frame(msg.arbitration_id, msg.data, msg.timestamp)
                print(line)

                # CSV记录
                if self._csv_logger:
                    self._csv_logger.log(msg.arbitration_id, msg.data, msg.timestamp)

        except Exception as e:
            logger.error("监控异常: %s", e)
        finally:
            self.stop()

    def stop(self) -> None:
        """停止监控。"""
        self._running = False
        if self._bus:
            self._bus.shutdown()
            self._bus = None
        if self._csv_logger:
            self._csv_logger.close()
            self._csv_logger = None
        logger.info("监控已停止，共接收 %d 帧", self._frame_count)

    def _signal_handler(self, signum, frame) -> None:
        """信号处理。"""
        self._running = False


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="CAN总线监控工具")
    parser.add_argument("--interface", type=str, default="pcan", help="CAN接口类型 (默认: pcan)")
    parser.add_argument("--channel", type=str, default="PCAN_USBBUS1", help="通道名称 (默认: PCAN_USBBUS1)")
    parser.add_argument("--bitrate", type=int, default=1000000, help="波特率 (默认: 1000000)")
    parser.add_argument("--save", type=str, default=None, help="保存到CSV文件")
    args = parser.parse_args()

    monitor = CanMonitor(args.interface, args.channel, args.bitrate)
    monitor.start(csv_path=args.save)


if __name__ == "__main__":
    main()
