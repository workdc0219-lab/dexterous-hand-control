#!/usr/bin/env python3
"""
关键点映射器单元测试

Usage:
    pytest test_keypoint_mapper.py -v
"""

import numpy as np
import pytest

# 添加父目录到路径
import sys
sys.path.insert(0, '..')

from inference.keypoint_mapper import KeypointMapper, KeypointIndex, JointLimits


@pytest.fixture
def mapper():
    """创建映射器实例"""
    return KeypointMapper()


@pytest.fixture
def keypoints_open():
    """手掌张开状态的关键点"""
    return np.array([
        [200, 300, 0.9],  # 0: WRIST
        [220, 280, 0.9],  # 1: THUMB_CMC
        [240, 260, 0.9],  # 2: THUMB_MCP
        [260, 240, 0.9],  # 3: THUMB_IP
        [280, 220, 0.9],  # 4: THUMB_TIP
        [210, 250, 0.9],  # 5: INDEX_MCP
        [210, 200, 0.9],  # 6: INDEX_PIP
        [210, 160, 0.9],  # 7: INDEX_DIP
        [210, 120, 0.9],  # 8: INDEX_TIP
        [200, 250, 0.9],  # 9: MIDDLE_MCP
        [200, 200, 0.9],  # 10: MIDDLE_PIP
        [200, 155, 0.9],  # 11: MIDDLE_DIP
        [200, 110, 0.9],  # 12: MIDDLE_TIP
        [190, 255, 0.9],  # 13: RING_MCP
        [190, 205, 0.9],  # 14: RING_PIP
        [190, 160, 0.9],  # 15: RING_DIP
        [190, 115, 0.9],  # 16: RING_TIP
        [180, 265, 0.9],  # 17: PINKY_MCP
        [180, 220, 0.9],  # 18: PINKY_PIP
        [180, 180, 0.9],  # 19: PINKY_DIP
        [180, 140, 0.9],  # 20: PINKY_TIP
    ], dtype=np.float32)


@pytest.fixture
def keypoints_fist():
    """握拳状态的关键点"""
    return np.array([
        [200, 300, 0.9],  # 0: WRIST
        [220, 280, 0.9],  # 1: THUMB_CMC
        [230, 270, 0.9],  # 2: THUMB_MCP
        [235, 265, 0.9],  # 3: THUMB_IP
        [238, 262, 0.9],  # 4: THUMB_TIP
        [210, 260, 0.9],  # 5: INDEX_MCP
        [215, 255, 0.9],  # 6: INDEX_PIP
        [218, 252, 0.9],  # 7: INDEX_DIP
        [220, 250, 0.9],  # 8: INDEX_TIP
        [200, 260, 0.9],  # 9: MIDDLE_MCP
        [205, 255, 0.9],  # 10: MIDDLE_PIP
        [208, 252, 0.9],  # 11: MIDDLE_DIP
        [210, 250, 0.9],  # 12: MIDDLE_TIP
        [190, 260, 0.9],  # 13: RING_MCP
        [193, 255, 0.9],  # 14: RING_PIP
        [195, 252, 0.9],  # 15: RING_DIP
        [197, 250, 0.9],  # 16: RING_TIP
        [180, 265, 0.9],  # 17: PINKY_MCP
        [183, 260, 0.9],  # 18: PINKY_PIP
        [185, 257, 0.9],  # 19: PINKY_DIP
        [187, 255, 0.9],  # 20: PINKY_TIP
    ], dtype=np.float32)


class TestKeypointMapper:
    """关键点映射器测试类"""

    def test_init(self, mapper):
        """测试初始化"""
        assert mapper is not None
        assert mapper.joint_limits is not None

    def test_map_to_angles_shape(self, mapper, keypoints_open):
        """测试输出形状"""
        angles = mapper.map_to_angles(keypoints_open)
        assert angles.shape == (5,)

    def test_map_to_angles_range(self, mapper, keypoints_open):
        """测试输出范围"""
        angles = mapper.map_to_angles(keypoints_open)
        assert np.all(angles >= 0)
        assert np.all(angles <= 180)

    def test_open_hand_angles(self, mapper, keypoints_open):
        """测试手掌张开状态的角度"""
        angles = mapper.map_to_angles(keypoints_open)
        # 张开状态角度应该较小
        assert np.mean(angles) < 60, f"张开状态平均角度应<60，实际={np.mean(angles)}"

    def test_fist_hand_angles(self, mapper, keypoints_fist):
        """测试握拳状态的角度"""
        angles = mapper.map_to_angles(keypoints_fist)
        # 握拳状态角度应该较大
        assert np.mean(angles) > 30, f"握拳状态平均角度应>30，实际={np.mean(angles)}"

    def test_fist_more_bent_than_open(self, mapper, keypoints_open, keypoints_fist):
        """测试握拳比张开更弯曲"""
        angles_open = mapper.map_to_angles(keypoints_open)
        angles_fist = mapper.map_to_angles(keypoints_fist)
        # 握拳应该比张开更弯曲
        assert np.mean(angles_fist) > np.mean(angles_open)

    def test_invalid_shape(self, mapper):
        """测试无效输入形状"""
        bad_keypoints = np.zeros((10, 3))  # 错误的关键点数量
        with pytest.raises(ValueError):
            mapper.map_to_angles(bad_keypoints)

    def test_low_confidence(self, mapper, keypoints_open):
        """测试低置信度输入"""
        # 设置低置信度
        low_conf = keypoints_open.copy()
        low_conf[:, 2] = 0.1
        angles = mapper.map_to_angles(low_conf)
        # 低置信度应该返回零角度
        assert np.allclose(angles, 0)

    def test_custom_limits(self, mapper):
        """测试自定义关节限制"""
        limits = JointLimits(
            thumb_bend=(0, 45),
            index_bend=(0, 45),
        )
        mapper_custom = KeypointMapper(joint_limits=limits)

        keypoints = np.array([
            [200, 300, 0.9], [220, 280, 0.9], [240, 260, 0.9],
            [260, 240, 0.9], [280, 220, 0.9],
            [210, 250, 0.9], [210, 200, 0.9], [210, 160, 0.9],
            [210, 120, 0.9],
            [200, 250, 0.9], [200, 200, 0.9], [200, 155, 0.9],
            [200, 110, 0.9],
            [190, 255, 0.9], [190, 205, 0.9], [190, 160, 0.9],
            [190, 115, 0.9],
            [180, 265, 0.9], [180, 220, 0.9], [180, 180, 0.9],
            [180, 140, 0.9],
        ], dtype=np.float32)

        angles = mapper_custom.map_to_angles(keypoints)
        assert angles[0] <= 45  # 拇指限制
        assert angles[1] <= 45  # 食指限制

    def test_calculate_angle(self, mapper):
        """测试角度计算"""
        # 直角
        p1 = np.array([0, 1])
        p2 = np.array([0, 0])
        p3 = np.array([1, 0])
        angle = mapper._calculate_angle(p1, p2, p3)
        assert abs(angle - 90) < 1

        # 平角
        p1 = np.array([-1, 0])
        p2 = np.array([0, 0])
        p3 = np.array([1, 0])
        angle = mapper._calculate_angle(p1, p2, p3)
        assert abs(angle - 180) < 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
