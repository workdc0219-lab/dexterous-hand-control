# 系统集成指南

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

## 集成步骤

### 1. 环境准备

#### 1.1 硬件准备

- [ ] 主控板 (STM32F407VGT6)
- [ ] 手指节点 (STM32F103C8T6 × 5)
- [ ] CAN收发器 (TJA1050 × 6)
- [ ] USB摄像头 (640×480@30fps)
- [ ] ST-Link调试器
- [ ] PCAN-USB适配器

#### 1.2 软件准备

```bash
# 安装Python依赖
pip install ultralytics opencv-python pyserial python-can

# 安装STM32CubeIDE
# 下载地址: https://www.st.com/en/development-tools/stm32cubeide.html

# 安装PCAN驱动
# 下载地址: https://www.peak-system.com/PCAN-USB.199.0.html
```

### 2. 固件烧录

#### 2.1 烧录主控板固件

```bash
cd firmware/main_ctrl

# 使用Makefile编译
make

# 烧录到STM32F407
make flash
```

#### 2.2 烧录手指节点固件

```bash
cd firmware/finger_node

# 修改节点ID (0x01-0x05)
# 在main.c中修改: #define NODE_ID 0x01

# 编译
make

# 烧录到STM32F103
make flash
```

### 3. 通信测试

#### 3.1 测试UART通信

```bash
# 使用串口调试工具
python tools/uart_debug.py --port COM3 --baud 115200

# 发送测试指令
# 帧格式: [0xAA][angle0_L][angle0_H]...[angle4_L][angle4_H][CRC8][0x55]
```

#### 3.2 测试CAN通信

```bash
# 使用PCAN-View工具
# 或使用Python脚本
python tools/can_monitor.py --interface pcan --channel PCAN_USBBUS1
```

### 4. 视觉模块集成

#### 4.1 测试摄像头

```bash
cd vision/tools

# 测试摄像头
python test_pose.py --source 0 --show
```

#### 4.2 运行推理Pipeline

```bash
cd vision/inference

# 运行完整Pipeline
python pipeline.py \
    --model ../runs/pose/runs/train/hand_pose/weights/best.pt \
    --uart_port COM3 \
    --camera 0
```

### 5. 系统集成测试

#### 5.1 运行集成测试

```bash
cd tools

# 测试视觉模块
python integration_test.py --test vision

# 测试UART通信
python integration_test.py --test uart

# 测试CAN通信
python integration_test.py --test can

# 测试完整链路
python integration_test.py --test full

# 端到端延迟测试
python integration_test.py --test latency
```

#### 5.2 测试结果示例

```
============================================================
系统集成测试
============================================================
测试视觉模块
============================================================
1. 检查模型文件...
   ✓ 模型文件存在
2. 加载模型...
   ✓ 模型加载成功
3. 推理测试...
   ✓ 推理完成，检测到 1 个结果
4. 关键点映射测试...
   ✓ 关键点映射完成，角度: [10.5 20.3 30.1 40.2 50.4]
5. 轨迹平滑测试...
   ✓ 轨迹平滑完成，结果: [10.2 20.1 30.0 40.1 50.2]

测试结果汇总
============================================================
视觉模块: ✓ 通过
UART通信: ✓ 通过
CAN通信: ✓ 通过
延迟测试: ✓ 通过

总体结果: ✓ 全部通过
```

### 6. 端到端测试

#### 6.1 测试流程

1. **摄像头采集** → 640×480@30fps
2. **视觉推理** → YOLOv8-pose检测手部关键点
3. **关键点映射** → 21个关键点 → 5个手指角度
4. **轨迹平滑** → EMA滤波 + 死区处理
5. **UART发送** → 115200bps，13字节帧
6. **主控接收** → DMA + 空闲中断
7. **CAN广播** → 1Mbps，5个手指节点
8. **手指执行** → PID位置环控制

#### 6.2 性能指标

| 指标 | 目标值 | 实际值 |
|------|--------|--------|
| 视觉推理延迟 | <50ms | ~30ms |
| UART传输延迟 | <5ms | ~2ms |
| CAN传输延迟 | <2ms | ~1ms |
| 端到端延迟 | <100ms | ~50ms |
| 帧率 | >20fps | ~25fps |

### 7. 故障排除

#### 7.1 常见问题

**Q: 摄像头无法打开**
```bash
# 检查摄像头权限
# Windows: 设置 → 隐私 → 摄像头
# Linux: sudo usermod -a -G video $USER
```

**Q: UART通信失败**
```bash
# 检查串口
python -c "import serial.tools.list_ports; print(list(serial.tools.list_ports.comports()))"

# 检查波特率
# 确保主控板和PC端波特率一致 (115200)
```

**Q: CAN通信失败**
```bash
# 检查CAN接口
python -c "import can; print(can.interface.detect_available_configs())"

# 检查终端电阻
# CAN总线两端需要120Ω终端电阻
```

**Q: 手指节点不响应**
```bash
# 检查节点ID
# 确保每个节点有唯一ID (0x01-0x05)

# 检查CAN过滤器
# 确保节点过滤器配置正确
```

#### 7.2 调试工具

```bash
# UART调试
python tools/uart_debug.py --port COM3

# CAN监控
python tools/can_monitor.py --interface pcan --channel PCAN_USBBUS1

# 视觉调试
python vision/inference/test_pose.py --source 0 --show
```

### 8. 部署清单

- [ ] 固件烧录完成
- [ ] UART通信测试通过
- [ ] CAN通信测试通过
- [ ] 视觉模块测试通过
- [ ] 端到端延迟测试通过
- [ ] 多物体抓取测试通过
- [ ] 长时间运行测试通过
- [ ] 文档编写完成

## 下一步

1. **优化性能**
   - 使用华为昇腾310B加速视觉推理
   - 优化CAN总线负载
   - 减少端到端延迟

2. **增加功能**
   - 力矩闭环控制
   - 触觉反馈
   - 多模态切换

3. **产品化**
   - PCB设计优化
   - 外壳设计
   - 用户界面
