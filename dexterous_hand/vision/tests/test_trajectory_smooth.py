#!/usr/bin/env python3
"""
轨迹平滑器单元测试

Usage:
    pytest test_trajectory_smooth.py -v
"""

import numpy as np
import pytest

import sys
sys.path.insert(0, '..')

from inference.trajectory_smooth import TrajectorySmooth


@pytest.fixture
def smoother():
    """创建平滑器实例"""
    return TrajectorySmooth(
        alpha=0.3,
        deadband=2.0,
        max_velocity=180.0,
    )


class TestTrajectorySmooth:
    """轨迹平滑器测试类"""

    def test_init(self, smoother):
        """测试初始化"""
        assert smoother.alpha == 0.3
        assert smoother.deadband == 2.0
        assert smoother.max_velocity == 180.0

    def test_first_call(self, smoother):
        """测试第一次调用"""
        angles = np.array([10, 20, 30, 40, 50])
        result = smoother.smooth(angles)
        assert result.shape == (5,)

    def test_smoothing_effect(self, smoother):
        """测试平滑效果"""
        # 多次调用相同值
        angles = np.array([10, 20, 30, 40, 50])
        for _ in range(10):
            result = smoother.smooth(angles)

        # 结果应该接近输入
        np.testing.assert_allclose(result, angles, atol=1)

    def test_smoothing_reduces_jitter(self, smoother):
        """测试平滑减少抖动"""
        # 模拟抖动输入
        results = []
        for i in range(20):
            if i % 2 == 0:
                angles = np.array([10, 20, 30, 40, 50], dtype=float)
            else:
                angles = np.array([15, 25, 35, 45, 55], dtype=float)
            result = smoother.smooth(angles)
            results.append(result.copy())

        # 平滑后的结果应该比原始抖动小
        results = np.array(results)
        input_std = 2.5  # 原始抖动标准差
        output_std = np.mean(np.std(results, axis=0))
        assert output_std < input_std

    def test_deadband(self, smoother):
        """测试死区功能"""
        angles = np.array([10, 20, 30, 40, 50], dtype=float)
        result1 = smoother.smooth(angles)

        # 小变化应该被过滤
        angles_small_change = np.array([11, 21, 31, 41, 51], dtype=float)
        result2 = smoother.smooth(angles_small_change)

        # 变化小于死区，结果应该接近
        np.testing.assert_allclose(result1, result2, atol=5)

    def test_reset(self, smoother):
        """测试重置功能"""
        angles = np.array([10, 20, 30, 40, 50], dtype=float)
        smoother.smooth(angles)

        smoother.reset()

        # 重置后应该从零开始
        assert smoother._last_output is None

    def test_max_velocity(self, smoother):
        """测试最大速度限制"""
        # 大幅变化
        angles1 = np.array([0, 0, 0, 0, 0], dtype=float)
        smoother.smooth(angles1)

        angles2 = np.array([100, 100, 100, 100, 100], dtype=float)
        result = smoother.smooth(angles2)

        # 变化应该被限制
        # (需要知道dt来精确计算，这里只做粗略检查)
        assert np.all(result < 100)

    def test_convergence(self, smoother):
        """测试收敛性"""
        target = np.array([50, 60, 70, 80, 90], dtype=float)

        for _ in range(100):
            result = smoother.smooth(target)

        # 应该收敛到目标值
        np.testing.assert_allclose(result, target, atol=1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
