# 基于视触觉融合的低延迟灵巧手控制系统

**毕业设计项目** | 2026

---

## 项目简介

本项目设计并实现了一套基于视触觉融合的低延迟灵巧手控制系统，旨在解决当前灵巧手领域存在的线束繁杂、视觉控制延迟高、缺少力闭环等工程痛点。

### 核心特性

- **CAN总线分布式通信**：将线束从 O(n) 降至 O(1)，提高系统可靠性
- **边缘AI推理**：基于华为昇腾310B的YOLOv8-pose模型，端到端延迟 <50ms
- **触觉反馈闭环**：FSR传感器 + PID力矩控制，实现自适应抓取
- **MuJoCo仿真验证**：支持虚拟环境中的运动学验证和抓取测试

---

## 项目结构

```
├── dexterous_hand/          # 核心代码
│   ├── firmware/            # 固件代码
│   │   ├── main_ctrl/       # 主控板固件 (STM32F407)
│   │   └── finger_node/     # 手指节点固件 (STM32F103)
│   ├── vision/              # 视觉模块 (YOLOv8-pose)
│   ├── simulation/          # MuJoCo仿真环境
│   ├── tools/               # 调试工具
│   └── test/                # 单元测试
│
├── 技术方案文档.md           # 完整技术方案
├── 开发路线图与实操指南.md    # 9周开发计划
├── 软件架构设计.md           # 系统架构说明
├── 硬件接口与引脚分配.md      # 硬件设计文档
├── CAN通信协议规范.md         # CAN协议定义
└── 毕设项目书.docx           # 项目书
```

---

## 快速开始

### 环境要求

- Python 3.8+
- MuJoCo 3.0+
- STM32CubeIDE (固件开发)
- python-can (CAN总线通信)

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/workdc0219-lab/dexterous-hand-control.git
cd dexterous-hand-control

# 进入代码目录
cd dexterous_hand

# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 运行MuJoCo仿真
python simulation/scripts/load_hand.py

# 运行测试
pytest test/ -v
```

---

## 硬件需求

| 组件 | 型号/规格 | 数量 |
|------|----------|------|
| 主控板 | STM32F407VGT6 | 1 |
| 手指节点 | STM32F103C8T6 | 5 |
| 直流电机 | 130微型电机 | 15 |
| 磁编码器 | - | 15 |
| FSR传感器 | 薄膜压力传感器 | 5 |
| CAN收发器 | TJA1050 | 6 |
| 摄像头 | USB 640×480@30fps | 1 |

---

## 文档说明

| 文档 | 内容 |
|------|------|
| [技术方案文档](技术方案文档.md) | 完整的技术方案，包括研究背景、系统设计、实现细节 |
| [开发路线图](开发路线图与实操指南.md) | 9周开发计划，每周具体任务和产出 |
| [软件架构设计](软件架构设计.md) | 系统架构、模块划分、通信协议 |
| [硬件接口与引脚分配](硬件接口与引脚分配.md) | STM32引脚分配、PCB设计要点 |
| [CAN通信协议规范](CAN通信协议规范.md) | CAN报文格式、命令定义、状态码 |

---

## 技术栈

- **嵌入式**: STM32 HAL, FreeRTOS, CAN2.0B
- **视觉**: YOLOv8-pose, ONNX Runtime, MediaPipe
- **仿真**: MuJoCo, Python
- **通信**: python-can, UART
- **工具**: STM32CubeIDE, VSCode, Git

---

## 许可证

本项目仅用于学术研究和毕业设计。

---

## 联系方式

如有问题，请通过 GitHub Issues 反馈。
