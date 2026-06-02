# STM32CubeIDE 工程配置指南

## 一、创建手指节点工程 (STM32F103C8T6)

### 1.1 新建工程

1. 打开 STM32CubeIDE
2. File → New → STM32 Project
3. 选择芯片: **STM32F103C8Tx**
4. 工程名: `finger_node`
5. 位置: `dexterous_hand/firmware/finger_node`

### 1.2 时钟配置

```
HSE: 8MHz
PLL: 8MHz ×9 = 72MHz
SYSCLK: 72MHz
AHB: 72MHz
APB1: 36MHz (定时器时钟: 72MHz)
APB2: 72MHz
```

在 `.ioc` 文件中配置:
- RCC → HSE → Crystal/Ceramic Resonator
- Clock Configuration → PLL Source: HSE, Multiplier: ×9

### 1.3 GPIO 引脚配置

| 引脚 | 功能 | 模式 | 说明 |
|------|------|------|------|
| PA0 | TIM2_CH1 | Input | 编码器A相 |
| PA1 | TIM2_CH2 | Input | 编码器B相 |
| PA2 | ADC1_CH2 | Analog | FSR传感器 |
| PA5 | TIM3_CH1 | PWM | 电机PWM |
| PB2 | GPIO_Output | PP | 电机方向A |
| PB3 | GPIO_Output | PP | 电机方向B |
| PA11 | CAN1_RX | Alternate | CAN接收 |
| PA12 | CAN1_TX | Alternate | CAN发送 |
| PC13 | GPIO_Output | PP | LED指示灯 |

### 1.4 外设配置

#### TIM2 (编码器)
```
Mode: Encoder Mode
Counter Mode: Up
Counter Period: 65535
Encoder Mode: Both edges
```

#### TIM3 (PWM)
```
Channel 1: PWM Generation
Prescaler: 72-1 (72MHz/72=1MHz)
Counter Period: 1000-1 (1MHz/1000=1kHz PWM)
Pulse: 0
```

#### TIM6 (位置环定时器 1kHz)
```
Prescaler: 72-1
Counter Period: 1000-1
NVIC: Enable (Priority 3)
```

#### TIM7 (力矩环定时器 500Hz)
```
Prescaler: 72-1
Counter Period: 2000-1
NVIC: Enable (Priority 2)
```

#### ADC1
```
Mode: Independent mode
Scan Conversion Mode: Disabled
Continuous Conversion: Disabled
External Trigger: Software Start
Data Alignment: Right
Rank 1: Channel 2, Sampling Time: 239.5 Cycles
```

#### CAN1
```
Mode: Normal Mode
Prescaler: 9
Time Quanta: 1+8+7=16
Bit Rate: 72MHz/9/16 = 500Kbps (需调整到1Mbps)
Time Seg1: 8
Time Seg2: 7
SJW: 1
NVIC: Enable RX0 Interrupt
```

**注意**: CAN波特率需要根据实际APB1时钟计算:
- 目标: 1Mbps
- APB1时钟: 36MHz
- 配置: Prescaler=3, BS1=8, BS2=7 → 36MHz/3/16 = 750Kbps
- 或: Prescaler=2, BS1=15, BS2=2 → 36MHz/2/18 = 1Mbps

### 1.5 NVIC 中断配置

| 中断 | 优先级 | 说明 |
|------|--------|------|
| TIM6_DAC_IRQn | 3 | 位置环PID |
| TIM7_IRQn | 2 | 力矩环PID |
| CAN1_RX0_IRQn | 1 | CAN接收 |
| SysTick_IRQn | 0 | 系统滴答 |

### 1.6 生成代码

1. 保存 `.ioc` 文件
2. Project → Generate Code
3. 将生成的代码与现有代码合并

---

## 二、创建主控板工程 (STM32F407VGT6)

### 2.1 新建工程

1. File → New → STM32 Project
2. 选择芯片: **STM32F407VGTx**
3. 工程名: `main_ctrl`
4. 位置: `dexterous_hand/firmware/main_ctrl`

### 2.2 时钟配置

```
HSE: 8MHz
PLL: 8MHz/8×336/2 = 168MHz
SYSCLK: 168MHz
AHB: 168MHz
APB1: 42MHz (定时器时钟: 84MHz)
APB2: 84MHz
```

### 2.3 GPIO 引脚配置

| 引脚 | 功能 | 模式 | 说明 |
|------|------|------|------|
| PA11 | CAN1_RX | Alternate | CAN接收 |
| PA12 | CAN1_TX | Alternate | CAN发送 |
| PA2 | USART2_TX | Alternate | UART发送(AIpro) |
| PA3 | USART2_RX | Alternate | UART接收(AIpro) |
| PB6 | I2C1_SCL | Alternate | 可选:I2C扩展 |
| PB7 | I2C1_SDA | Alternate | 可选:I2C扩展 |

### 2.4 外设配置

#### TIM6 (1kHz)
```
Prescaler: 84-1 (84MHz/84=1MHz)
Counter Period: 1000-1
NVIC: Enable (Priority 3)
```

#### TIM7 (100Hz)
```
Prescaler: 84-1
Counter Period: 10000-1
NVIC: Enable (Priority 2)
```

#### CAN1
```
Mode: Normal Mode
Prescaler: 5
Time Quanta: 1+8+7=16
Bit Rate: 42MHz/5/16 = 525Kbps (需调整到1Mbps)
```

**主控板CAN配置**:
- APB1时钟: 42MHz
- 目标: 1Mbps
- 配置: Prescaler=3, BS1=10, BS2=3 → 42MHz/3/14 = 1Mbps

#### USART2
```
Baud Rate: 115200
Word Length: 8 Bits
Stop Bits: 1
Parity: None
NVIC: Enable
```

### 2.5 NVIC 中断配置

| 中断 | 优先级 | 说明 |
|------|--------|------|
| TIM6_DAC_IRQn | 3 | 位置环转发 |
| TIM7_IRQn | 2 | 心跳/安全 |
| CAN1_RX0_IRQn | 1 | CAN接收 |
| USART2_IRQn | 1 | UART接收 |
| SysTick_IRQn | 0 | 系统滴答 |

---

## 三、快速配置步骤

### 3.1 使用 STM32CubeMX 图形配置

1. **打开 CubeMX** (CubeIDE内置)
2. **选择芯片**: STM32F103C8T6 或 STM32F407VGT6
3. **配置引脚**: 按照上表点击引脚，选择功能
4. **配置外设**: 左侧 Peripheral 选项卡
5. **配置时钟**: Clock Configuration 选项卡
6. **配置NVIC**: System → NVIC
7. **生成代码**: Project → Generate Code

### 3.2 手动修改 hal_conf.h

```c
/* 启用需要的HAL模块 */
#define HAL_MODULE_ENABLED
#define HAL_GPIO_MODULE_ENABLED
#define HAL_TIM_MODULE_ENABLED
#define HAL_CAN_MODULE_ENABLED
#define HAL_ADC_MODULE_ENABLED
#define HAL_UART_MODULE_ENABLED
#define HAL_RCC_MODULE_ENABLED
#define HAL_CORTEX_MODULE_ENABLED
#define HAL_DMA_MODULE_ENABLED
#define HAL_FLASH_MODULE_ENABLED
#define HAL_PWR_MODULE_ENABLED
```

### 3.3 链接现有代码

将生成的代码与现有代码合并:
1. 复制 `Core/Src/` 和 `Core/Inc/` 下的现有文件
2. 保留生成的 `stm32f1xx_hal_msp.c` 和 `stm32f1xx_it.c`
3. 在 `main.c` 中调用现有模块的初始化函数

---

## 四、编译与烧录

### 4.1 编译

1. Project → Build All (Ctrl+B)
2. 检查是否有编译错误

### 4.2 烧录

1. 连接 ST-Link
2. Run → Debug (F11)
3. 程序下载到芯片

### 4.3 调试

1. 设置断点
2. Run → Resume (F8)
3. 查看变量值

---

## 五、常见问题

### Q1: CAN波特率不对
**解决**: 根据APB1时钟重新计算分频值

### Q2: 编码器计数不准
**解决**: 检查TIM2配置，确保双边沿计数

### Q3: PWM输出为0
**解决**: 检查TIM3通道配置，确保PWM模式正确

### Q4: 中断不触发
**解决**: 检查NVIC配置，确保中断使能
