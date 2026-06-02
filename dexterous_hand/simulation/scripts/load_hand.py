#!/usr/bin/env python3
"""
@file    load_hand.py
@brief   加载灵巧手MuJoCo模型并显示
@details 使用mujoco和mujoco.viewer加载模型，设置初始姿态（手指张开），
         支持键盘控制单个关节。

用法:
    python load_hand.py
    键盘控制:
        1-5: 选择手指 (1=拇指, 2=食指, 3=中指, 4=无名指, 5=小指)
        q/e: 选中手指的MCP关节 +/- 5度
        w/s: 选中手指的PIP关节 +/- 5度
        a/d: 选中手指的DIP关节 +/- 5度
        r:   重置为张开姿态
        ESC: 退出
"""

import logging
import sys
import os
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# 关节名称映射: finger_index -> [mcp, pip, dip]
# 拇指有3个关节但名称不同
FINGER_JOINTS = {
    0: ["thumb_mcp_x", "thumb_mcp_y", "thumb_pip"],  # 拇指
    1: ["index_mcp", "index_pip", "index_dip"],       # 食指
    2: ["middle_mcp", "middle_pip", "middle_dip"],     # 中指
    3: ["ring_mcp", "ring_pip", "ring_dip"],           # 无名指
    4: ["pinky_mcp", "pinky_pip", "pinky_dip"],        # 小指
}

FINGER_NAMES = ["拇指", "食指", "中指", "无名指", "小指"]

# 手指张开时的目标角度 (度)
OPEN_POSE = {
    0: [0.0, 0.0, 0.0],   # 拇指
    1: [0.0, 0.0, 0.0],   # 食指
    2: [0.0, 0.0, 0.0],   # 中指
    3: [0.0, 0.0, 0.0],   # 无名指
    4: [0.0, 0.0, 0.0],   # 小指
}


def get_model_path() -> str:
    """获取MuJoCo模型文件路径。"""
    script_dir = Path(__file__).resolve().parent
    model_path = script_dir.parent / "assets" / "leap_hand_description.xml"
    if not model_path.exists():
        logger.error("模型文件不存在: %s", model_path)
        sys.exit(1)
    return str(model_path)


def get_joint_id(model: mujoco.MjModel, joint_name: str) -> int:
    """根据关节名称获取关节ID。"""
    jnt_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, joint_name)
    if jnt_id == -1:
        logger.warning("关节 '%s' 未找到", joint_name)
    return jnt_id


def reset_to_open_pose(data: mujoco.MjData, model: mujoco.MjModel) -> None:
    """将所有手指重置为张开姿态。"""
    for finger_idx, joint_names in FINGER_JOINTS.items():
        for j, jnt_name in enumerate(joint_names):
            jnt_id = get_joint_id(model, jnt_name)
            if jnt_id >= 0:
                qpos_adr = model.jnt_qposadr[jnt_id]
                data.qpos[qpos_adr] = np.deg2rad(OPEN_POSE[finger_idx][j])
    mujoco.mj_forward(model, data)
    logger.info("已重置为张开姿态")


def main() -> None:
    """主函数：加载模型并启动交互式查看器。"""
    model_path = get_model_path()
    logger.info("加载模型: %s", model_path)

    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)

    logger.info("模型加载成功: %d 个关节, %d 个执行器", model.njnt, model.nu)

    # 设置初始姿态
    reset_to_open_pose(data, model)

    # 当前选中的手指和关节角度
    selected_finger = 0
    joint_angles = {i: [0.0, 0.0, 0.0] for i in range(5)}

    logger.info("启动查看器...")
    logger.info("按键说明: 1-5选择手指, q/e(MCP), w/s(PIP), a/d(DIP), r(重置)")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        # 设置相机位置
        viewer.cam.lookat[:] = [0.15, 0, 0.35]
        viewer.cam.distance = 0.5
        viewer.cam.elevation = -30
        viewer.cam.azimuth = 45

        while viewer.is_running():
            # 更新执行器目标
            for finger_idx, joint_names in FINGER_JOINTS.items():
                for j, jnt_name in enumerate(joint_names):
                    # 通过执行器名称查找对应的控制值
                    ctrl_name_map = {
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
                    ctrl_name = ctrl_name_map.get(jnt_name)
                    if ctrl_name:
                        act_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_ACTUATOR, ctrl_name)
                        if act_id >= 0:
                            data.ctrl[act_id] = np.deg2rad(joint_angles[finger_idx][j])

            mujoco.mj_step(model, data)
            viewer.sync()

    logger.info("查看器已关闭")


if __name__ == "__main__":
    main()
