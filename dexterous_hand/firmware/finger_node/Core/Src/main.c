/**
 * @file    main.c
 * @brief   手指节点主程序
 * @details 系统初始化、主循环、定时器中断
 *
 * 初始化顺序: CAN → Motor → Encoder → FSR → PID → Safety
 * 主循环(1ms): CAN接收 → 读编码器 → 读FSR → 安全检查 → 状态上报
 * TIM6中断(1kHz): 位置环PID
 * TIM7中断(500Hz): 力矩环PID + 双模态切换
 */

#include "main.h"

/* ──────────────── 全局变量 ──────────────── */
FingerState_t g_finger;

/* ──────────────── 私有变量 ──────────────── */
static TIM_HandleTypeDef htim6;     /* 位置环定时器 */
static TIM_HandleTypeDef htim7;     /* 力矩环定时器 */

static volatile uint8_t s_pos_pid_flag = 0;
static volatile uint8_t s_force_pid_flag = 0;

static uint32_t s_last_report_tick = 0;

/* ──────────────── 私有函数声明 ──────────────── */
static void MX_TIM6_Init(void);
static void MX_TIM7_Init(void);
static void GPIO_Init(void);
static void FingerState_Init(void);

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 系统时钟配置
 * @note  HSE 8MHz → PLL ×9 → 72MHz
 */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef osc = {0};
    RCC_ClkInitTypeDef clk = {0};

    /* HSE振荡器配置 */
    osc.OscillatorType = RCC_OSCILLATORTYPE_HSE;
    osc.HSEState = RCC_HSE_ON;
    osc.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
    osc.PLL.PLLState = RCC_PLL_ON;
    osc.PLL.PLLSource = RCC_PLLSOURCE_HSE;
    osc.PLL.PLLMUL = RCC_PLL_MUL9;
    HAL_RCC_OscConfig(&osc);

    /* 系统时钟配置 */
    clk.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                  | RCC_CLOCKTYPE_PCLK1 | RCC_CLOCKTYPE_PCLK2;
    clk.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    clk.AHBCLKDivider = RCC_SYSCLK_DIV1;
    clk.APB1CLKDivider = RCC_HCLK_DIV2;
    clk.APB2CLKDivider = RCC_HCLK_DIV1;
    HAL_RCC_ClockConfig(&clk, FLASH_LATENCY_2);
}

/**
 * @brief GPIO初始化
 */
static void GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* LED指示灯 PC13 */
    gpio.Pin = GPIO_PIN_13;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOC, &gpio);
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_SET);  /* 默认灭 */
}

/**
 * @brief TIM6初始化 (位置环 1kHz)
 */
static void MX_TIM6_Init(void)
{
    __HAL_RCC_TIM6_CLK_ENABLE();

    htim6.Instance = TIM6;
    htim6.Init.Prescaler = 72 - 1;         /* 72MHz / 72 = 1MHz */
    htim6.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim6.Init.Period = 1000 - 1;           /* 1MHz / 1000 = 1kHz */
    htim6.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_Base_Init(&htim6);

    /* 使能更新中断 */
    HAL_TIM_Base_Start_IT(&htim6);
}

/**
 * @brief TIM7初始化 (力矩环 500Hz)
 */
static void MX_TIM7_Init(void)
{
    __HAL_RCC_TIM7_CLK_ENABLE();

    htim7.Instance = TIM7;
    htim7.Init.Prescaler = 72 - 1;         /* 72MHz / 72 = 1MHz */
    htim7.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim7.Init.Period = 2000 - 1;           /* 1MHz / 2000 = 500Hz */
    htim7.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_Base_Init(&htim7);

    /* 使能更新中断 */
    HAL_TIM_Base_Start_IT(&htim7);
}

/**
 * @brief 手指状态初始化
 */
static void FingerState_Init(void)
{
    g_finger.angle = 0;
    g_finger.encoder_raw = 0;
    g_finger.force = 0;
    g_finger.adc_raw = 0;
    g_finger.contact = 0;

    g_finger.target_angle = 0;
    g_finger.target_force = 0;
    g_finger.ctrl_mode = CTRL_MODE_POSITION;
    g_finger.speed = 0;

    g_finger.pid_kp = PID_POS_KP_DEFAULT;
    g_finger.pid_ki = PID_POS_KI_DEFAULT;
    g_finger.pid_kd = PID_POS_KD_DEFAULT;

    g_finger.sys_status = SYS_STATUS_RUNNING;
    g_finger.error_code = ERR_NONE;
    g_finger.last_can_time = 0;
    g_finger.tick = 0;
}

/* ──────────────── 主函数 ──────────────── */

/**
 * @brief 主函数入口
 */
int main(void)
{
    /* HAL初始化 */
    HAL_Init();

    /* 系统时钟配置 */
    SystemClock_Config();

    /* GPIO初始化 */
    GPIO_Init();

    /* 状态初始化 */
    FingerState_Init();

    /* 按顺序初始化各模块 */
    CAN_Protocol_Init((NodeId_t)NODE_ID);   /* CAN通信 */
    Motor_Init();                            /* 电机驱动 */
    Encoder_Init();                          /* 编码器 */
    FSR_Init();                              /* FSR传感器 */
    PID_Init();                              /* PID控制器 */
    Safety_Init();                           /* 安全保护 */

    /* 初始化定时器中断 */
    MX_TIM6_Init();     /* 位置环 1kHz */
    MX_TIM7_Init();     /* 力矩环 500Hz */

    /* 初始化完成，LED亮 */
    HAL_GPIO_WritePin(GPIOC, GPIO_PIN_13, GPIO_PIN_RESET);

    /* 主循环周期控制 */
    #define MAIN_LOOP_PERIOD_MS    1
    uint32_t last_loop_tick = HAL_GetTick();

    /* ──────────────── 主循环 ──────────────── */
    while (1) {
        /* 周期控制: 等待到下一个周期 */
        uint32_t now = HAL_GetTick();
        if ((now - last_loop_tick) < MAIN_LOOP_PERIOD_MS) {
            continue;  /* 未到周期，继续等待 */
        }
        last_loop_tick = now;

        g_finger.tick = now;

        /* 1. CAN接收处理 */
        CAN_ProcessRx();

        /* 2. 读取编码器角度 */
        g_finger.encoder_raw = Encoder_GetCount();
        g_finger.angle = Encoder_GetAngle();

        /* 3. 读取FSR力值 */
        FSR_Sample();
        g_finger.adc_raw = FSR_GetRawValue();
        g_finger.force = FSR_GetForce();
        g_finger.contact = FSR_IsContact();

        /* 4. 安全检查 */
        ErrorCode_t err = Safety_Check();
        if (err != ERR_NONE) {
            g_finger.error_code = err;
            g_finger.sys_status &= ~SYS_STATUS_RUNNING;
        }

        /* 5. 状态上报（每10ms一次） */
        if ((g_finger.tick - s_last_report_tick) >= 10) {
            s_last_report_tick = g_finger.tick;

            /* 上报角度 */
            CAN_ReportAngle(g_finger.angle, g_finger.encoder_raw);

            /* 上报力值 */
            CAN_ReportForce(g_finger.force, g_finger.adc_raw, g_finger.contact);

            /* LED心跳闪烁 */
            HAL_GPIO_TogglePin(GPIOC, GPIO_PIN_13);
        }
    }
}

/* ──────────────── 中断回调 ──────────────── */

/**
 * @brief TIM6中断回调 (1kHz 位置环)
 */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
    if (htim->Instance == TIM6) {
        /* 位置环PID */
        if (g_finger.ctrl_mode == CTRL_MODE_POSITION ||
            g_finger.ctrl_mode == CTRL_MODE_AUTO) {

            int16_t pwm = PID_PositionCalc(g_finger.target_angle, g_finger.angle);
            Motor_SetPWM(pwm);
        }
    }

    if (htim->Instance == TIM7) {
        /* 力矩环PID */
        if (g_finger.ctrl_mode == CTRL_MODE_FORCE) {
            int16_t pwm = PID_ForceCalc(g_finger.target_force, g_finger.force);
            Motor_SetPWM(pwm);
        }

        /* 自动模式: 力矩达到目标后切换到力矩环 */
        if (g_finger.ctrl_mode == CTRL_MODE_AUTO) {
            if (g_finger.contact && g_finger.target_force > 0) {
                int16_t pwm = PID_ForceCalc(g_finger.target_force, g_finger.force);
                Motor_SetPWM(pwm);
            }
        }
    }
}

/**
 * @brief NMI中断处理
 */
void NMI_Handler(void)
{
}

/**
 * @brief HardFault中断处理
 */
void HardFault_Handler(void)
{
    while (1) {
        /* 死循环 */
    }
}

/**
 * @brief MemManage中断处理
 */
void MemManage_Handler(void)
{
    while (1) {
    }
}

/**
 * @brief BusFault中断处理
 */
void BusFault_Handler(void)
{
    while (1) {
    }
}

/**
 * @brief UsageFault中断处理
 */
void UsageFault_Handler(void)
{
    while (1) {
    }
}

/**
 * @brief SVC中断处理
 */
void SVC_Handler(void)
{
}

/**
 * @brief DebugMon中断处理
 */
void DebugMon_Handler(void)
{
}

/**
 * @brief PendSV中断处理
 */
void PendSV_Handler(void)
{
}

/**
 * @brief SysTick中断处理
 */
void SysTick_Handler(void)
{
    HAL_IncTick();
}
