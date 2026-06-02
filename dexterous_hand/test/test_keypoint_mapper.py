#!/usr/bin/env python3
"""
@file    test_keypoint_mapper.py
@brief   关键点映射单元测试
@details 测试已知关键点到角度映射、边界条件

用法:
    pytest test_keypoint_mapper.py -v
"""

import math
import sys
from pathlib import Path

import numpy as np
import pytest

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ──────────────── 关键点映射实现 ────────────────

# MediaPipe手部关键点索引
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# 手指关键点链
FINGER_CHAINS = {
    "thumb": [THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP],
    "index": [INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP],
    "middle": [MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP],
    "ring": [RING_MCP, RING_PIP, RING_DIP, RING_TIP],
    "pinky": [PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP],
}


def compute_angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    """计算两个向量之间的夹角（弧度）。"""
    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-8 or norm2 < 1e-8:
        return 0.0
    cos_angle = np.dot(v1, v2) / (norm1 * norm2)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return math.acos(cos_angle)


def compute_bend_angle(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
    """
    计算三个点构成的弯曲角度。

    Args:
        p0: 起始点
        p1: 中间点
        p2: 终止点

    Returns:
        弯曲角度（弧度），0表示完全伸直，pi表示完全弯曲
    """
    v1 = p1 - p0
    v2 = p2 - p1
    return compute_angle_between_vectors(v1, v2)


def keypoints_to_joint_angles(keypoints: np.ndarray) -> dict:
    """
    将21个关键点转换为关节角度。

    Args:
        keypoints: shape (21, 3) 的关键点坐标

    Returns:
        各手指关节角度字典
    """
    angles = {}

    for finger_name, chain in FINGER_CHAINS.items():
        p0 = keypoints[chain[0]]
        p1 = keypoints[chain[1]]
        p2 = keypoints[chain[2]]
        p3 = keypoints[chain[3]]

        # MCP角度（相对于伸直状态的弯曲）
        v_mcp = p1 - p0
        v_pip = p2 - p1
        mcp_bend = compute_angle_between_vectors(v_mcp, v_pip)

        # PIP角度
        v_dip = p3 - p2
        pip_bend = compute_angle_between_vectors(v_pip, v_dip)

        # DIP角度（经验公式）
        dip_bend = pip_bend * 0.7

        # 转换为关节角度（0=伸直，正数=弯曲）
        mcp_angle = max(0, mcp_bend - math.pi / 2)
        pip_angle = max(0, pip_bend - math.pi / 2)
        dip_angle = max(0, dip_bend - math.pi / 2)

        # 限制范围
        mcp_angle = min(mcp_angle, math.radians(90))
        pip_angle = min(pip_angle, math.radians(100))
        dip_angle = min(dip_angle, math.radians(80))

        angles[finger_name] = {
            "mcp": math.degrees(mcp_angle),
            "pip": math.degrees(pip_angle),
            "dip": math.degrees(dip_angle),
        }

    return angles


def validate_keypoints(keypoints: np.ndarray) -> bool:
    """
    验证关键点数据有效性。

    Args:
        keypoints: shape (21, 3) 的关键点坐标

    Returns:
        是否有效
    """
    if keypoints.shape != (21, 3):
        return False
    if np.any(np.isnan(keypoints)) or np.any(np.isinf(keypoints)):
        return False
    return True


# ──────────────── 测试用例 ────────────────

class TestAngleComputation:
    """角度计算测试。"""

    def test_straight_line(self):
        """测试直线（无弯曲）情况。"""
        # 三个点在一条直线上
        p0 = np.array([0, 0, 0])
        p1 = np.array([1, 0, 0])
        p2 = np.array([2, 0, 0])
        angle = compute_bend_angle(p0, p1, p2)
        assert abs(angle - math.pi) < 0.01  # 接近180度（直线）

    def test_right_angle(self):
        """测试直角弯曲。"""
        p0 = np.array([0, 0, 0])
        p1 = np.array([1, 0, 0])
        p2 = np.array([1, 1, 0])
        angle = compute_bend_angle(p0, p1, p2)
        assert abs(angle - math.pi / 2) < 0.01  # 接近90度

    def test_same_point(self):
        """测试相同点（退化情况）。"""
        p0 = np.array([0, 0, 0])
        p1 = np.array([0, 0, 0])
        p2 = np.array([1, 0, 0])
        angle = compute_bend_angle(p0, p1, p2)
        assert angle == 0.0  # 零长度向量返回0

    def test_parallel_vectors(self):
        """测试平行向量。"""
        p0 = np.array([0, 0, 0])
        p1 = np.array([1, 0, 0])
        p2 = np.array([2, 0, 0])
        angle = compute_angle_between_vectors(
            p1 - p0, p2 - p1
        )
        assert abs(angle) < 0.01  # 平行向量夹角为0

    def test_perpendicular_vectors(self):
        """测试垂直向量。"""
        v1 = np.array([1, 0, 0])
        v2 = np.array([0, 1, 0])
        angle = compute_angle_between_vectors(v1, v2)
        assert abs(angle - math.pi / 2) < 0.01

    def test_opposite_vectors(self):
        """测试反向向量。"""
        v1 = np.array([1, 0, 0])
        v2 = np.array([-1, 0, 0])
        angle = compute_angle_between_vectors(v1, v2)
        assert abs(angle - math.pi) < 0.01


class TestKeypointMapping:
    """关键点映射测试。"""

    def _make_straight_finger(self, start: np.ndarray, direction: np.ndarray, length: float) -> np.ndarray:
        """构建伸直手指的关键点。"""
        d = direction / np.linalg.norm(direction)
        return np.array([
            start,
            start + d * length,
            start + d * 2 * length,
            start + d * 3 * length,
        ])

    def test_straight_fingers(self):
        """测试完全伸直的手指。"""
        # 创建完全伸直的手部关键点
        keypoints = np.zeros((21, 3))

        # 手腕
        keypoints[WRIST] = [0, 0, 0]

        # 拇指（水平伸出）
        keypoints[THUMB_CMC] = [0.02, 0.01, 0]
        keypoints[THUMB_MCP] = [0.04, 0.02, 0]
        keypoints[THUMB_IP] = [0.06, 0.03, 0]
        keypoints[THUMB_TIP] = [0.08, 0.04, 0]

        # 食指（垂直向上）
        keypoints[INDEX_MCP] = [0.01, 0.02, 0]
        keypoints[INDEX_PIP] = [0.01, 0.04, 0]
        keypoints[INDEX_DIP] = [0.01, 0.06, 0]
        keypoints[INDEX_TIP] = [0.01, 0.08, 0]

        # 中指
        keypoints[MIDDLE_MCP] = [0.00, 0.02, 0]
        keypoints[MIDDLE_PIP] = [0.00, 0.045, 0]
        keypoints[MIDDLE_DIP] = [0.00, 0.065, 0]
        keypoints[MIDDLE_TIP] = [0.00, 0.085, 0]

        # 无名指
        keypoints[RING_MCP] = [-0.01, 0.02, 0]
        keypoints[RING_PIP] = [-0.01, 0.04, 0]
        keypoints[RING_DIP] = [-0.01, 0.06, 0]
        keypoints[RING_TIP] = [-0.01, 0.08, 0]

        # 小指
        keypoints[PINKY_MCP] = [-0.02, 0.015, 0]
        keypoints[PINKY_PIP] = [-0.02, 0.03, 0]
        keypoints[PINKY_DIP] = [-0.02, 0.045, 0]
        keypoints[PINKY_TIP] = [-0.02, 0.06, 0]

        angles = keypoints_to_joint_angles(keypoints)

        # 伸直时角度应接近0
        for finger_name in ["index", "middle", "ring", "pinky"]:
            assert angles[finger_name]["mcp"] < 5.0, f"{finger_name} MCP角度过大: {angles[finger_name]['mcp']}"
            assert angles[finger_name]["pip"] < 5.0, f"{finger_name} PIP角度过大: {angles[finger_name]['pip']}"

    def test_bent_fingers(self):
        """测试弯曲的手指。"""
        keypoints = np.zeros((21, 3))
        keypoints[WRIST] = [0, 0, 0]

        # 食指弯曲90度
        keypoints[INDEX_MCP] = [0.01, 0.02, 0]
        keypoints[INDEX_PIP] = [0.02, 0.02, 0]  # 水平
        keypoints[INDEX_DIP] = [0.02, 0.01, 0]  # 向下
        keypoints[INDEX_TIP] = [0.015, 0.005, 0]

        # 其他手指保持伸直
        for finger_chain in [
            [MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP],
            [RING_MCP, RING_PIP, RING_DIP, RING_TIP],
            [PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP],
        ]:
            base_idx = finger_chain[0]
            for j, idx in enumerate(finger_chain):
                keypoints[idx] = [0, 0.02 + j * 0.02, 0]

        # 拇指
        keypoints[THUMB_CMC] = [0.02, 0.01, 0]
        keypoints[THUMB_MCP] = [0.04, 0.02, 0]
        keypoints[THUMB_IP] = [0.06, 0.03, 0]
        keypoints[THUMB_TIP] = [0.08, 0.04, 0]

        angles = keypoints_to_joint_angles(keypoints)

        # 食指应该有较大的弯曲角度
        assert angles["index"]["mcp"] > 10.0, f"食指MCP弯曲不足: {angles['index']['mcp']}"

    def test_output_format(self):
        """测试输出格式。"""
        keypoints = np.zeros((21, 3))
        # 构造简单关键点
        for i in range(21):
            keypoints[i] = [0, i * 0.01, 0]

        angles = keypoints_to_joint_angles(keypoints)

        # 检查输出结构
        assert "thumb" in angles
        assert "index" in angles
        assert "middle" in angles
        assert "ring" in angles
        assert "pinky" in angles

        for finger_name in angles:
            assert "mcp" in angles[finger_name]
            assert "pip" in angles[finger_name]
            assert "dip" in angles[finger_name]
            assert isinstance(angles[finger_name]["mcp"], float)
            assert isinstance(angles[finger_name]["pip"], float)
            assert isinstance(angles[finger_name]["dip"], float)

    def test_angle_range(self):
        """测试角度范围限制。"""
        keypoints = np.zeros((21, 3))
        # 构造极端弯曲的关键点
        for i in range(21):
            keypoints[i] = [0, 0, i * 0.01]

        angles = keypoints_to_joint_angles(keypoints)

        # 角度应在合理范围内
        for finger_name in angles:
            assert 0 <= angles[finger_name]["mcp"] <= 90
            assert 0 <= angles[finger_name]["pip"] <= 100
            assert 0 <= angles[finger_name]["dip"] <= 80


class TestKeypointValidation:
    """关键点验证测试。"""

    def test_valid_keypoints(self):
        """测试有效关键点。"""
        keypoints = np.zeros((21, 3))
        assert validate_keypoints(keypoints) is True

    def test_wrong_shape(self):
        """测试错误形状。"""
        keypoints = np.zeros((20, 3))
        assert validate_keypoints(keypoints) is False

    def test_nan_values(self):
        """测试NaN值。"""
        keypoints = np.zeros((21, 3))
        keypoints[0, 0] = float('nan')
        assert validate_keypoints(keypoints) is False

    def test_inf_values(self):
        """测试Inf值。"""
        keypoints = np.zeros((21, 3))
        keypoints[0, 0] = float('inf')
        assert validate_keypoints(keypoints) is False


class TestBoundaryConditions:
    """边界条件测试。"""

    def test_zero_keypoints(self):
        """测试全零关键点。"""
        keypoints = np.zeros((21, 3))
        angles = keypoints_to_joint_angles(keypoints)
        # 不应崩溃，所有角度应为0
        for finger_name in angles:
            assert angles[finger_name]["mcp"] >= 0
            assert angles[finger_name]["pip"] >= 0
            assert angles[finger_name]["dip"] >= 0

    def test_identical_points(self):
        """测试所有点相同。"""
        keypoints = np.ones((21, 3)) * 0.5
        angles = keypoints_to_joint_angles(keypoints)
        # 不应崩溃
        assert len(angles) == 5

    def test_very_small_distances(self):
        """测试极小距离。"""
        keypoints = np.random.randn(21, 3) * 1e-10
        angles = keypoints_to_joint_angles(keypoints)
        # 不应崩溃
        assert len(angles) == 5

    def test_very_large_distances(self):
        """测试极大距离。"""
        keypoints = np.random.randn(21, 3) * 1e10
        angles = keypoints_to_joint_angles(keypoints)
        # 不应崩溃
        assert len(angles) == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
