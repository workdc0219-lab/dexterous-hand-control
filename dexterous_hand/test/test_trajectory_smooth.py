#!/usr/bin/env python3
"""
@file    test_trajectory_smooth.py
@brief   轨迹平滑单元测试
@details 测试EMA平滑、死区处理、速度限制

用法:
    pytest test_trajectory_smooth.py -v
"""

import math
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import pytest

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ──────────────── 轨迹平滑实现 ────────────────

class EmaFilter:
    """指数移动平均滤波器。"""

    def __init__(self, alpha: float = 0.3) -> None:
        """
        初始化EMA滤波器。

        Args:
            alpha: 平滑系数 (0 < alpha <= 1)，越小越平滑
        """
        if not 0 < alpha <= 1:
            raise ValueError("alpha必须在(0, 1]范围内")
        self.alpha = alpha
        self._value: Optional[float] = None

    def update(self, new_value: float) -> float:
        """
        更新滤波器。

        Args:
            new_value: 新的输入值

        Returns:
            滤波后的值
        """
        if self._value is None:
            self._value = new_value
        else:
            self._value = self.alpha * new_value + (1 - self.alpha) * self._value
        return self._value

    def reset(self) -> None:
        """重置滤波器。"""
        self._value = None

    @property
    def value(self) -> Optional[float]:
        """当前滤波值。"""
        return self._value


class DeadZoneFilter:
    """死区滤波器。"""

    def __init__(self, threshold: float = 0.5) -> None:
        """
        初始化死区滤波器。

        Args:
            threshold: 死区阈值，变化量小于此值时保持不变
        """
        self.threshold = threshold
        self._value: Optional[float] = None

    def update(self, new_value: float) -> float:
        """
        更新滤波器。

        Args:
            new_value: 新的输入值

        Returns:
            滤波后的值
        """
        if self._value is None:
            self._value = new_value
        else:
            diff = new_value - self._value
            if abs(diff) >= self.threshold:
                self._value = new_value
        return self._value

    def reset(self) -> None:
        """重置滤波器。"""
        self._value = None

    @property
    def value(self) -> Optional[float]:
        """当前滤波值。"""
        return self._value


class RateLimiter:
    """速率限制器。"""

    def __init__(self, max_rate: float, dt: float = 0.01) -> None:
        """
        初始化速率限制器。

        Args:
            max_rate: 最大变化速率 (单位/秒)
            dt: 时间步长 (秒)
        """
        if max_rate <= 0:
            raise ValueError("max_rate必须为正数")
        if dt <= 0:
            raise ValueError("dt必须为正数")
        self.max_rate = max_rate
        self.dt = dt
        self._value: Optional[float] = None

    def update(self, target: float) -> float:
        """
        更新限制器，输出受速率限制的值。

        Args:
            target: 目标值

        Returns:
            受限制的值
        """
        if self._value is None:
            self._value = target
        else:
            max_change = self.max_rate * self.dt
            diff = target - self._value
            if abs(diff) > max_change:
                self._value += math.copysign(max_change, diff)
            else:
                self._value = target
        return self._value

    def reset(self) -> None:
        """重置限制器。"""
        self._value = None

    @property
    def value(self) -> Optional[float]:
        """当前值。"""
        return self._value


class TrajectorySmooth:
    """轨迹平滑器（组合滤波器）。"""

    def __init__(
        self,
        ema_alpha: float = 0.3,
        dead_zone: float = 0.5,
        max_rate: float = 100.0,
        dt: float = 0.01,
    ) -> None:
        """
        初始化轨迹平滑器。

        Args:
            ema_alpha: EMA平滑系数
            dead_zone: 死区阈值
            max_rate: 最大变化速率 (度/秒)
            dt: 时间步长
        """
        self.ema = EmaFilter(ema_alpha)
        self.dead_zone = DeadZoneFilter(dead_zone)
        self.rate_limiter = RateLimiter(max_rate, dt)

    def update(self, target: float) -> float:
        """
        更新平滑器。

        Args:
            target: 目标值

        Returns:
            平滑后的值
        """
        # 死区 -> EMA -> 速率限制
        filtered = self.dead_zone.update(target)
        smoothed = self.ema.update(filtered)
        limited = self.rate_limiter.update(smoothed)
        return limited

    def reset(self) -> None:
        """重置所有滤波器。"""
        self.ema.reset()
        self.dead_zone.reset()
        self.rate_limiter.reset()


# ──────────────── 测试用例 ────────────────

class TestEmaFilter:
    """EMA滤波器测试。"""

    def test_initial_value(self):
        """测试初始值。"""
        ema = EmaFilter(alpha=0.5)
        result = ema.update(10.0)
        assert result == 10.0

    def test_smoothing(self):
        """测试平滑效果。"""
        ema = EmaFilter(alpha=0.3)
        ema.update(0.0)
        ema.update(10.0)
        result = ema.update(10.0)
        # alpha=0.3: 第一次10 -> 0.3*10+0.7*0=3, 第二次10 -> 0.3*10+0.7*3=5.1
        assert abs(result - 5.1) < 0.01

    def test_step_response(self):
        """测试阶跃响应。"""
        ema = EmaFilter(alpha=0.5)
        values = []
        ema.update(0.0)  # 初始化
        for _ in range(20):
            values.append(ema.update(10.0))

        # 应该逐渐趋近10
        assert values[-1] > values[0]
        assert values[-1] < 10.0  # 但永远不会完全达到

    def test_alpha_one(self):
        """测试alpha=1（无平滑）。"""
        ema = EmaFilter(alpha=1.0)
        ema.update(0.0)
        result = ema.update(10.0)
        assert result == 10.0

    def test_alpha_small(self):
        """测试小alpha（强平滑）。"""
        ema = EmaFilter(alpha=0.1)
        ema.update(0.0)
        result = ema.update(10.0)
        # alpha=0.1: 0.1*10+0.9*0=1.0
        assert abs(result - 1.0) < 0.01

    def test_reset(self):
        """测试重置。"""
        ema = EmaFilter(alpha=0.5)
        ema.update(10.0)
        ema.reset()
        assert ema.value is None
        result = ema.update(5.0)
        assert result == 5.0

    def test_invalid_alpha(self):
        """测试无效alpha。"""
        with pytest.raises(ValueError):
            EmaFilter(alpha=0.0)
        with pytest.raises(ValueError):
            EmaFilter(alpha=1.5)

    def test_convergence(self):
        """测试收敛性。"""
        ema = EmaFilter(alpha=0.3)
        target = 100.0
        ema.update(0.0)
        for _ in range(100):
            ema.update(target)
        # 经过100次迭代应该非常接近目标
        assert abs(ema.value - target) < 1.0


class TestDeadZoneFilter:
    """死区滤波器测试。"""

    def test_initial_value(self):
        """测试初始值。"""
        dz = DeadZoneFilter(threshold=1.0)
        result = dz.update(10.0)
        assert result == 10.0

    def test_within_deadzone(self):
        """测试死区内变化。"""
        dz = DeadZoneFilter(threshold=1.0)
        dz.update(10.0)
        result = dz.update(10.5)  # 变化0.5 < 阈值1.0
        assert result == 10.0  # 保持不变

    def test_outside_deadzone(self):
        """测试死区外变化。"""
        dz = DeadZoneFilter(threshold=1.0)
        dz.update(10.0)
        result = dz.update(12.0)  # 变化2.0 > 阈值1.0
        assert result == 12.0  # 更新

    def test_negative_change(self):
        """测试负向变化。"""
        dz = DeadZoneFilter(threshold=1.0)
        dz.update(10.0)
        result = dz.update(8.5)  # 变化-1.5，绝对值>阈值
        assert result == 8.5

    def test_small_oscillation(self):
        """测试小幅振荡抑制。"""
        dz = DeadZoneFilter(threshold=2.0)
        dz.update(50.0)
        # 模拟噪声振荡
        for val in [50.5, 49.8, 50.3, 49.5, 50.1]:
            result = dz.update(val)
        assert result == 50.0  # 保持不变

    def test_reset(self):
        """测试重置。"""
        dz = DeadZoneFilter(threshold=1.0)
        dz.update(10.0)
        dz.reset()
        assert dz.value is None
        result = dz.update(5.0)
        assert result == 5.0


class TestRateLimiter:
    """速率限制器测试。"""

    def test_initial_value(self):
        """测试初始值。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)
        result = rl.update(50.0)
        assert result == 50.0

    def test_no_limit_needed(self):
        """测试不需要限制。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)  # max_change = 1.0/step
        rl.update(0.0)
        result = rl.update(0.5)  # 变化0.5 < 1.0
        assert result == 0.5

    def test_rate_limited(self):
        """测试速率限制。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)  # max_change = 1.0/step
        rl.update(0.0)
        result = rl.update(10.0)  # 变化10 > 1.0
        # 应该只变化1.0
        assert abs(result - 1.0) < 0.01

    def test_convergence(self):
        """测试最终收敛到目标。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)
        rl.update(0.0)
        target = 5.0
        for _ in range(100):
            rl.update(target)
        # 经过足够多步应该收敛
        assert abs(rl.value - target) < 0.1

    def test_bidirectional_limiting(self):
        """测试双向限制。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)
        rl.update(10.0)
        result = rl.update(0.0)  # 负向变化
        assert abs(result - 9.0) < 0.01  # 应该限制在-1.0

    def test_invalid_max_rate(self):
        """测试无效速率。"""
        with pytest.raises(ValueError):
            RateLimiter(max_rate=0.0)
        with pytest.raises(ValueError):
            RateLimiter(max_rate=-1.0)

    def test_reset(self):
        """测试重置。"""
        rl = RateLimiter(max_rate=100.0, dt=0.01)
        rl.update(10.0)
        rl.reset()
        assert rl.value is None


class TestTrajectorySmooth:
    """轨迹平滑器集成测试。"""

    def test_step_response(self):
        """测试阶跃响应。"""
        ts = TrajectorySmooth(ema_alpha=0.5, dead_zone=0.1, max_rate=1000.0, dt=0.01)
        ts.update(0.0)
        values = []
        for _ in range(50):
            values.append(ts.update(10.0))
        # 应该单调递增
        for i in range(1, len(values)):
            assert values[i] >= values[i - 1]

    def test_noise_rejection(self):
        """测试噪声抑制。"""
        ts = TrajectorySmooth(ema_alpha=0.3, dead_zone=1.0, max_rate=500.0, dt=0.01)
        ts.update(50.0)
        # 添加随机噪声
        np.random.seed(42)
        for _ in range(100):
            noise = np.random.randn() * 0.5  # 小噪声
            ts.update(50.0 + noise)
        # 输出应该接近50
        assert abs(ts.update(50.0) - 50.0) < 2.0

    def test_smooth_trajectory(self):
        """测试平滑轨迹。"""
        ts = TrajectorySmooth(ema_alpha=0.3, dead_zone=0.5, max_rate=200.0, dt=0.01)
        ts.update(0.0)
        # 正弦波轨迹
        t_values = np.linspace(0, 2 * math.pi, 200)
        targets = [50 + 30 * math.sin(t) for t in t_values]
        outputs = []
        for target in targets:
            outputs.append(ts.update(target))

        # 输出应该比输入更平滑（方差更小）
        target_diffs = [abs(targets[i] - targets[i - 1]) for i in range(1, len(targets))]
        output_diffs = [abs(outputs[i] - outputs[i - 1]) for i in range(1, len(outputs))]
        assert np.mean(output_diffs) < np.mean(target_diffs)

    def test_reset(self):
        """测试重置。"""
        ts = TrajectorySmooth()
        ts.update(10.0)
        ts.reset()
        result = ts.update(5.0)
        assert result == 5.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
