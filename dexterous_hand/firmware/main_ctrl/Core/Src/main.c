/**
 * @file    main.c
 * @brief   灵巧手主控板主程序
 * @details 主循环10ms周期：UART接收->CAN广播->状态回传->心跳->安全检查
 *          TIM6中断(1kHz): 位置环PID计算（节点侧执行，主控只转发）
 *          TIM7中断(100Hz): 心跳发送 + 安全状态检查
 */

#include "main.h"
#include <string.h>

/* ──────────────── 全局变量 ──────────────── */
SystemState_t g_sys;

/* 定时器句柄 */
static TIM_HandleTypeDef htim6;  /* 1kHz 位置环定时器 */
static TIM_HandleTypeDef htim7;  /* 100Hz 心跳/安全定时器 */

/* 节点ID映射表 */
static const NodeId_t g_finger_nodes[FINGER_COUNT] = {
    NODE_ID_THUMB, NODE_ID_INDEX, NODE_ID_MIDDLE,
    NODE_ID_RING, NODE_ID_PINKY
};

/* ──────────────── 私有函数声明 ──────────────── */
static void SystemState_Init(void);
static void TIM6_Init(void);
static void TIM7_Init(void);
static void CAN_RxAngleReport(NodeId_t src, const CanFrame_t *frame);
static void CAN_RxForceReport(NodeId_t src, const CanFrame_t *frame);
static void CAN_RxErrorReport(NodeId_t src, const CanFrame_t *frame);
static void CAN_RxHeartbeat(NodeId_t src, const CanFrame_t *frame);
static uint8_t FingerIdxFromNode(NodeId_t node);

/* ──────────────── 主函数 ──────────────── */

/**
 * @brief  主函数入口
 */
int main(void)
{
    /* HAL初始化 */
    HAL_Init();

    /* 配置系统时钟 168MHz */
    SystemClock_Config();

    /* 初始化系统状态 */
    SystemState_Init();

    /* 初始化各模块 */
    CAN_Init();
    UART_Comm_Init();
    Motor_Init();
    FSR_Init();
    Safety_Init();

    /* 初始化定时器 */
    TIM6_Init();
    TIM7_Init();

    /* 注册CAN回调 */
    CAN_RegisterCallback(CMD_ANGLE_REPORT, CAN_RxAngleReport);
    CAN_RegisterCallback(CMD_FORCE_REPORT, CAN_RxForceReport);
    CAN_RegisterCallback(CMD_ERROR_REPORT, CAN_RxErrorReport);
    CAN_RegisterCallback(CMD_HEARTBEAT, CAN_RxHeartbeat);

    /* 启动FSR采集 */
    FSR_StartConversion();

    /* 设置系统运行标志 */
    g_sys.system_status = SYS_STATUS_RUNNING;

    /* ──────── 主循环 (10ms周期) ──────── */
    uint32_t last_loop_tick = HAL_GetTick();

    while (1) {
        /* 10ms周期控制 */
        uint32_t now = HAL_GetTick();
        if ((now - last_loop_tick) < MAIN_LOOP_PERIOD_MS) {
            continue;
        }
        last_loop_tick = now;

        /* 步骤1: 从UART接收AIpro的角度指令 */
        uint16_t uart_angles[FINGER_COUNT];
        if (UART_ProcessRxData(uart_angles) == HAL_OK) {
            /* 限幅 */
            for (int i = 0; i < FINGER_COUNT; i++) {
                Safety_CheckAngleLimit(&uart_angles[i]);
                g_sys.target_angles[i] = uart_angles[i];
            }
        }

        /* 步骤2: 通过CAN广播给各手指节点 */
        if (g_sys.system_status & SYS_STATUS_RUNNING) {
            CAN_BroadcastAngle(g_sys.target_angles, 500);  /* 默认速度50°/s */
        }

        /* 步骤3: 接收各节点的状态回传（通过回调已在中断中处理） */
        CAN_ProcessRxBuffer();

        /* 步骤4: 安全检查 */
        if (Safety_GetState() == SAFETY_SAFE_STOP) {
            Motor_StopAll();
            g_sys.system_status |= SYS_STATUS_ESTOP;
        } else {
            g_sys.system_status &= ~SYS_STATUS_ESTOP;
        }
    }
}

/* ──────────────── 系统配置 ──────────────── */

/**
 * @brief  配置系统时钟为168MHz
 * @details HSE=8MHz, PLL: 8MHz/8*336/2=168MHz
 *          APB1=42MHz, APB2=84MHz
 */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* 配置电压调节器输出 */
    __HAL_RCC_PWR_CLK_ENABLE();
    __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

    /* 配置HSE + PLL */
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLM = 8;
    osc.PLL.PLLN = 336;
    osc.PLL.PLLP = RCC_PLLP_DIV2;
    osc.PLL.PLLQ = 7;
    HAL_RCC_OscConfig(&osc);

    /* 配置总线时钟 */
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK |
                    RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV4;    /* 42MHz */
    clk.APB2CLKDivider = RCC_HCLK_DIV2;    /* 84MHz */
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_5);

    /* 配置SysTick */
    HAL_SYSTICK_Config(HAL_RCC_GetHCLKFreq() / 1000);
    HAL_SYSTICK_CLKSourceConfig(SYSTICK_CLKSOURCE_HCLK);
    HAL_NVIC_SetPriority(SysTick_IRQn, 0, 0);
}

/**
 * @brief  初始化系统状态
 */
static void SystemState_Init(void)
{
    memset(&g_sys, 0, sizeof(SystemState_t));
    g_sys.control_mode = CTRL_MODE_POSITION;
    g_sys.system_status = 0;
    g_sys.error_code = ERR_NONE;
}

/**
 * @brief  初始化TIM6 (1kHz定时器)
 * @details APB1定时器时钟=84MHz, 分频后1kHz
 */
static void TIM6_Init(void)
{
    __HAL_RCC_TIM6_CLK_ENABLE();

    htim6.Instance = TIM6;
    htim6.Init.Prescaler = 83;         /* 84MHz/(83+1)=1MHz */
    htim6.Init.Period = 999;           /* 1MHz/(999+1)=1kHz */
    htim6.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim6.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    HAL_TIM_Base_Init(&htim6);

    HAL_NVIC_SetPriority(TIM6_DAC_IRQn, 3, 0);
    HAL_NVIC_EnableIRQ(TIM6_DAC_IRQn);

    HAL_TIM_Base_Start_IT(&htim6);
}

/**
 * @brief  初始化TIM7 (100Hz定时器)
 * @details APB1定时器时钟=84MHz, 分频后100Hz
 */
static void TIM7_Init(void)
{
    __HAL_RCC_TIM7_CLK_ENABLE();

    htim7.Instance = TIM7;
    htim7.Init.Prescaler = 83;         /* 84MHz/(83+1)=1MHz */
    htim7.Init.Period = 9999;          /* 1MHz/(9999+1)=100Hz */
    htim7.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim7.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    HAL_TIM_Base_Init(&htim7);

    HAL_NVIC_SetPriority(TIM7_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(TIM7_IRQn);

    HAL_TIM_Base_Start_IT(&htim7);
}

/* ──────────────── 定时器中断 ──────────────── */

/**
 * @brief  TIM6中断处理 (1kHz)
 * @details 位置环PID计算（在节点侧执行，主控只转发角度指令）
 */
void TIM6_DAC_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim6);
}

/**
 * @brief  TIM6中断回调
 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM6) {
        /* 位置环PID在节点侧执行，主控不做PID计算 */
        /* 此处可用于主控侧的辅助任务 */
    } else if (htim->Instance == TIM7) {
        /* 100Hz: 心跳发送 + 安全状态检查 */
        CAN_SendHeartbeat();
        g_sys.heartbeat_counter++;
        Safety_PeriodicCheck();
    }
}

/**
 * @brief  TIM7中断处理 (100Hz)
 */
void TIM7_IRQHandler(void)
{
    HAL_TIM_IRQHandler(&htim7);
}

/* ──────────────── CAN回调处理 ──────────────── */

/**
 * @brief  从节点ID获取手指索引
 */
static uint8_t FingerIdxFromNode(NodeId_t node)
{
    if (node >= NODE_ID_THUMB && node <= NODE_ID_PINKY) {
        return (uint8_t)(node - NODE_ID_THUMB);
    }
    return 0xFF;
}

/**
 * @brief  处理角度回传
 */
static void CAN_RxAngleReport(NodeId_t src, const CanFrame_t *frame)
{
    uint8_t idx = FingerIdxFromNode(src);
    if (idx >= FINGER_COUNT) return;

    const RptAngle_t *rpt = (const RptAngle_t *)frame->data;
    g_sys.current_angles[idx] = rpt->angle;
    g_sys.node_online[idx] = true;

    /* 转发到UART（发送给AIpro） */
    UART_SendAngles(g_sys.current_angles);
}

/**
 * @brief  处理力数据回传
 */
static void CAN_RxForceReport(NodeId_t src, const CanFrame_t *frame)
{
    uint8_t idx = FingerIdxFromNode(src);
    if (idx >= FINGER_COUNT) return;

    const RptForce_t *rpt = (const RptForce_t *)frame->data;
    g_sys.force_values[idx] = rpt->force;

    /* 过载检测 */
    if (FSR_IsOverload(idx)) {
        Safety_TriggerEStop(ERR_FSR_OVERLOAD);
    }
}

/**
 * @brief  处理错误报告
 */
static void CAN_RxErrorReport(NodeId_t src, const CanFrame_t *frame)
{
    uint8_t idx = FingerIdxFromNode(src);
    if (idx >= FINGER_COUNT) return;

    g_sys.error_code = (ErrorCode_t)frame->data[0];
    g_sys.system_status |= SYS_STATUS_COMM_ERR;

    /* 根据错误类型处理 */
    if (g_sys.error_code == ERR_OVERCURRENT ||
        g_sys.error_code == ERR_STALL) {
        Safety_TriggerEStop(g_sys.error_code);
    }
}

/**
 * @brief  处理节点心跳
 */
static void CAN_RxHeartbeat(NodeId_t src, const CanFrame_t *frame)
{
    Safety_UpdateHeartbeat(src);

    uint8_t idx = FingerIdxFromNode(src);
    if (idx < FINGER_COUNT) {
        g_sys.node_online[idx] = true;
    }
}

/* ──────────────── 错误处理 ──────────────── */

/**
 * @brief  错误处理函数
 */
void Error_Handler(void)
{
    __disable_irq();
    Motor_StopAll();
    while (1) {
        /* 死循环，等待看门狗复位 */
    }
}

/**
 * @brief  USART2中断处理
 */
void USART2_IRQHandler(void)
{
    UART_IdleIRQHandler();
    HAL_UART_IRQHandler(UART_GetHandle());
}

/**
 * @brief  CAN1 RX0中断处理
 */
void CAN1_RX0_IRQHandler(void)
{
    extern CAN_HandleTypeDef hcan1;
    HAL_CAN_IRQHandler(&hcan1);
}
