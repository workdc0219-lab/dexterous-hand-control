#!/usr/bin/env python3
"""
@file    grasp_sim.py
@brief   抓取仿真：在场景中放置不同物体，执行抓取动作，检测是否成功抓取
@details 在MuJoCo场景中放置球体、圆柱体和立方体，执行5指合拢的抓取动作，
         通过检测物体高度变化来判断抓取是否成功，并记录抓取成功率。

用法:
    python grasp_sim.py [--objects ball,cylinder,cube] [--trials 5]
"""

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mujoco
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class GraspResult:
    """单次抓取结果。"""
    object_name: str
    trial: int
    success: bool
    height_change: float  # 物体高度变化 (m)
    initial_height: float
    final_height: float
    duration: float  # 仿真时间 (s)


@dataclass
class GraspStatistics:
    """抓取统计。"""
    object_name: str
    total_trials: int = 0
    success_count: int = 0
    results: List[GraspResult] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """抓取成功率。"""
        return self.success_count / self.total_trials if self.total_trials > 0 else 0.0


# 手指关节配置
FINGER_JOINTS = {
    "thumb": ["thumb_mcp_x", "thumb_mcp_y", "thumb_pip"],
    "index": ["index_mcp", "index_pip", "index_dip"],
    "middle": ["middle_mcp", "middle_pip", "middle_dip"],
    "ring": ["ring_mcp", "ring_pip", "ring_dip"],
    "pinky": ["pinky_mcp", "pinky_pip", "pinky_dip"],
}

# 执行器名称映射
CTRL_MAP = {
    "thumb_mcp_x": "thumb_mcp_x_ctrl",
    "thumb_mcp_y": "thumb_mcp_y_ctrl",
    "thumb_pip": "thumb_pip_ctrl",
    "index_mcp": "index_mcp_ctrl",
    "index_pip": "index_pip_ctrl",
    "index_dip": "index_dip_ctrl",
    "middle_mcp": "middle_mcp_ctrl",
    "middle_pip": "middle_pip_ctrl",
    "middle_dip": "middle_dip_ctrl",
    "ring_mcp": "ring_mcp_ctrl",
    "ring_pip": "ring_pip_ctrl",
    "ring_dip": "ring_dip_ctrl",
    "pinky_mcp": "pinky_mcp_ctrl",
    "pinky_pip": "pinky_pip_ctrl",
    "pinky_dip": "pinky_dip_ctrl",
}

# 抓取姿态（角度，度）
GRASP_POSE = {
    "thumb": [45.0, 60.0, 50.0],
    "index": [60.0, 70.0, 50.0],
    "middle": [60.0, 70.0, 50.0],
    "ring": [60.0, 70.0, 50.0],
    "pinky": [60.0, 70.0, 50.0],
}

# 张开姿态
OPEN_POSE = {
    "thumb": [0.0, 0.0, 0.0],
    "index": [0.0, 0.0, 0.0],
    "middle": [0.0, 0.0, 0.0],
    "ring": [0.0, 0.0, 0.0],
    "pinky": [0.0, 0.0, 0.0],
}

# 物体参数
OBJECT_CONFIGS = {
    "ball": {
        "type": "sphere",
        "size": [0.025],  # 半径 2.5cm
        "mass": 0.05,
        "pos": [0.0, 0.08, 0.0],  # 相对于手掌的初始位置
        "material": "ball_mat",
    },
    "cylinder": {
        "type": "cylinder",
        "size": [0.015, 0.04],  # 半径 1.5cm, 半高 4cm
        "mass": 0.08,
        "pos": [0.0, 0.08, 0.0],
        "material": "cylinder_mat",
    },
    "cube": {
        "type": "box",
        "size": [0.02, 0.02, 0.02],  # 4cm边长
        "mass": 0.06,
        "pos": [0.0, 0.08, 0.0],
        "material": "box_mat",
    },
}


def get_model_path() -> str:
    """获取MuJoCo模型文件路径。"""
    script_dir = Path(__file__).resolve().parent
    model_path = script_dir.parent / "assets" / "leap_hand_description.xml"
    if not model_path.exists():
        logger.error("模型文件不存在: %s", model_path)
        sys.exit(1)
    return str(model_path)


def set_hand_pose(model: mujoco.MjModel, data: mujoco.MjData, pose: Dict[str, List[float]]) -> None:
    """
    设置灵巧手姿态。

    Args:
        model: MuJoCo模型
        data: MuJoCo数据
        pose: 手指姿态字典
    """
    for finger_name, joint_names in FINGER_JOINTS.items():
        for j, jnt_name in enumerate(joint_names):
            ctrl_name = CTRL_MAP.get(jnt_name)
            if ctrl_name:
                act_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name)
                if act_id >= 0:
                    data.ctrl[act_id] = np.deg2rad(pose[finger_name][j])


def get_object_height(model: mujoco.MjModel, data: mujoco.MjData, body_name: str) -> float:
    """
    获取物体高度。

    Args:
        model: MuJoCo模型
        data: MuJoCo数据
        body_name: 物体body名称

    Returns:
        物体z坐标高度
    """
    body_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, body_name)
    if body_id >= 0:
        return float(data.xpos[body_id][2])
    return 0.0


def run_grasp_trial(
    model: mujoco.MjModel,
    data: mujoco.MjData,
    object_name: str,
    grasp_steps: int = 500,
    hold_steps: int = 200,
) -> GraspResult:
    """
    执行单次抓取试验。

    Args:
        model: MuJoCo模型
        data: MuJoCo数据
        object_name: 物体名称
        grasp_steps: 抓取阶段步数
        hold_steps: 保持阶段步数

    Returns:
        抓取结果
    """
    # 重置仿真状态
    mujoco.mj_resetData(model, data)

    # 张开手指
    set_hand_pose(model, data, OPEN_POSE)
    for _ in range(100):
        mujoco.mj_step(model, data)

    # 记录初始高度
    initial_height = get_object_height(model, data, object_name)
    start_time = time.time()

    # 渐进式抓取（线性插值）
    for step in range(grasp_steps):
        alpha = step / grasp_steps
        interpolated_pose = {}
        for finger in FINGER_JOINTS:
            interpolated_pose[finger] = [
                OPEN_POSE[finger][j] + alpha * (GRASP_POSE[finger][j] - OPEN_POSE[finger][j])
                for j in range(3)
            ]
        set_hand_pose(model, data, interpolated_pose)
        mujoco.mj_step(model, data)

    # 保持抓取
    for _ in range(hold_steps):
        set_hand_pose(model, data, GRASP_POSE)
        mujoco.mj_step(model, data)

    # 记录最终高度
    final_height = get_object_height(model, data, object_name)
    duration = time.time() - start_time

    # 判断抓取是否成功（物体高度提升超过阈值）
    height_change = final_height - initial_height
    success = height_change > 0.01  # 提升超过1cm视为成功

    return GraspResult(
        object_name=object_name,
        trial=0,
        success=success,
        height_change=height_change,
        initial_height=initial_height,
        final_height=final_height,
        duration=duration,
    )


def run_grasp_experiment(
    object_names: List[str],
    num_trials: int = 5,
) -> Dict[str, GraspStatistics]:
    """
    运行抓取实验。

    Args:
        object_names: 物体名称列表
        num_trials: 每个物体的试验次数

    Returns:
        各物体的抓取统计
    """
    # 加载模型
    model_path = get_model_path()
    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)
    logger.info("MuJoCo模型加载成功: %d 个关节", model.njnt)

    # 初始化统计
    stats: Dict[str, GraspStatistics] = {}
    for obj_name in object_names:
        stats[obj_name] = GraspStatistics(object_name=obj_name)

    # 运行试验
    for obj_name in object_names:
        logger.info("=== 测试物体: %s ===", obj_name)
        for trial in range(num_trials):
            result = run_grasp_trial(model, data, obj_name)
            result.trial = trial + 1
            stats[obj_name].results.append(result)
            stats[obj_name].total_trials += 1
            if result.success:
                stats[obj_name].success_count += 1

            logger.info(
                "  试验 %d/%d: %s, 高度变化: %.4f m",
                trial + 1, num_trials,
                "成功" if result.success else "失败",
                result.height_change,
            )

    return stats


def print_statistics(stats: Dict[str, GraspStatistics]) -> None:
    """打印抓取统计结果。"""
    print("\n" + "=" * 60)
    print("抓取实验结果")
    print("=" * 60)
    print(f"{'物体':<12} {'试验次数':<10} {'成功次数':<10} {'成功率':<10} {'平均高度变化':<12}")
    print("-" * 60)

    for obj_name, stat in stats.items():
        avg_height = np.mean([r.height_change for r in stat.results]) if stat.results else 0
        print(
            f"{obj_name:<12} {stat.total_trials:<10} {stat.success_count:<10} "
            f"{stat.success_rate:<10.1%} {avg_height:<12.4f}"
        )

    print("=" * 60)


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="灵巧手抓取仿真")
    parser.add_argument(
        "--objects", type=str, default="ball,cylinder,cube",
        help="要测试的物体，逗号分隔 (默认: ball,cylinder,cube)"
    )
    parser.add_argument("--trials", type=int, default=5, help="每个物体的试验次数 (默认: 5)")
    args = parser.parse_args()

    # 解析物体列表
    object_names = [s.strip() for s in args.objects.split(",")]
    for obj_name in object_names:
        if obj_name not in OBJECT_CONFIGS:
            logger.error("未知物体: %s (可选: %s)", obj_name, list(OBJECT_CONFIGS.keys()))
            sys.exit(1)

    logger.info("测试物体: %s, 每个物体 %d 次试验", object_names, args.trials)

    # 运行实验
    stats = run_grasp_experiment(object_names, args.trials)

    # 打印结果
    print_statistics(stats)


if __name__ == "__main__":
    main()
