#!/usr/bin/env python3
"""
@file    latency_test.py
@brief   端到端延迟测试工具
@details 发送指令并测量响应时间，统计平均/最大/最小延迟，输出报告。

用法:
    python latency_test.py --interface pcan --channel PCAN_USBBUS1 --count 100
    python latency_test.py --interface socketcan --channel can0 --count 50
"""

import argparse
import logging
import signal
import statistics
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# CAN协议常量
CAN_ID_PRIORITY_POS = 9
CAN_ID_DST_POS = 4
CAN_ID_SRC_POS = 0
NODE_ID_MASTER = 0x00
NODE_ID_THUMB = 0x01
NODE_ID_INDEX = 0x02
NODE_ID_MIDDLE = 0x03
NODE_ID_RING = 0x04
NODE_ID_PINKY = 0x05

CMD_QUERY_FORCE = 0x02
CMD_FORCE_REPORT = 0x82
CMD_ANGLE_REPORT = 0x81

NODE_IDS = [NODE_ID_THUMB, NODE_ID_INDEX, NODE_ID_MIDDLE, NODE_ID_RING, NODE_ID_PINKY]
NODE_NAMES = {1: "拇指", 2: "食指", 3: "中指", 4: "无名指", 5: "小指"}


@dataclass
class LatencyResult:
    """延迟测试结果。"""
    node_id: int
    node_name: str
    latencies: List[float] = field(default_factory=list)  # 毫秒

    @property
    def count(self) -> int:
        return len(self.latencies)

    @property
    def mean(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0

    @property
    def median(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0

    @property
    def min_latency(self) -> float:
        return min(self.latencies) if self.latencies else 0

    @property
    def max_latency(self) -> float:
        return max(self.latencies) if self.latencies else 0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.latencies) if len(self.latencies) > 1 else 0

    @property
    def p95(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def p99(self) -> float:
        if not self.latencies:
            return 0
        sorted_lat = sorted(self.latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]


class LatencyTester:
    """延迟测试器。"""

    def __init__(self, interface: str, channel: str, bitrate: int = 1000000) -> None:
        """
        初始化测试器。

        Args:
            interface: CAN接口类型
            channel: 通道名称
            bitrate: 波特率
        """
        self.interface = interface
        self.channel = channel
        self.bitrate = bitrate
        self._bus = None
        self._running = False

    def _make_query_frame(self, target_node: int) -> tuple:
        """
        构建查询帧。

        Args:
            target_node: 目标节点ID

        Returns:
            (can_id, data)
        """
        can_id = (1 << CAN_ID_PRIORITY_POS) | (target_node << CAN_ID_DST_POS) | (NODE_ID_MASTER << CAN_ID_SRC_POS)
        data = bytes([CMD_QUERY_FORCE, 0x00, target_node, 0x00, 0x00, 0x00, 0x00, 0x00])
        return can_id, data

    def _parse_response(self, msg) -> Optional[int]:
        """
        解析响应帧，返回源节点ID。

        Args:
            msg: CAN消息

        Returns:
            源节点ID，如果不是期望的响应则返回None
        """
        cmd = msg.data[0] if len(msg.data) > 0 else 0
        if cmd != CMD_FORCE_REPORT:
            return None

        src = (msg.arbitration_id >> CAN_ID_SRC_POS) & 0x0F
        return src

    def test_node(self, node_id: int, count: int, timeout: float = 0.5) -> LatencyResult:
        """
        测试单个节点的延迟。

        Args:
            node_id: 节点ID
            count: 测试次数
            timeout: 超时时间(秒)

        Returns:
            延迟结果
        """
        result = LatencyResult(
            node_id=node_id,
            node_name=NODE_NAMES.get(node_id, f"Node({node_id})")
        )

        for i in range(count):
            if not self._running:
                break

            # 发送查询
            can_id, data = self._make_query_frame(node_id)
            send_time = time.perf_counter()

            try:
                import can
                msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=False)
                self._bus.send(msg)
            except Exception as e:
                logger.warning("发送失败: %s", e)
                continue

            # 等待响应
            recv_time = None
            while time.perf_counter() - send_time < timeout:
                recv_msg = self._bus.recv(timeout=0.01)
                if recv_msg is None:
                    continue

                src = self._parse_response(recv_msg)
                if src == node_id:
                    recv_time = time.perf_counter()
                    break

            if recv_time is not None:
                latency_ms = (recv_time - send_time) * 1000
                result.latencies.append(latency_ms)
            else:
                logger.debug("节点 %s 第 %d 次超时", result.node_name, i + 1)

            time.sleep(0.01)  # 间隔10ms

        return result

    def run(self, nodes: List[int], count: int) -> Dict[int, LatencyResult]:
        """
        运行延迟测试。

        Args:
            nodes: 要测试的节点列表
            count: 每个节点的测试次数

        Returns:
            各节点的延迟结果
        """
        try:
            import can
        except ImportError:
            logger.error("python-can未安装")
            sys.exit(1)

        try:
            self._bus = can.Bus(interface=self.interface, channel=self.channel, bitrate=self.bitrate)
            logger.info("CAN总线已连接: %s %s", self.interface, self.channel)
        except Exception as e:
            logger.error("CAN总线连接失败: %s", e)
            sys.exit(1)

        self._running = True
        signal.signal(signal.SIGINT, lambda s, f: setattr(self, '_running', False))

        results: Dict[int, LatencyResult] = {}
        for node_id in nodes:
            node_name = NODE_NAMES.get(node_id, f"Node({node_id})")
            logger.info("测试节点: %s (ID=%d), %d次...", node_name, node_id, count)
            result = self.test_node(node_id, count)
            results[node_id] = result
            logger.info(
                "  完成: %d/%d 次成功, 平均 %.2f ms",
                result.count, count, result.mean
            )

        if self._bus:
            self._bus.shutdown()

        return results

    def stop(self) -> None:
        """停止测试。"""
        self._running = False


def print_report(results: Dict[int, LatencyResult]) -> None:
    """打印延迟测试报告。"""
    print("\n" + "=" * 80)
    print("端到端延迟测试报告")
    print("=" * 80)
    print(f"{'节点':<8} {'成功/总数':<12} {'平均(ms)':<10} {'中位(ms)':<10} "
          f"{'最小(ms)':<10} {'最大(ms)':<10} {'P95(ms)':<10} {'P99(ms)':<10} {'标准差':<10}")
    print("-" * 80)

    all_latencies = []
    for node_id in sorted(results.keys()):
        r = results[node_id]
        all_latencies.extend(r.latencies)
        print(
            f"{r.node_name:<8} {r.count:<12} {r.mean:<10.2f} {r.median:<10.2f} "
            f"{r.min_latency:<10.2f} {r.max_latency:<10.2f} {r.p95:<10.2f} {r.p99:<10.2f} {r.stdev:<10.2f}"
        )

    # 总体统计
    if all_latencies:
        print("-" * 80)
        total_mean = statistics.mean(all_latencies)
        total_median = statistics.median(all_latencies)
        total_min = min(all_latencies)
        total_max = max(all_latencies)
        total_p95 = sorted(all_latencies)[int(len(all_latencies) * 0.95)]
        total_p99 = sorted(all_latencies)[int(len(all_latencies) * 0.99)]
        total_stdev = statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0
        print(
            f"{'总体':<8} {len(all_latencies):<12} {total_mean:<10.2f} {total_median:<10.2f} "
            f"{total_min:<10.2f} {total_max:<10.2f} {total_p95:<10.2f} {total_p99:<10.2f} {total_stdev:<10.2f}"
        )

    print("=" * 80)


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="端到端延迟测试工具")
    parser.add_argument("--interface", type=str, default="pcan", help="CAN接口类型")
    parser.add_argument("--channel", type=str, default="PCAN_USBBUS1", help="通道名称")
    parser.add_argument("--bitrate", type=int, default=1000000, help="波特率")
    parser.add_argument("--count", type=int, default=100, help="每个节点测试次数 (默认: 100)")
    parser.add_argument("--nodes", type=str, default="1,2,3,4,5", help="要测试的节点ID，逗号分隔 (默认: 1,2,3,4,5)")
    args = parser.parse_args()

    # 解析节点列表
    node_ids = [int(s.strip()) for s in args.nodes.split(",")]

    logger.info("延迟测试: 节点=%s, 每节点 %d 次", node_ids, args.count)

    tester = LatencyTester(args.interface, args.channel, args.bitrate)
    results = tester.run(node_ids, args.count)

    print_report(results)


if __name__ == "__main__":
    main()
