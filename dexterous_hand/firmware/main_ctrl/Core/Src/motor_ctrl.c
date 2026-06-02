/**
 * @file    motor_ctrl.c
 * @brief   电机驱动控制实现
 * @details TIM1生成5路PWM (20kHz)，GPIO控制TB6612FNG方向
 */

#include "motor_ctrl.h"
#include <string.h>

/* ──────────────── 私有变量 ──────────────── */
static TIM_HandleTypeDef htim1;

/* TB6612FNG方向引脚: PB12~PB15 (每电机2个引脚: AIN1/AIN2) */
/* 电机0: PB12(AIN1), PB13(AIN2) */
/* 电机1: PB14(AIN1), PB15(AIN2) */
/* 电机2~4: 扩展到其他GPIO（示例中简化处理） */
#define DIR_PORT        GPIOB
#define DIR_PIN_M0_AIN1 GPIO_PIN_12
#define DIR_PIN_M0_AIN2 GPIO_PIN_13
#define DIR_PIN_M1_AIN1 GPIO_PIN_14
#define DIR_PIN_M1_AIN2 GPIO_PIN_15

/* 方向引脚表: [motor][0=AIN1, 1=AIN2] */
static const uint16_t g_dir_pins[MOTOR_COUNT][2] = {
    { GPIO_PIN_12, GPIO_PIN_13 },   /* 电机0 (拇指) */
    { GPIO_PIN_14, GPIO_PIN_15 },   /* 电机1 (食指) */
    { GPIO_PIN_0,  GPIO_PIN_1  },   /* 电机2 (中指) - GPIOC */
    { GPIO_PIN_2,  GPIO_PIN_3  },   /* 电机3 (无名指) - GPIOC */
    { GPIO_PIN_4,  GPIO_PIN_5  },   /* 电机4 (小指) - GPIOC */
};

static GPIO_TypeDef *g_dir_ports[MOTOR_COUNT] = {
    GPIOB, GPIOB, GPIOC, GPIOC, GPIOC
};

/* TIM1通道映射 */
static const uint32_t g_tim_channels[MOTOR_COUNT] = {
    TIM_CHANNEL_1,  /* PA8  - TIM1_CH1 */
    TIM_CHANNEL_2,  /* PA9  - TIM1_CH2 */
    TIM_CHANNEL_3,  /* PA10 - TIM1_CH3 */
    TIM_CHANNEL_3,  /* PE13 - TIM1_CH3N (互补) */
    TIM_CHANNEL_4,  /* PE14 - TIM1_CH4 */
};

/* 是否为互补通道 */
static const uint8_t g_is_complementary[MOTOR_COUNT] = {
    0, 0, 0, 1, 0
};

/* ──────────────── 私有函数声明 ──────────────── */
static void Motor_PWM_GPIO_Init(void);
static void Motor_DIR_GPIO_Init(void);
static uint32_t Motor_CalcCCR(int16_t duty);

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief  初始化TIM1 5路PWM + GPIO方向控制
 */
HAL_StatusTypeDef Motor_Init(void)
{
    Motor_PWM_GPIO_Init();
    Motor_DIR_GPIO_Init();

    /* TIM1基本配置 */
    __HAL_RCC_TIM1_CLK_ENABLE();

    uint32_t prescaler = 0;
    uint32_t period = (SystemCoreClock / 2) / PWM_FREQUENCY - 1;  /* APB2定时器时钟 */

    htim1.Instance = TIM1;
    htim1.Init.Prescaler = prescaler;
    htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim1.Init.Period = period;
    htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim1.Init.RepetitionCounter = 0;
    htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    if (HAL_TIM_PWM_Init(&htim1) != HAL_OK) {
        return HAL_ERROR;
    }

    /* 配置5个PWM通道 */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;

    for (int i = 0; i < MOTOR_COUNT; i++) {
        if (g_is_complementary[i]) {
            oc.OCNPolarity = TIM_OCNPOLARITY_HIGH;
            HAL_TIM_PWM_ConfigChannel(&htim1, &oc, g_tim_channels[i]);
            HAL_TIMEx_PWMN_Start(&htim1, g_tim_channels[i]);
        } else {
            HAL_TIM_PWM_ConfigChannel(&htim1, &oc, g_tim_channels[i]);
            HAL_TIM_PWM_Start(&htim1, g_tim_channels[i]);
        }
    }

    /* 使能TIM1主输出 */
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);

    return HAL_OK;
}

/**
 * @brief  初始化TIM1 PWM引脚
 */
static void Motor_PWM_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOE_CLK_ENABLE();

    /* PA8, PA9, PA10 - TIM1_CH1, CH2, CH3 */
    gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9 | GPIO_PIN_10;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF1_TIM1;
    HAL_GPIO_Init(GPIOA, &gpio);

    /* PE13, PE14 - TIM1_CH3N, CH4 */
    gpio.Pin = GPIO_PIN_13 | GPIO_PIN_14;
    HAL_GPIO_Init(GPIOE, &gpio);
}

/**
 * @brief  初始化方向控制GPIO
 */
static void Motor_DIR_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;

    /* PB12~PB15 */
    gpio.Pin = GPIO_PIN_12 | GPIO_PIN_13 | GPIO_PIN_14 | GPIO_PIN_15;
    HAL_GPIO_Init(GPIOB, &gpio);

    /* PC0~PC5 */
    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2 |
               GPIO_PIN_3 | GPIO_PIN_4 | GPIO_PIN_5;
    HAL_GPIO_Init(GPIOC, &gpio);
}

/**
 * @brief  计算CCR值
 */
static uint32_t Motor_CalcCCR(int16_t duty)
{
    if (duty > PWM_MAX_DUTY) duty = PWM_MAX_DUTY;
    if (duty < PWM_MIN_DUTY) duty = PWM_MIN_DUTY;

    uint32_t period = htim1.Init.Period;
    uint32_t abs_duty = (duty < 0) ? -duty : duty;

    return (uint32_t)((abs_duty * period) / PWM_MAX_DUTY);
}

/**
 * @brief  设置PWM占空比
 */
HAL_StatusTypeDef Motor_SetPWM(uint8_t channel, int16_t duty)
{
    if (channel >= MOTOR_COUNT) return HAL_ERROR;

    /* 设置方向 */
    if (duty > 0) {
        Motor_SetDirection(channel, 0);  /* 正转 */
    } else if (duty < 0) {
        Motor_SetDirection(channel, 1);  /* 反转 */
    } else {
        Motor_SetDirection(channel, 2);  /* 制动 */
    }

    /* 设置占空比 */
    __HAL_TIM_SET_COMPARE(&htim1, g_tim_channels[channel], Motor_CalcCCR(duty));

    return HAL_OK;
}

/**
 * @brief  设置电机方向
 */
void Motor_SetDirection(uint8_t motor, uint8_t direction)
{
    if (motor >= MOTOR_COUNT) return;

    GPIO_TypeDef *port = g_dir_ports[motor];
    uint16_t pin1 = g_dir_pins[motor][0];
    uint16_t pin2 = g_dir_pins[motor][1];

    switch (direction) {
        case 0: /* 正转: AIN1=HIGH, AIN2=LOW */
            HAL_GPIO_WritePin(port, pin1, GPIO_PIN_SET);
            HAL_GPIO_WritePin(port, pin2, GPIO_PIN_RESET);
            break;
        case 1: /* 反转: AIN1=LOW, AIN2=HIGH */
            HAL_GPIO_WritePin(port, pin1, GPIO_PIN_RESET);
            HAL_GPIO_WritePin(port, pin2, GPIO_PIN_SET);
            break;
        case 2: /* 制动: AIN1=HIGH, AIN2=HIGH */
            HAL_GPIO_WritePin(port, pin1, GPIO_PIN_SET);
            HAL_GPIO_WritePin(port, pin2, GPIO_PIN_SET);
            break;
        default:
            break;
    }
}

/**
 * @brief  停止指定电机
 */
void Motor_Stop(uint8_t motor)
{
    if (motor >= MOTOR_COUNT) return;
    Motor_SetPWM(motor, 0);
    Motor_SetDirection(motor, 2);  /* 制动 */
}

/**
 * @brief  停止所有电机
 */
void Motor_StopAll(void)
{
    for (uint8_t i = 0; i < MOTOR_COUNT; i++) {
        Motor_Stop(i);
    }
}
