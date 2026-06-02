"""关键点到关节角度映射模块.

将 21 个手部关键点映射为 5 个手指的关节角度，用于控制灵巧手。
关键点格式兼容 MediaPipe 定义。

Usage:
    python keypoint_mapper.py
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# 关键点索引定义（兼容 MediaPipe）
class KeypointIndex:
    """21 个手部关键点索引."""
    WRIST = 0

    # 拇指
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4

    # 食指
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8

    # 中指
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12

    # 无名指
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16

    # 小指
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


@dataclass
class JointLimits:
    """关节角度限制（单位：度）."""
    # 手指弯曲角度范围 [min, max]
    thumb_bend: Tuple[float, float] = (0.0, 90.0)
    thumb_abduct: Tuple[float, float] = (-30.0, 30.0)
    index_bend: Tuple[float, float] = (0.0, 90.0)
    middle_bend: Tuple[float, float] = (0.0, 90.0)
    ring_bend: Tuple[float, float] = (0.0, 90.0)
    pinky_bend: Tuple[float, float] = (0.0, 90.0)


class KeypointMapper:
    """关键点到关节角度映射器.

    将 21 个手部关键点映射为 5 个手指的弯曲角度。
    角度计算基于相邻关节向量的夹角。

    Attributes:
        joint_limits: 关节角度限制
    """

    def __init__(self, joint_limits: Optional[JointLimits] = None) -> None:
        """初始化关键点映射器.

        Args:
            joint_limits: 关节角度限制，为 None 时使用默认值
        """
        self.joint_limits = joint_limits or JointLimits()

    def _calculate_angle(
        self,
        point1: np.ndarray,
        point2: np.ndarray,
        point3: np.ndarray,
    ) -> float:
        """计算三个点形成的角度（point2 为顶点）.

        Args:
            point1: 第一个点 [x, y] 或 [x, y, z]
            point2: 顶点 [x, y] 或 [x, y, z]
            point3: 第三个点 [x, y] 或 [x, y, z]

        Returns:
            float: 角度（度）
        """
        # 计算向量
        vec1 = point1[:2] - point2[:2]
        vec2 = point3[:2] - point2[:2]

        # 计算向量模长
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        # 避免除零
        if norm1 < 1e-6 or norm2 < 1e-6:
            return 0.0

        # 计算余弦值
        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)

        # 限制范围避免数值误差
        cos_angle = np.clip(cos_angle, -1.0, 1.0)

        # 计算角度（度）
        angle = np.degrees(np.arccos(cos_angle))

        return angle

    def _calculate_bend_angle(
        self,
        base: np.ndarray,
        joint1: np.ndarray,
        joint2: np.ndarray,
        tip: np.ndarray,
    ) -> float:
        """计算手指弯曲角度.

        通过计算关节链的弯曲程度来估算手指弯曲角度。
        弯曲角度 = 180 - 平均关节角度

        Args:
            base: 基部关节
            joint1: 中间关节1
            joint2: 中间关节2
            tip: 末端关节

        Returns:
            float: 弯曲角度（度），0 表示完全伸直，90 表示完全弯曲
        """
        # 计算三个关节角度
        angle1 = self._calculate_angle(base, joint1, joint2)
        angle2 = self._calculate_angle(joint1, joint2, tip)

        # 平均角度
        avg_angle = (angle1 + angle2) / 2.0

        # 转换为弯曲角度（180度为完全伸直，90度为完全弯曲）
        bend_angle = 180.0 - avg_angle

        # 确保非负
        bend_angle = max(0.0, bend_angle)

        return bend_angle

    def _calculate_thumb_bend(self, keypoints: np.ndarray) -> float:
        """计算拇指弯曲角度.

        Args:
            keypoints: 21 个关键点 [21, 3]

        Returns:
            float: 弯曲角度（度）
        """
        wrist = keypoints[KeypointIndex.WRIST]
        cmc = keypoints[KeypointIndex.THUMB_CMC]
        mcp = keypoints[KeypointIndex.THUMB_MCP]
        ip = keypoints[KeypointIndex.THUMB_IP]
        tip = keypoints[KeypointIndex.THUMB_TIP]

        # 拇指的弯曲角度
        angle = self._calculate_bend_angle(cmc, mcp, ip, tip)

        return angle

    def _calculate_thumb_abduction(self, keypoints: np.ndarray) -> float:
        """计算拇指外展/内收角度.

        外展角度通过拇指基部关节与食指基部关节的相对位置计算。

        Args:
            keypoints: 21 个关键点 [21, 3]

        Returns:
            float: 外展角度（度），正数为外展，负数为内收
        """
        wrist = keypoints[KeypointIndex.WRIST]
        thumb_cmc = keypoints[KeypointIndex.THUMB_CMC]
        thumb_mcp = keypoints[KeypointIndex.THUMB_MCP]
        index_mcp = keypoints[KeypointIndex.INDEX_MCP]

        # 计算手掌方向向量（手腕到食指基部）
        palm_vec = index_mcp[:2] - wrist[:2]
        palm_norm = np.linalg.norm(palm_vec)

        if palm_norm < 1e-6:
            return 0.0

        palm_vec = palm_vec / palm_norm

        # 计算拇指方向向量（拇指基部到拇指 MCP）
        thumb_vec = thumb_mcp[:2] - thumb_cmc[:2]
        thumb_norm = np.linalg.norm(thumb_vec)

        if thumb_norm < 1e-6:
            return 0.0

        thumb_vec = thumb_vec / thumb_norm

        # 计算夹角
        cos_angle = np.dot(palm_vec, thumb_vec)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))

        # 判断外展/内收方向（使用叉积）
        cross = np.cross(palm_vec, thumb_vec)

        if cross < 0:
            angle = -angle

        return angle

    def _calculate_finger_bend(
        self,
        keypoints: np.ndarray,
        mcp_idx: int,
        pip_idx: int,
        dip_idx: int,
        tip_idx: int,
    ) -> float:
        """计算单个手指的弯曲角度.

        Args:
            keypoints: 21 个关键点 [21, 3]
            mcp_idx: MCP 关键点索引
            pip_idx: PIP 关键点索引
            dip_idx: DIP 关键点索引
            tip_idx: TIP 关键点索引

        Returns:
            float: 弯曲角度（度）
        """
        wrist = keypoints[KeypointIndex.WRIST]
        mcp = keypoints[mcp_idx]
        pip = keypoints[pip_idx]
        dip = keypoints[dip_idx]
        tip = keypoints[tip_idx]

        # 使用手腕作为基部
        angle = self._calculate_bend_angle(wrist, mcp, pip, tip)

        return angle

    def _clamp_angle(
        self,
        angle: float,
        limits: Tuple[float, float],
    ) -> float:
        """限制关节角度范围.

        Args:
            angle: 输入角度
            limits: 角度范围 (min, max)

        Returns:
            float: 限制后的角度
        """
        return max(limits[0], min(limits[1], angle))

    def map_to_angles(self, keypoints_21: np.ndarray) -> np.ndarray:
        """将 21 个关键点映射为 5 个手指的弯曲角度.

        Args:
            keypoints_21: 21 个关键点 [21, 3] (x, y, confidence)

        Returns:
            np.ndarray: 5 个手指的弯曲角度 [thumb, index, middle, ring, pinky]
                        单位：度
        """
        if keypoints_21.shape != (21, 3):
            raise ValueError(f"关键点形状应为 (21, 3)，实际为 {keypoints_21.shape}")

        # 检查关键点置信度
        confidences = keypoints_21[:, 2]
        if np.mean(confidences) < 0.3:
            logger.warning("关键点置信度过低，返回零角度")
            return np.zeros(5)

        # 计算各手指弯曲角度
        thumb_bend = self._calculate_thumb_bend(keypoints_21)
        index_bend = self._calculate_finger_bend(
            keypoints_21,
            KeypointIndex.INDEX_MCP,
            KeypointIndex.INDEX_PIP,
            KeypointIndex.INDEX_DIP,
            KeypointIndex.INDEX_TIP,
        )
        middle_bend = self._calculate_finger_bend(
            keypoints_21,
            KeypointIndex.MIDDLE_MCP,
            KeypointIndex.MIDDLE_PIP,
            KeypointIndex.MIDDLE_DIP,
            KeypointIndex.MIDDLE_TIP,
        )
        ring_bend = self._calculate_finger_bend(
            keypoints_21,
            KeypointIndex.RING_MCP,
            KeypointIndex.RING_PIP,
            KeypointIndex.RING_DIP,
            KeypointIndex.RING_TIP,
        )
        pinky_bend = self._calculate_finger_bend(
            keypoints_21,
            KeypointIndex.PINKY_MCP,
            KeypointIndex.PINKY_PIP,
            KeypointIndex.PINKY_DIP,
            KeypointIndex.PINKY_TIP,
        )

        # 应用关节角度限制
        thumb_bend = self._clamp_angle(thumb_bend, self.joint_limits.thumb_bend)
        index_bend = self._clamp_angle(index_bend, self.joint_limits.index_bend)
        middle_bend = self._clamp_angle(middle_bend, self.joint_limits.middle_bend)
        ring_bend = self._clamp_angle(ring_bend, self.joint_limits.ring_bend)
        pinky_bend = self._clamp_angle(pinky_bend, self.joint_limits.pinky_bend)

        angles = np.array([
            thumb_bend,
            index_bend,
            middle_bend,
            ring_bend,
            pinky_bend,
        ])

        return angles

    def map_to_detailed_angles(self, keypoints_21: np.ndarray) -> Dict[str, float]:
        """将关键点映射为详细的角度信息（包含外展角度）.

        Args:
            keypoints_21: 21 个关键点 [21, 3] (x, y, confidence)

        Returns:
            Dict[str, float]: 详细角度信息
        """
        angles = self.map_to_angles(keypoints_21)
        thumb_abduction = self._calculate_thumb_abduction(keypoints_21)

        return {
            "thumb_bend": float(angles[0]),
            "thumb_abduction": float(thumb_abduction),
            "index_bend": float(angles[1]),
            "middle_bend": float(angles[2]),
            "ring_bend": float(angles[3]),
            "pinky_bend": float(angles[4]),
        }


def main() -> None:
    """主函数（用于测试）."""
    # 创建映射器
    mapper = KeypointMapper()

    # 模拟关键点数据（手掌张开状态）
    keypoints_open = np.array([
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

    # 模拟关键点数据（握拳状态）
    keypoints_fist = np.array([
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

    logger.info("=" * 50)
    logger.info("测试关键点到关节角度映射")
    logger.info("=" * 50)

    # 测试手掌张开状态
    logger.info("\n手掌张开状态:")
    angles_open = mapper.map_to_angles(keypoints_open)
    detailed_open = mapper.map_to_detailed_angles(keypoints_open)
    logger.info(f"  弯曲角度: {angles_open}")
    logger.info(f"  详细角度: {detailed_open}")

    # 测试握拳状态
    logger.info("\n握拳状态:")
    angles_fist = mapper.map_to_angles(keypoints_fist)
    detailed_fist = mapper.map_to_detailed_angles(keypoints_fist)
    logger.info(f"  弯曲角度: {angles_fist}")
    logger.info(f"  详细角度: {detailed_fist}")

    logger.info("\n测试完成!")


if __name__ == "__main__":
    main()
