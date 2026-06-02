"""轨迹平滑模块.

使用 EMA（指数移动平均）、死区处理和速度限制来平滑关节角度轨迹，
减少抖动和突变，提高灵巧手控制的稳定性。

Usage:
    python trajectory_smooth.py
"""

import logging
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


class TrajectorySmooth:
    """轨迹平滑器.

    使用三种策略平滑关节角度轨迹：
    1. EMA（指数移动平均）：减少高频抖动
    2. 死区处理：角度变化小于阈值时保持上一次输出
    3. 速度限制：防止角度跳变过大

    Attributes:
        alpha: EMA 平滑系数 (0, 1]，越小越平滑
        deadband: 死区阈值（度）
        max_velocity: 最大角速度（度/秒）
        num_joints: 关节数量
    """

    def __init__(
        self,
        alpha: float = 0.3,
        deadband: float = 2.0,
        max_velocity: float = 180.0,
        num_joints: int = 5,
    ) -> None:
        """初始化轨迹平滑器.

        Args:
            alpha: EMA 平滑系数 (0, 1]，越小越平滑，默认 0.3
            deadband: 死区阈值（度），变化量小于此值时保持上一次输出，默认 2.0
            max_velocity: 最大角速度（度/秒），防止跳变过大，默认 180.0
            num_joints: 关节数量，默认 5（5 个手指）
        """
        if not 0 < alpha <= 1:
            raise ValueError(f"alpha 必须在 (0, 1] 范围内，实际值: {alpha}")
        if deadband < 0:
            raise ValueError(f"deadband 不能为负数，实际值: {deadband}")
        if max_velocity <= 0:
            raise ValueError(f"max_velocity 必须为正数，实际值: {max_velocity}")

        self.alpha = alpha
        self.deadband = deadband
        self.max_velocity = max_velocity
        self.num_joints = num_joints

        # 状态变量
        self._last_output: Optional[np.ndarray] = None
        self._last_time: Optional[float] = None
        self._initialized: bool = False

    def reset(self) -> None:
        """重置平滑器状态."""
        self._last_output = None
        self._last_time = None
        self._initialized = False
        logger.debug("轨迹平滑器已重置")

    def _apply_ema(self, current: np.ndarray, target: np.ndarray) -> np.ndarray:
        """应用指数移动平均.

        Args:
            current: 当前值
            target: 目标值

        Returns:
            np.ndarray: 平滑后的值
        """
        return self.alpha * target + (1 - self.alpha) * current

    def _apply_deadband(
        self,
        current: np.ndarray,
        target: np.ndarray,
    ) -> np.ndarray:
        """应用死区处理.

        当目标值与当前值的差值小于死区阈值时，保持当前值不变。
        这可以减少在目标值附近的小幅抖动。

        Args:
            current: 当前值
            target: 目标值

        Returns:
            np.ndarray: 处理后的值
        """
        diff = target - current
        mask = np.abs(diff) >= self.deadband

        # 只更新变化量超过死区的关节
        output = np.where(mask, target, current)

        return output

    def _apply_velocity_limit(
        self,
        current: np.ndarray,
        target: np.ndarray,
        dt: float,
    ) -> np.ndarray:
        """应用速度限制.

        限制角度变化速度，防止突变。

        Args:
            current: 当前值
            target: 目标值
            dt: 时间间隔（秒）

        Returns:
            np.ndarray: 限制后的值
        """
        if dt <= 0:
            return current

        # 计算最大允许变化量
        max_delta = self.max_velocity * dt

        # 计算实际变化量
        delta = target - current

        # 限制变化量
        limited_delta = np.clip(delta, -max_delta, max_delta)

        return current + limited_delta

    def smooth(self, angles: np.ndarray) -> np.ndarray:
        """平滑关节角度.

        对输入的关节角度应用 EMA、死区处理和速度限制。

        Args:
            angles: 输入关节角度 [num_joints]，单位：度

        Returns:
            np.ndarray: 平滑后的关节角度 [num_joints]
        """
        # 验证输入
        angles = np.asarray(angles, dtype=np.float64)

        if angles.shape[0] != self.num_joints:
            raise ValueError(
                f"输入维度应为 {self.num_joints}，实际为 {angles.shape[0]}"
            )

        # 获取当前时间
        current_time = time.time()

        # 首次调用，直接返回输入
        if not self._initialized:
            self._last_output = angles.copy()
            self._last_time = current_time
            self._initialized = True
            logger.debug("轨迹平滑器初始化完成")
            return angles

        # 计算时间间隔
        dt = current_time - self._last_time

        # 步骤 1：死区处理
        deadband_output = self._apply_deadband(self._last_output, angles)

        # 步骤 2：EMA 平滑
        ema_output = self._apply_ema(self._last_output, deadband_output)

        # 步骤 3：速度限制
        velocity_limited = self._apply_velocity_limit(
            self._last_output, ema_output, dt
        )

        # 更新状态
        self._last_output = velocity_limited.copy()
        self._last_time = current_time

        return velocity_limited

    @property
    def is_initialized(self) -> bool:
        """检查平滑器是否已初始化.

        Returns:
            bool: 是否已初始化
        """
        return self._initialized

    @property
    def last_output(self) -> Optional[np.ndarray]:
        """获取上一次的输出.

        Returns:
            Optional[np.ndarray]: 上一次的输出，未初始化时返回 None
        """
        return self._last_output


def main() -> None:
    """主函数（用于测试）."""
    logger.info("=" * 50)
    logger.info("测试轨迹平滑器")
    logger.info("=" * 50)

    # 创建平滑器
    smoother = TrajectorySmooth(
        alpha=0.3,
        deadband=2.0,
        max_velocity=180.0,
        num_joints=5,
    )

    # 模拟目标角度变化
    # 从张开手（0度）到握拳（80度）的过程
    target_angles = [
        np.array([0.0, 0.0, 0.0, 0.0, 0.0]),  # 初始：完全张开
        np.array([10.0, 10.0, 10.0, 10.0, 10.0]),  # 开始弯曲
        np.array([20.0, 20.0, 20.0, 20.0, 20.0]),
        np.array([40.0, 40.0, 40.0, 40.0, 40.0]),
        np.array([60.0, 60.0, 60.0, 60.0, 60.0]),
        np.array([80.0, 80.0, 80.0, 80.0, 80.0]),  # 完全握拳
        np.array([80.0, 80.0, 80.0, 80.0, 80.0]),  # 保持
        np.array([80.5, 80.5, 80.5, 80.5, 80.5]),  # 微小抖动（死区内）
        np.array([80.0, 80.0, 80.0, 80.0, 80.0]),  # 微小抖动（死区内）
        np.array([60.0, 60.0, 60.0, 60.0, 60.0]),  # 开始张开
        np.array([40.0, 40.0, 40.0, 40.0, 40.0]),
        np.array([20.0, 20.0, 20.0, 20.0, 20.0]),
        np.array([0.0, 0.0, 0.0, 0.0, 0.0]),  # 完全张开
    ]

    logger.info("\n平滑效果测试:")
    logger.info("-" * 80)
    logger.info(f"{'步骤':<6} {'目标角度':<30} {'平滑后':<30} {'差值':<20}")
    logger.info("-" * 80)

    for i, target in enumerate(target_angles):
        smoothed = smoother.smooth(target)
        diff = smoothed - target

        logger.info(
            f"{i:<6} "
            f"[{', '.join(f'{x:6.1f}' for x in target)}]  "
            f"[{', '.join(f'{x:6.1f}' for x in smoothed)}]  "
            f"[{', '.join(f'{x:6.1f}' for x in diff)}]"
        )

        time.sleep(0.05)  # 模拟时间间隔

    logger.info("-" * 80)
    logger.info("\n测试完成!")

    # 测试重置功能
    logger.info("\n测试重置功能:")
    smoother.reset()
    logger.info(f"重置后是否已初始化: {smoother.is_initialized}")
    logger.info(f"重置后 last_output: {smoother.last_output}")

    # 重新测试
    smoothed = smoother.smooth(np.array([45.0, 45.0, 45.0, 45.0, 45.0]))
    logger.info(f"重新初始化后输出: {smoothed}")


if __name__ == "__main__":
    main()
