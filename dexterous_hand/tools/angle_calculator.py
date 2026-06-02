#!/usr/bin/env python3
"""
@file    angle_calculator.py
@brief   关键点角度计算器
@details 输入21个关键点坐标（手动输入或从图片检测），输出5个手指关节角度，
         可视化显示手指骨架。

用法:
    python angle_calculator.py --input keypoints.json
    python angle_calculator.py --image hand.jpg
    python angle_calculator.py --interactive
"""

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    logger.warning("matplotlib未安装，可视化功能不可用")

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

# 关键点名称
KEYPOINT_NAMES = [
    "WRIST", "THUMB_CMC", "THUMB_MCP", "THUMB_IP", "THUMB_TIP",
    "INDEX_MCP", "INDEX_PIP", "INDEX_DIP", "INDEX_TIP",
    "MIDDLE_MCP", "MIDDLE_PIP", "MIDDLE_DIP", "MIDDLE_TIP",
    "RING_MCP", "RING_PIP", "RING_DIP", "RING_TIP",
    "PINKY_MCP", "PINKY_PIP", "PINKY_DIP", "PINKY_TIP",
]

# 手指骨骼连接
FINGER_CONNECTIONS = {
    "thumb": [WRIST, THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP],
    "index": [WRIST, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP],
    "middle": [WRIST, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP],
    "ring": [WRIST, RING_MCP, RING_PIP, RING_DIP, RING_TIP],
    "pinky": [WRIST, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP],
}

FINGER_NAMES_CN = ["拇指", "食指", "中指", "无名指", "小指"]
FINGER_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]


def compute_angle_between_vectors(v1: np.ndarray, v2: np.ndarray) -> float:
    """
    计算两个向量之间的夹角（度）。

    Args:
        v1: 向量1
        v2: 向量2

    Returns:
        夹角（度）
    """
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
    cos_angle = np.clip(cos_angle, -1.0, 1.0)
    return math.degrees(math.acos(cos_angle))


def compute_finger_angles(keypoints: np.ndarray) -> Dict[str, Dict[str, float]]:
    """
    从21个关键点计算各手指关节角度。

    Args:
        keypoints: shape (21, 3) 的关键点坐标

    Returns:
        字典，键为手指名称，值为各关节角度字典
    """
    angles = {}

    # 拇指: CMC, MCP, IP关节
    thumb_cmc = compute_angle_between_vectors(
        keypoints[THUMB_CMC] - keypoints[WRIST],
        keypoints[THUMB_MCP] - keypoints[THUMB_CMC]
    )
    thumb_mcp = compute_angle_between_vectors(
        keypoints[THUMB_MCP] - keypoints[THUMB_CMC],
        keypoints[THUMB_IP] - keypoints[THUMB_MCP]
    )
    thumb_ip = compute_angle_between_vectors(
        keypoints[THUMB_IP] - keypoints[THUMB_MCP],
        keypoints[THUMB_TIP] - keypoints[THUMB_IP]
    )
    angles["thumb"] = {
        "CMC": thumb_cmc,
        "MCP": thumb_mcp,
        "IP": thumb_ip,
    }

    # 其他手指: MCP, PIP, DIP关节
    finger_joints = {
        "index": [INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP],
        "middle": [MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP],
        "ring": [RING_MCP, RING_PIP, RING_DIP, RING_TIP],
        "pinky": [PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP],
    }

    for finger_name, joints in finger_joints.items():
        mcp, pip, dip, tip = joints

        mcp_angle = compute_angle_between_vectors(
            keypoints[mcp] - keypoints[WRIST],
            keypoints[pip] - keypoints[mcp]
        )
        pip_angle = compute_angle_between_vectors(
            keypoints[pip] - keypoints[mcp],
            keypoints[dip] - keypoints[pip]
        )
        dip_angle = compute_angle_between_vectors(
            keypoints[dip] - keypoints[pip],
            keypoints[tip] - keypoints[dip]
        )

        angles[finger_name] = {
            "MCP": mcp_angle,
            "PIP": pip_angle,
            "DIP": dip_angle,
        }

    return angles


def print_angles(angles: Dict[str, Dict[str, float]]) -> None:
    """打印角度结果。"""
    print("\n" + "=" * 50)
    print("手指关节角度计算结果")
    print("=" * 50)

    for i, (finger_name, finger_angles) in enumerate(angles.items()):
        cn_name = FINGER_NAMES_CN[i] if i < len(FINGER_NAMES_CN) else finger_name
        print(f"\n{cn_name} ({finger_name}):")
        for joint_name, angle in finger_angles.items():
            print(f"  {joint_name}: {angle:.2f}°")

    print("\n" + "=" * 50)


def visualize_skeleton(keypoints: np.ndarray, angles: Optional[Dict] = None) -> None:
    """
    可视化手指骨架。

    Args:
        keypoints: shape (21, 3) 的关键点坐标
        angles: 可选的角度字典
    """
    if not HAS_MATPLOTLIB:
        logger.error("matplotlib未安装，无法可视化")
        return

    fig = plt.figure(figsize=(14, 6))

    # 3D骨架图
    ax1 = fig.add_subplot(121, projection="3d")
    ax1.set_title("手部骨架 3D", fontsize=14, fontweight="bold")
    ax1.set_xlabel("X")
    ax1.set_ylabel("Y")
    ax1.set_zlabel("Z")

    # 绘制关键点
    ax1.scatter(keypoints[:, 0], keypoints[:, 1], keypoints[:, 2],
                c="black", s=50, zorder=5)

    # 标注关键点名称
    for i, name in enumerate(KEYPOINT_NAMES):
        ax1.text(keypoints[i, 0], keypoints[i, 1], keypoints[i, 2],
                 f" {name}", fontsize=6)

    # 绘制骨骼连接
    for finger_idx, (finger_name, joints) in enumerate(FINGER_CONNECTIONS.items()):
        color = FINGER_COLORS[finger_idx]
        for j in range(len(joints) - 1):
            p1 = keypoints[joints[j]]
            p2 = keypoints[joints[j + 1]]
            ax1.plot([p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
                     color=color, linewidth=2)

    # 2D投影图
    ax2 = fig.add_subplot(122)
    ax2.set_title("手部骨架 2D (XY平面)", fontsize=14, fontweight="bold")
    ax2.set_xlabel("X")
    ax2.set_ylabel("Y")
    ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3)

    # 绘制2D骨架
    for finger_idx, (finger_name, joints) in enumerate(FINGER_CONNECTIONS.items()):
        color = FINGER_COLORS[finger_idx]
        xs = [keypoints[j, 0] for j in joints]
        ys = [keypoints[j, 1] for j in joints]
        ax2.plot(xs, ys, color=color, linewidth=2, marker="o", markersize=4, label=finger_name)

    ax2.legend()

    # 如果有角度信息，显示在图表上
    if angles:
        angle_text = "关节角度:\n"
        for i, (finger_name, finger_angles) in enumerate(angles.items()):
            cn_name = FINGER_NAMES_CN[i] if i < len(FINGER_NAMES_CN) else finger_name
            angle_text += f"{cn_name}: "
            angle_text += ", ".join(f"{k}={v:.1f}°" for k, v in finger_angles.items())
            angle_text += "\n"

        ax2.text(0.02, 0.98, angle_text, transform=ax2.transAxes,
                 fontsize=8, verticalalignment="top",
                 bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    plt.tight_layout()
    plt.show()


def detect_from_image(image_path: str) -> np.ndarray:
    """
    从图片中检测手部关键点。

    Args:
        image_path: 图片路径

    Returns:
        shape (21, 3) 的关键点坐标
    """
    try:
        import cv2
    except ImportError:
        logger.error("opencv-python未安装")
        sys.exit(1)

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics未安装")
        sys.exit(1)

    # 加载模型（如果有的话）
    model_path = Path(__file__).resolve().parent.parent / "models" / "best.pt"
    if not model_path.exists():
        logger.error("模型文件不存在: %s", model_path)
        logger.info("请先训练模型或使用 --input 参数提供关键点JSON文件")
        sys.exit(1)

    model = YOLO(str(model_path))
    image = cv2.imread(image_path)
    if image is None:
        logger.error("无法读取图片: %s", image_path)
        sys.exit(1)

    results = model(image)

    if not results or len(results) == 0:
        logger.error("未检测到手部")
        sys.exit(1)

    # 提取关键点
    result = results[0]
    if result.keypoints is None or len(result.keypoints) == 0:
        logger.error("未检测到关键点")
        sys.exit(1)

    keypoints = result.keypoints[0].xy[0].cpu().numpy()  # shape: (21, 2)

    # 添加z坐标（估计值）
    keypoints_3d = np.zeros((21, 3))
    keypoints_3d[:, :2] = keypoints
    keypoints_3d[:, 2] = 0.0  # 2D图片z=0

    return keypoints_3d


def load_from_json(json_path: str) -> np.ndarray:
    """
    从JSON文件加载关键点。

    Args:
        json_path: JSON文件路径

    Returns:
        shape (21, 3) 的关键点坐标
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "keypoints" in data:
        keypoints = np.array(data["keypoints"]).reshape(-1, 3)
    elif "frames" in data and len(data["frames"]) > 0:
        keypoints = np.array(data["frames"][0]["keypoints"]).reshape(-1, 3)
    else:
        logger.error("JSON格式不正确")
        sys.exit(1)

    if keypoints.shape[0] != 21:
        logger.error("关键点数量不正确: %d (期望21)", keypoints.shape[0])
        sys.exit(1)

    return keypoints


def interactive_input() -> np.ndarray:
    """
    交互式输入关键点。

    Returns:
        shape (21, 3) 的关键点坐标
    """
    print("\n请输入21个关键点坐标 (x, y, z)，每行一个:")
    print("格式: x y z (空格分隔)")
    print("关键点顺序:", ", ".join(KEYPOINT_NAMES))
    print()

    keypoints = []
    for i, name in enumerate(KEYPOINT_NAMES):
        while True:
            try:
                line = input(f"[{i+1:2d}/21] {name}: ").strip()
                coords = [float(x) for x in line.split()]
                if len(coords) == 2:
                    coords.append(0.0)  # 默认z=0
                if len(coords) != 3:
                    print("  需要2或3个坐标值，请重新输入")
                    continue
                keypoints.append(coords)
                break
            except ValueError:
                print("  输入格式错误，请重新输入")

    return np.array(keypoints)


def main() -> None:
    """主函数。"""
    parser = argparse.ArgumentParser(description="关键点角度计算器")
    parser.add_argument("--input", type=str, help="关键点JSON文件路径")
    parser.add_argument("--image", type=str, help="手部图片路径")
    parser.add_argument("--interactive", action="store_true", help="交互式输入")
    parser.add_argument("--no-vis", action="store_true", help="不显示可视化")
    args = parser.parse_args()

    # 获取关键点
    if args.input:
        keypoints = load_from_json(args.input)
    elif args.image:
        keypoints = detect_from_image(args.image)
    elif args.interactive:
        keypoints = interactive_input()
    else:
        logger.error("请指定 --input, --image 或 --interactive")
        parser.print_help()
        sys.exit(1)

    logger.info("关键点形状: %s", keypoints.shape)

    # 计算角度
    angles = compute_finger_angles(keypoints)

    # 打印结果
    print_angles(angles)

    # 可视化
    if not args.no_vis:
        visualize_skeleton(keypoints, angles)


if __name__ == "__main__":
    main()
