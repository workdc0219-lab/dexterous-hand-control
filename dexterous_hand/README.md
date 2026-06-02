# 灵巧手视觉驱动系统

基于视觉识别的灵巧手抓取控制系统，支持手势识别、轨迹规划、CAN总线通信和MuJoCo仿真。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      主控板 (STM32)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 视觉模块  │───▶│ 手势识别  │───▶│ 轨迹规划  │              │
│  │ (YOLOv8) │    │ (MediaPipe)│   │ (几何法) │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                            │                │
│                                            ▼                │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ 手指节点  │◀──│ CAN总线   │◀──│ 指令生成  │              │
│  │ (STM32)  │   │ (1Mbps)  │    │          │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
dexterous_hand/
├── firmware/           # 固件代码
│   ├── main_ctrl/      # 主控板固件
│   └── finger_node/    # 手指节点固件
├── shared/             # 共享定义（CAN协议等）
├── vision/             # 视觉模块
│   ├── train.py        # 训练脚本
│   ├── export_onnx.py  # ONNX导出
│   └── inference.py    # 推理脚本
├── simulation/         # MuJoCo仿真
│   ├── assets/         # 模型文件
│   └── scripts/        # 仿真脚本
├── tools/              # 调试工具
├── test/               # 单元测试
├── scripts/            # 项目脚本
└── docs/               # 文档
```

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 或使用Makefile
make install
```

### 2. 运行MuJoCo仿真

```bash
# 加载灵巧手模型
python simulation/scripts/load_hand.py

# 运行抓取仿真
python simulation/scripts/grasp_sim.py --objects ball --trials 5

# 或使用Makefile
make sim
```

### 3. 运行测试

```bash
# 运行所有测试
pytest test/ -v

# 或使用Makefile
make test
```

### 4. 使用调试工具

```bash
# CAN总线监控
python tools/can_monitor.py --interface pcan --channel PCAN_USBBUS1

# FSR力值绘图
python tools/fsr_plotter.py --port COM3 --baud 115200

# 延迟测试
python tools/latency_test.py --interface pcan --channel PCAN_USBBUS1 --count 100

# 角度计算器
python tools/angle_calculator.py --interactive
```

## 模块说明

### 视觉模块 (vision/)

使用YOLOv8-pose进行手部关键点检测，支持21个关键点。

```bash
# 训练模型
python vision/train.py --data dataset.yaml --epochs 100

# 导出ONNX
python vision/export_onnx.py --weights best.pt
```

### 仿真模块 (simulation/)

MuJoCo仿真环境，支持灵巧手运动学验证和抓取测试。

- `assets/leap_hand_description.xml`: 简化的灵巧手模型
- `scripts/load_hand.py`: 加载模型并显示
- `scripts/retarget_test.py`: 重定向测试
- `scripts/grasp_sim.py`: 抓取仿真

### 调试工具 (tools/)

- `can_monitor.py`: CAN总线监控，彩色输出，支持CSV记录
- `fsr_plotter.py`: FSR力值实时绘图
- `latency_test.py`: 端到端延迟测试
- `angle_calculator.py`: 关键点角度计算器

## 硬件需求

- **主控板**: STM32F407VGT6
- **手指节点**: STM32F103C8T6 × 5
- **电机**: 130微型直流电机 × 15 (每指3个)
- **编码器**: 磁编码器 × 15
- **FSR传感器**: 薄膜压力传感器 × 5 (指尖)
- **CAN收发器**: TJA1050 × 6
- **摄像头**: USB摄像头 (支持640×480@30fps)

## 开发环境配置

### 1. Python环境

- Python 3.8+
- 推荐使用conda或venv管理环境

### 2. MuJoCo安装

```bash
pip install mujoco
```

MuJoCo 3.0+ 已包含预编译的二进制文件，无需额外下载。

### 3. CANN环境（华为昇腾）

如需模型转换为OM格式：

```bash
# 设置环境变量
export ASCEND_INSTALL_PATH=/usr/local/Ascend
source $ASCEND_INSTALL_PATH/bin/setenv.sh

# 转换模型
atc --model=best.onnx --framework=5 --output=best --soc_version=Ascend310
```

### 4. CAN总线工具

Linux:
```bash
sudo apt install can-utils
sudo ip link set can0 type can bitrate 1000000
sudo ip link set up can0
```

Windows:
- 使用PCAN驱动和python-can库

## 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- 使用Google风格的docstring
- 类型注解
- 通过pytest测试

## 许可证

本项目仅用于学术研究和毕业设计。
