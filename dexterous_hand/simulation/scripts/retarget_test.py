#!/usr/bin/env python3
"""
@file    retarget_test.py
@brief   重定向测试：从JSON文件读取关键点序列，使用几何法计算关节角度，在MuJoCo中驱动灵巧手
@details 读取MediaPipe格式的21个手部关键点，通过几何法计算各关节角度，
         然后在MuJoCo仿真中驱动灵巧手模型，并记录指尖位置误差。

用法:
    python retarget_test.py --input keypoints.json [--output results.json]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import mujoco
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

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

# MuJoCo关节名称映射
MUJOCO_JOINTS = {
    "thumb": ["thumb_mcp_x", "thumb_mcp_y", "thumb_pip"],
    "index": ["index_mcp", "index_pip", "index_dip"],
    "middle": ["middle_mcp", "middle_pip", "middle_dip"],
    "ring": ["ring_mcp", "ring_pip", "ring_dip"],
    "pinky": ["pinky_mcp", "pinky_pip", "pinky_dip"],
}


def compute_angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    """计算两个向量之间的夹角（弧度）。"""
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return np.arccos(cos_angle)


def compute_joint_angles_from_keypoints(keypoints: np.ndarray) -> Dict[str, List[float]]:
    """
    使用几何法从21个关键点计算各手指关节角度。

    Args:
        keypoints: shape (21, 3) 的关键点坐标数组

    Returns:
        字典，键为手指名称，值为 [mcp_angle, pip_angle, dip_angle] (弧度)
    """
    angles = {}

    for finger_name, chain in FINGER_CHAINS.items():
        # 提取关键点
        p0 = keypoints[chain[0]]  # MCP/CMC
        p1 = keypoints[chain[1]]  # PIP/MCP
        p2 = keypoints[chain[2]]  # DIP/IP
        p3 = keypoints[chain[3]]  # TIP

        # 计算向量
        v01 = p1 - p0
        v12 = p2 - p1
        v23 = p3 - p2

        # MCP角度：相对于手掌法线的弯曲
        if finger_name == "thumb":
            # 拇指使用CMC-MCP-IP角度
            mcp_angle = compute_angle_between_vectors(v01, v12) - np.pi / 2
        else:
            # 其他手指使用MCP-PIP-DIP角度
            mcp_angle = compute_angle_between_vectors(v01, v12) - np.pi / 2

        # PIP角度
        pip_angle = compute_angle_between_vectors(v01, v12) - np.pi / 2

        # DIP角度（经验公式：DIP约为PIP的60-80%）
        dip_angle = pip_angle * 0.7

        # 限制角度范围
        mcp_angle = np.clip(mcp_angle, 0, np.deg2rad(90))
        pip_angle = np.clip(pip_angle, 0, np.deg2rad(100))
        dip_angle = np.clip(dip_angle, 0, np.deg2rad(80))

        angles[finger_name] = [mcp_angle, pip_angle, dip_angle]

    return angles


def get_model_path() -> str:
    """获取MuJoCo模型文件路径。"""
    script_dir = Path(__file__).resolve().parent
    model_path = script_dir.parent / "assets" / "leap_hand_description.xml"
    if not model_path.exists():
        logger.error("模型文件不存在: %s", model_path)
        sys.exit(1)
    return str(model_path)


def run_retarget(
    keypoint_sequence: List[np.ndarray],
    model: mujoco.MjModel,
    data: mujoco.MjData,
) -> Dict[str, any]:
    """
    运行重定向测试。

    Args:
        keypoint_sequence: 关键点序列，每个元素为(21,3)数组
        model: MuJoCo模型
        data: MuJoCo数据

    Returns:
        包含每帧误差的字典
    """
    results = {
        "frame_count": len(keypoint_sequence),
        "per_frame_errors": [],
        "mean_error": 0.0,
        "max_error": 0.0,
    }

    tip_site_names = {
        "thumb": "thumb_tip_site",
        "index": "index_tip_site",
        "middle": "middle_tip_site",
        "ring": "ring_tip_site",
        "pinky": "pinky_tip_site",
    }

    for frame_idx, keypoints in enumerate(keypoint_sequence):
        # 计算关节角度
        angles = compute_joint_angles_from_keypoints(keypoints)

        # 设置MuJoCo执行器目标
        for finger_name, joint_names in MUJOCO_JOINTS.items():
            for j, jnt_name in enumerate(joint_names):
                # 查找对应的执行器
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
                        data.ctrl[act_id] = angles[finger_name][j]

        # 仿真步进
        for _ in range(50):  # 等待收敛
            mujoco.mj_step(model, data)

        # 计算指尖位置误差
        frame_errors = {}
        for finger_name, site_name in tip_site_names.items():
            site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, site_name)
            if site_id >= 0:
                sim_pos = data.site_xpos[site_id].copy()

                # 目标指尖位置（从关键点获取）
                tip_idx_map = {"thumb": THUMB_TIP, "index": INDEX_TIP,
                               "middle": MIDDLE_TIP, "ring": RING_TIP, "pinky": PINKY_TIP}
                target_pos = keypoints[tip_idx_map[finger_name]]

                error = np.linalg.norm(sim_pos - target_pos)
                frame_errors[finger_name] = float(error)

        results["per_frame_errors"].append(frame_errors)

        if frame_idx % 10 == 0:
            mean_err = np.mean(list(frame_errors.values()))
            logger.info("帧 %d/%d, 平均误差: %.4f m", frame_idx + 1, len(keypoint_sequence), mean_err)

    # 计算总体统计
    all_errors = []
    for frame_err in results["per_frame_errors"]:
        all_errors.extend(frame_err.values())

    results["mean_error"] = float(np.mean(all_errors)) if all_errors else 0.0
    results["max_error"] = float(np.max(all_errors)) if all_errors else 0.0

    return results


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="灵巧手重定向测试")
    parser.add_argument("--input", type=str, required=True, help="关键点JSON文件路径")
    parser.add_argument("--output", type=str, default=None, help="结果输出路径")
    args = parser.parse_args()

    # 加载关键点数据
    input_path = Path(args.input)
    if not input_path.exists():
        logger.error("输入文件不存在: %s", input_path)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data_dict = json.load(f)

    # 解析关键点序列
    if "frames" in data_dict:
        keypoint_sequence = [np.array(frame["keypoints"]).reshape(21, 3) for frame in data_dict["frames"]]
    elif "keypoints" in data_dict:
        keypoint_sequence = [np.array(data_dict["keypoints"]).reshape(21, 3)]
    else:
        logger.error("JSON格式不正确，需要 'frames' 或 'keypoints' 字段")
        sys.exit(1)

    logger.info("加载了 %d 帧关键点数据", len(keypoint_sequence))

    # 加载MuJoCo模型
    model_path = get_model_path()
    model = mujoco.MjModel.from_xml_path(model_path)
    data = mujoco.MjData(model)
    logger.info("MuJoCo模型加载成功")

    # 运行重定向测试
    results = run_retarget(keypoint_sequence, model, data)

    # 输出结果
    logger.info("=== 重定向测试结果 ===")
    logger.info("总帧数: %d", results["frame_count"])
    logger.info("平均误差: %.4f m", results["mean_error"])
    logger.info("最大误差: %.4f m", results["max_error"])

    # 保存结果
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info("结果已保存到: %s", output_path)
    else:
        # 打印结果
        print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
