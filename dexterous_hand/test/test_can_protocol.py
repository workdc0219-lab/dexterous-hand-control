#!/usr/bin/env python3
"""
@file    test_can_protocol.py
@brief   CAN协议单元测试
@details 测试帧构建和解析、ID编码/解码、CMD序列化/反序列化

用法:
    pytest test_can_protocol.py -v
"""

import struct
import sys
from pathlib import Path

import pytest

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ──────────────── CAN协议Python实现（与can_protocol_defs.h对齐）────────────────

# ID编码位域
CAN_ID_PRIORITY_POS = 9
CAN_ID_DST_POS = 4
CAN_ID_SRC_POS = 0

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

# 控制模式
CTRL_MODE_POSITION = 0x00
CTRL_MODE_FORCE = 0x01
CTRL_MODE_AUTO = 0x02

# 错误码
ERR_NONE = 0x00
ERR_OVERCURRENT = 0x01
ERR_STALL = 0x02
ERR_COMM_TIMEOUT = 0x03
ERR_FSR_OVERLOAD = 0x04
ERR_ANGLE_LIMIT = 0x05


def can_make_id(priority: int, dst: int, src: int) -> int:
    """构建CAN ID。"""
    return (priority << CAN_ID_PRIORITY_POS) | (dst << CAN_ID_DST_POS) | (src << CAN_ID_SRC_POS)


def can_get_priority(can_id: int) -> int:
    """从CAN ID提取优先级。"""
    return (can_id >> CAN_ID_PRIORITY_POS) & 0x03


def can_get_dst(can_id: int) -> int:
    """从CAN ID提取目标节点。"""
    return (can_id >> CAN_ID_DST_POS) & 0x1F


def can_get_src(can_id: int) -> int:
    """从CAN ID提取源节点。"""
    return (can_id >> CAN_ID_SRC_POS) & 0x0F


def can_frame_build(priority: int, dst: int, src: int, cmd: int, seq: int, data: bytes) -> tuple:
    """
    构建CAN帧。

    Returns:
        (can_id, frame_data) 其中frame_data为8字节
    """
    can_id = can_make_id(priority, dst, src)
    # 补齐到6字节
    payload = data[:6].ljust(6, b'\x00')
    frame_data = bytes([cmd, seq]) + payload
    return can_id, frame_data


def can_frame_parse(can_id: int, frame_data: bytes) -> dict:
    """
    解析CAN帧。

    Returns:
        帧信息字典
    """
    return {
        "id": can_id,
        "priority": can_get_priority(can_id),
        "dst": can_get_dst(can_id),
        "src": can_get_src(can_id),
        "cmd": frame_data[0],
        "seq": frame_data[1],
        "data": frame_data[2:8],
    }


def serialize_set_angle(angle_deg: float, speed_dps: float) -> bytes:
    """序列化SET_ANGLE命令数据。"""
    angle_x10 = int(angle_deg * 10) & 0xFFFF
    speed_x10 = int(speed_dps * 10) & 0xFFFF
    return struct.pack("<HH", angle_x10, speed_x10) + b'\x00\x00'


def deserialize_set_angle(data: bytes) -> tuple:
    """反序列化SET_ANGLE命令数据。"""
    angle_x10, speed_x10 = struct.unpack("<HH", data[:4])
    return angle_x10 / 10.0, speed_x10 / 10.0


def serialize_set_pid(kp: float, ki: float, kd: float) -> bytes:
    """序列化SET_PID命令数据。"""
    kp_x100 = int(kp * 100) & 0xFFFF
    ki_x100 = int(ki * 100) & 0xFFFF
    kd_x100 = int(kd * 100) & 0xFFFF
    return struct.pack("<HHH", kp_x100, ki_x100, kd_x100)


def deserialize_set_pid(data: bytes) -> tuple:
    """反序列化SET_PID命令数据。"""
    kp_x100, ki_x100, kd_x100 = struct.unpack("<HHH", data[:6])
    return kp_x100 / 100.0, ki_x100 / 100.0, kd_x100 / 100.0


def serialize_angle_report(angle_deg: float, encoder_raw: int, status: int) -> bytes:
    """序列化ANGLE_REPORT数据。"""
    angle_x10 = int(angle_deg * 10) & 0xFFFF
    encoder = encoder_raw & 0xFFFF
    return struct.pack("<HHB", angle_x10, encoder, status) + b'\x00'


def deserialize_angle_report(data: bytes) -> dict:
    """反序列化ANGLE_REPORT数据。"""
    angle_x10, encoder, status = struct.unpack("<HHB", data[:5])
    return {
        "angle": angle_x10 / 10.0,
        "encoder": encoder,
        "status": status,
    }


def serialize_force_report(force_n: float, adc_raw: int, contact: bool) -> bytes:
    """序列化FORCE_REPORT数据。"""
    force_x100 = int(force_n * 100) & 0xFFFF
    adc = adc_raw & 0xFFFF
    status = 0x01 if contact else 0x00
    return struct.pack("<HHB", force_x100, adc, status) + b'\x00'


def deserialize_force_report(data: bytes) -> dict:
    """反序列化FORCE_REPORT数据。"""
    force_x100, adc, status = struct.unpack("<HHB", data[:5])
    return {
        "force": force_x100 / 100.0,
        "adc_raw": adc,
        "contact": bool(status & 0x01),
    }


# ──────────────── 测试用例 ────────────────

class TestCanIdEncoding:
    """CAN ID编码/解码测试。"""

    def test_make_id_basic(self):
        """测试基本ID构建。"""
        can_id = can_make_id(1, NODE_ID_THUMB, NODE_ID_MASTER)
        assert can_id == 0b01_00001_0000  # priority=1, dst=1, src=0

    def test_make_id_all_fingers(self):
        """测试所有手指节点ID。"""
        for node_id in [NODE_ID_THUMB, NODE_ID_INDEX, NODE_ID_MIDDLE, NODE_ID_RING, NODE_ID_PINKY]:
            can_id = can_make_id(1, node_id, NODE_ID_MASTER)
            assert can_get_dst(can_id) == node_id
            assert can_get_src(can_id) == NODE_ID_MASTER
            assert can_get_priority(can_id) == 1

    def test_make_id_broadcast(self):
        """测试广播ID。"""
        can_id = can_make_id(0, NODE_ID_BROADCAST, NODE_ID_MASTER)
        assert can_get_dst(can_id) == NODE_ID_BROADCAST

    def test_priority_encoding(self):
        """测试优先级编码。"""
        for priority in range(4):
            can_id = can_make_id(priority, NODE_ID_THUMB, NODE_ID_MASTER)
            assert can_get_priority(can_id) == priority

    def test_id_roundtrip(self):
        """测试ID编码解码往返。"""
        test_cases = [
            (0, 0, 0),
            (1, 1, 0),
            (3, 31, 15),
            (2, 5, 3),
        ]
        for priority, dst, src in test_cases:
            can_id = can_make_id(priority, dst, src)
            assert can_get_priority(can_id) == priority
            assert can_get_dst(can_id) == dst
            assert can_get_src(can_id) == src

    def test_master_to_finger_id(self):
        """测试主控到手指的ID构建。"""
        # 主控发送到拇指，优先级1
        can_id = (1 << CAN_ID_PRIORITY_POS) | (NODE_ID_THUMB << CAN_ID_DST_POS) | (NODE_ID_MASTER << CAN_ID_SRC_POS)
        assert can_get_dst(can_id) == NODE_ID_THUMB
        assert can_get_src(can_id) == NODE_ID_MASTER

    def test_finger_to_master_id(self):
        """测试手指到主控的ID构建。"""
        can_id = (2 << CAN_ID_PRIORITY_POS) | (NODE_ID_MASTER << CAN_ID_DST_POS) | (NODE_ID_INDEX << CAN_ID_SRC_POS)
        assert can_get_dst(can_id) == NODE_ID_MASTER
        assert can_get_src(can_id) == NODE_ID_INDEX


class TestFrameBuilding:
    """CAN帧构建测试。"""

    def test_build_basic_frame(self):
        """测试基本帧构建。"""
        can_id, frame_data = can_frame_build(1, NODE_ID_THUMB, NODE_ID_MASTER, CMD_SET_ANGLE, 0, b'\x00')
        assert len(frame_data) == 8
        assert frame_data[0] == CMD_SET_ANGLE
        assert frame_data[1] == 0

    def test_build_frame_with_data(self):
        """测试带数据的帧构建。"""
        data = b'\x01\x02\x03\x04\x05\x06'
        can_id, frame_data = can_frame_build(1, NODE_ID_THUMB, NODE_ID_MASTER, CMD_SET_ANGLE, 1, data)
        assert frame_data[2:8] == data

    def test_build_frame_data_padding(self):
        """测试数据填充。"""
        data = b'\x01\x02'
        can_id, frame_data = can_frame_build(1, NODE_ID_THUMB, NODE_ID_MASTER, CMD_QUERY_FORCE, 0, data)
        assert frame_data[2:4] == data
        assert frame_data[4:8] == b'\x00\x00\x00\x00'

    def test_build_frame_data_truncation(self):
        """测试数据截断。"""
        data = b'\x01\x02\x03\x04\x05\x06\x07\x08'  # 8字节，应截断到6
        can_id, frame_data = can_frame_build(1, NODE_ID_THUMB, NODE_ID_MASTER, CMD_SET_ANGLE, 0, data)
        assert frame_data[2:8] == data[:6]


class TestFrameParsing:
    """CAN帧解析测试。"""

    def test_parse_basic_frame(self):
        """测试基本帧解析。"""
        can_id = can_make_id(1, NODE_ID_THUMB, NODE_ID_MASTER)
        frame_data = bytes([CMD_SET_ANGLE, 0, 0x10, 0x27, 0x64, 0x00, 0x00, 0x00])
        result = can_frame_parse(can_id, frame_data)
        assert result["priority"] == 1
        assert result["dst"] == NODE_ID_THUMB
        assert result["src"] == NODE_ID_MASTER
        assert result["cmd"] == CMD_SET_ANGLE
        assert result["seq"] == 0

    def test_parse_heartbeat_frame(self):
        """测试心跳帧解析。"""
        can_id = can_make_id(2, NODE_ID_MASTER, NODE_ID_THUMB)
        frame_data = bytes([CMD_HEARTBEAT, 5, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
        result = can_frame_parse(can_id, frame_data)
        assert result["cmd"] == CMD_HEARTBEAT
        assert result["seq"] == 5
        assert result["data"][0] == 0x01  # 系统状态

    def test_parse_error_frame(self):
        """测试错误帧解析。"""
        can_id = can_make_id(0, NODE_ID_MASTER, NODE_ID_INDEX)
        frame_data = bytes([CMD_ERROR_REPORT, 0, ERR_OVERCURRENT, 0x00, 0x00, 0x00, 0x00, 0x00])
        result = can_frame_parse(can_id, frame_data)
        assert result["cmd"] == CMD_ERROR_REPORT
        assert result["data"][0] == ERR_OVERCURRENT


class TestCmdSerialization:
    """CMD序列化/反序列化测试。"""

    def test_set_angle_serialization(self):
        """测试SET_ANGLE序列化。"""
        data = serialize_set_angle(90.0, 100.0)
        assert len(data) == 6
        angle, speed = deserialize_set_angle(data)
        assert abs(angle - 90.0) < 0.2  # 精度0.1度
        assert abs(speed - 100.0) < 0.2

    def test_set_angle_boundary(self):
        """测试SET_ANGLE边界值。"""
        # 最小角度
        data = serialize_set_angle(0.0, 0.0)
        angle, speed = deserialize_set_angle(data)
        assert abs(angle) < 0.2
        assert abs(speed) < 0.2

        # 最大角度
        data = serialize_set_angle(180.0, 500.0)
        angle, speed = deserialize_set_angle(data)
        assert abs(angle - 180.0) < 0.2
        assert abs(speed - 500.0) < 0.2

    def test_set_pid_serialization(self):
        """测试SET_PID序列化。"""
        data = serialize_set_pid(1.5, 0.1, 0.05)
        assert len(data) == 6
        kp, ki, kd = deserialize_set_pid(data)
        assert abs(kp - 1.5) < 0.02
        assert abs(ki - 0.1) < 0.02
        assert abs(kd - 0.05) < 0.02

    def test_angle_report_serialization(self):
        """测试ANGLE_REPORT序列化。"""
        data = serialize_angle_report(45.5, 1024, 0x01)
        assert len(data) == 6
        result = deserialize_angle_report(data)
        assert abs(result["angle"] - 45.5) < 0.2
        assert result["encoder"] == 1024
        assert result["status"] == 0x01

    def test_force_report_serialization(self):
        """测试FORCE_REPORT序列化。"""
        data = serialize_force_report(5.25, 2048, True)
        assert len(data) == 6
        result = deserialize_force_report(data)
        assert abs(result["force"] - 5.25) < 0.02
        assert result["adc_raw"] == 2048
        assert result["contact"] is True

    def test_force_report_no_contact(self):
        """测试无接触状态。"""
        data = serialize_force_report(0.0, 0, False)
        result = deserialize_force_report(data)
        assert result["contact"] is False
        assert abs(result["force"]) < 0.02

    def test_angle_roundtrip(self):
        """测试角度序列化往返。"""
        test_angles = [0.0, 45.0, 90.0, 135.5, 180.0]
        for angle in test_angles:
            data = serialize_set_angle(angle, 100.0)
            decoded_angle, _ = deserialize_set_angle(data)
            assert abs(decoded_angle - angle) < 0.2, f"角度 {angle} 往返失败: {decoded_angle}"

    def test_pid_roundtrip(self):
        """测试PID序列化往返。"""
        test_cases = [(1.0, 0.1, 0.01), (2.5, 0.5, 0.1), (0.0, 0.0, 0.0)]
        for kp, ki, kd in test_cases:
            data = serialize_set_pid(kp, ki, kd)
            dkp, dki, dkd = deserialize_set_pid(data)
            assert abs(dkp - kp) < 0.02
            assert abs(dki - ki) < 0.02
            assert abs(dkd - kd) < 0.02


class TestFrameRoundTrip:
    """帧构建解析往返测试。"""

    def test_set_angle_roundtrip(self):
        """测试SET_ANGLE帧往返。"""
        angle_data = serialize_set_angle(60.0, 200.0)
        can_id, frame_data = can_frame_build(1, NODE_ID_THUMB, NODE_ID_MASTER, CMD_SET_ANGLE, 3, angle_data)
        result = can_frame_parse(can_id, frame_data)
        assert result["cmd"] == CMD_SET_ANGLE
        assert result["seq"] == 3
        angle, speed = deserialize_set_angle(result["data"])
        assert abs(angle - 60.0) < 0.2
        assert abs(speed - 200.0) < 0.2

    def test_force_report_roundtrip(self):
        """测试FORCE_REPORT帧往返。"""
        force_data = serialize_force_report(3.75, 1500, True)
        can_id, frame_data = can_frame_build(2, NODE_ID_MASTER, NODE_ID_INDEX, CMD_FORCE_REPORT, 10, force_data)
        result = can_frame_parse(can_id, frame_data)
        assert result["cmd"] == CMD_FORCE_REPORT
        assert result["src"] == NODE_ID_INDEX
        force_result = deserialize_force_report(result["data"])
        assert abs(force_result["force"] - 3.75) < 0.02
        assert force_result["contact"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
