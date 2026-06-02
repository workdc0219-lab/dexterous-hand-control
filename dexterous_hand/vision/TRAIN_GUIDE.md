# 手部关键点检测模型训练指南

## 训练流程概述

```
┌─────────────────────────────────────────────────────────────┐
│  1. 安装依赖                                                 │
│     ↓                                                        │
│  2. 采集数据 (摄像头 + MediaPipe自动标注)                      │
│     ↓                                                        │
│  3. 训练模型 (YOLOv8-pose)                                   │
│     ↓                                                        │
│  4. 导出模型 (ONNX/OM)                                       │
│     ↓                                                        │
│  5. 部署推理                                                 │
└─────────────────────────────────────────────────────────────┘
```

## 1. 安装依赖

```bash
# 安装MediaPipe（用于自动标注）
pip install mediapipe

# 安装ultralytics（用于训练）
pip install ultralytics

# 安装其他依赖
pip install opencv-python numpy
```

## 2. 采集数据

### 使用摄像头采集（推荐）

```bash
cd dexterous_hand/vision/tools

# 采集500张图片
python collect_and_label.py --output ../data/hand_keypoints --samples 500
```

**操作说明：**
- 按 `s` 保存当前帧
- 按 `c` 开始/停止连续采集（每0.5秒一帧）
- 按 `q` 退出

**采集技巧：**
- 变换手的角度（正面、侧面、背面）
- 变换距离（近景、远景）
- 变换手势（张开、握拳、单指等）
- 变换光照条件
- 采集不同肤色的手
- 建议每个方向采集20-30张

### 使用公开数据集（备选）

```bash
# 下载FreiHAND数据集
# 地址: https://lmb.informatik.uni-freiburg.de/projects/freihand/

# 下载后解压到 data/freihand/
# 然后运行转换脚本
python prepare_dataset.py --source freihand --output ../data/hand_keypoints
```

## 3. 检查数据

采集完成后，检查数据集结构：

```
data/hand_keypoints/
├── images/
│   ├── train/        # 训练集图片 (90%)
│   │   ├── hand_train_000000_xxx.jpg
│   │   └── ...
│   └── val/          # 验证集图片 (10%)
│       ├── hand_val_000000_xxx.jpg
│       └── ...
└── labels/
    ├── train/        # 训练集标签
    │   ├── hand_train_000000_xxx.txt
    │   └── ...
    └── val/          # 验证集标签
        ├── hand_val_000000_xxx.txt
        └── ...
```

**检查标签格式：**
```bash
# 查看一个标签文件
cat data/hand_keypoints/labels/train/hand_train_000000_xxx.txt

# 格式: class_id cx cy w h kp1_x kp1_y kp1_v kp2_x kp2_y kp2_v ...
# 示例: 0 0.5 0.5 0.3 0.4 0.45 0.35 2 0.48 0.32 2 ...
```

## 4. 训练模型

### 基础训练

```bash
cd dexterous_hand/vision/tools

# 使用默认参数训练
python train_hand_model.py --data ../data/hand_keypoints --epochs 100
```

### 自定义训练参数

```bash
python train_hand_model.py \
    --data ../data/hand_keypoints \
    --model yolov8s-pose.pt \
    --epochs 200 \
    --batch_size 32 \
    --imgsz 640 \
    --device 0 \
    --workers 8
```

### 训练参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--data` | ./data/hand_keypoints | 数据集目录 |
| `--model` | yolov8n-pose.pt | 预训练模型 (n/s/m/l/x) |
| `--epochs` | 100 | 训练轮数 |
| `--batch_size` | 16 | 批量大小 |
| `--imgsz` | 640 | 图片尺寸 |
| `--device` | 自动 | 设备 (0=GPU, cpu=CPU) |
| `--workers` | 4 | 数据加载线程数 |

### 模型选择

| 模型 | 参数量 | 速度 | 精度 | 推荐场景 |
|------|--------|------|------|----------|
| yolov8n-pose.pt | 3.2M | ⭐⭐⭐⭐⭐ | ⭐⭐ | 边缘设备 |
| yolov8s-pose.pt | 11.6M | ⭐⭐⭐⭐ | ⭐⭐⭐ | 平衡选择 |
| yolov8m-pose.pt | 26.4M | ⭐⭐⭐ | ⭐⭐⭐⭐ | 高精度 |
| yolov8l-pose.pt | 44.4M | ⭐⭐ | ⭐⭐⭐⭐⭐ | 最高精度 |

## 5. 查看训练结果

训练完成后，结果保存在 `runs/train/hand_pose/` 目录：

```
runs/train/hand_pose/
├── weights/
│   ├── best.pt       # 最佳模型
│   └── last.pt       # 最后一轮模型
├── results.csv       # 训练指标
├── confusion_matrix.png
├── F1_curve.png
├── PR_curve.png
└── ...
```

## 6. 测试模型

```bash
# 使用摄像头测试
python test_pose.py --model runs/train/hand_pose/weights/best.pt --source 0 --show

# 使用图片测试
python test_pose.py --model runs/train/hand_pose/weights/best.pt --source test.jpg --show
```

## 7. 导出模型

### 导出ONNX

```bash
python train_hand_model.py export \
    --weights runs/train/hand_pose/weights/best.pt
```

### 导出OM格式（华为昇腾）

```bash
# 需要CANN环境
atc --model=best.onnx --framework=5 --output=best --soc_version=Ascend310
```

## 8. 常见问题

### Q: 训练时显存不足怎么办？

```bash
# 减小batch_size
python train_hand_model.py --batch_size 8

# 或使用更小的模型
python train_hand_model.py --model yolov8n-pose.pt
```

### Q: 训练精度不高怎么办？

1. 增加训练数据（采集更多图片）
2. 增加训练轮数（--epochs 200）
3. 使用更大的模型（yolov8s-pose.pt）
4. 检查数据标注质量

### Q: 没有GPU怎么训练？

```bash
# 使用CPU训练（速度较慢）
python train_hand_model.py --device cpu --epochs 50 --batch_size 4
```

### Q: 如何使用自己的图片数据？

1. 将图片放入 `data/hand_keypoints/images/train/`
2. 使用标注工具（如LabelImg）标注
3. 或使用 `collect_and_label.py` 重新采集

## 9. 训练时间参考

| 设备 | 数据量 | 模型 | 预计时间 |
|------|--------|------|----------|
| RTX 3060 | 500张 | yolov8n-pose | ~10分钟 |
| RTX 3060 | 500张 | yolov8s-pose | ~20分钟 |
| CPU (i7) | 500张 | yolov8n-pose | ~2小时 |
| CPU (i7) | 500张 | yolov8s-pose | ~4小时 |

## 10. 下一步

训练完成后，可以：

1. **集成到推理Pipeline** - 使用训练好的模型替换默认模型
2. **部署到边缘设备** - 导出ONNX/OM格式，部署到华为昇腾
3. **持续优化** - 根据实际效果，采集更多数据重新训练
