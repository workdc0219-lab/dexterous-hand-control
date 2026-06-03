/**
 * @file    motor_ctrl.c
 * @brief   单路电机驱动实现
 * @details TIM3_CH1 PWM + PB2/PB3方向GPIO
 */

#include "motor_ctrl.h"

/* ──────────────── 私有变量 ──────────────── */
static TIM_HandleTypeDef htim_pwm;
static int16_t s_current_duty = 0;

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 初始化电机驱动
 */
void Motor_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* 使能时钟 */
    __HAL_RCC_TIM3_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_AFIO_CLK_ENABLE();

    /* TIM3部分重映射: CH1->PB4, CH2->PB5, CH3->PB0, CH4->PB1 */
    __HAL_AFIO_REMAP_TIM3_ENABLE();

    /* 禁用JTAG，释放PB3/PB4用于GPIO/PWM功能（保留SWD调试） */
    __HAL_AFIO_REMAP_SWJ_NOJTAG();

    /* 方向引脚 PB2, PB3 */
    gpio.Pin = MOTOR_DIR_A_PIN | MOTOR_DIR_B_PIN;
    gpio.Mode = GPIO_MODE_OUTPUT_PP;
    gpio.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &gpio);

    /* 默认停止方向 */
    HAL_GPIO_WritePin(MOTOR_DIR_A_PORT, MOTOR_DIR_A_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_DIR_B_PORT, MOTOR_DIR_B_PIN, GPIO_PIN_RESET);

    /* TIM3 PWM配置 */
    htim_pwm.Instance = MOTOR_PWM_TIM;
    htim_pwm.Init.Prescaler = 72 - 1;              /* 72MHz / 72 = 1MHz */
    htim_pwm.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim_pwm.Init.Period = MOTOR_PWM_MAX - 1;      /* 1MHz / 1000 = 1kHz PWM */
    htim_pwm.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim_pwm.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;
    HAL_TIM_PWM_Init(&htim_pwm);

    /* PWM通道配置 */
    TIM_OC_InitTypeDef oc = {0};
    oc.OCMode = TIM_OCMODE_PWM1;
    oc.Pulse = 0;
    oc.OCPolarity = TIM_OCPOLARITY_HIGH;
    oc.OCFastMode = TIM_OCFAST_DISABLE;
    HAL_TIM_PWM_ConfigChannel(&htim_pwm, &oc, MOTOR_PWM_TIM_CH);

    /* 启动PWM */
    HAL_TIM_PWM_Start(&htim_pwm, MOTOR_PWM_TIM_CH);
}

/**
 * @brief 设置PWM占空比
 */
void Motor_SetPWM(int16_t duty)
{
    if (duty > MOTOR_PWM_MAX) duty = MOTOR_PWM_MAX;
    if (duty < -MOTOR_PWM_MAX) duty = -MOTOR_PWM_MAX;

    s_current_duty = duty;

    if (duty >= 0) {
        Motor_SetDirection(0);
        __HAL_TIM_SET_COMPARE(&htim_pwm, MOTOR_PWM_TIM_CH, (uint16_t)duty);
    } else {
        Motor_SetDirection(1);
        __HAL_TIM_SET_COMPARE(&htim_pwm, MOTOR_PWM_TIM_CH, (uint16_t)(-duty));
    }
}

/**
 * @brief 设置电机方向
 */
void Motor_SetDirection(uint8_t dir)
{
    if (dir == 0) {
        /* 正转: A=HIGH, B=LOW */
        HAL_GPIO_WritePin(MOTOR_DIR_A_PORT, MOTOR_DIR_A_PIN, GPIO_PIN_SET);
        HAL_GPIO_WritePin(MOTOR_DIR_B_PORT, MOTOR_DIR_B_PIN, GPIO_PIN_RESET);
    } else {
        /* 反转: A=LOW, B=HIGH */
        HAL_GPIO_WritePin(MOTOR_DIR_A_PORT, MOTOR_DIR_A_PIN, GPIO_PIN_RESET);
        HAL_GPIO_WritePin(MOTOR_DIR_B_PORT, MOTOR_DIR_B_PIN, GPIO_PIN_SET);
    }
}

/**
 * @brief 停止电机
 */
void Motor_Stop(void)
{
    s_current_duty = 0;
    __HAL_TIM_SET_COMPARE(&htim_pwm, MOTOR_PWM_TIM_CH, 0);
    HAL_GPIO_WritePin(MOTOR_DIR_A_PORT, MOTOR_DIR_A_PIN, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(MOTOR_DIR_B_PORT, MOTOR_DIR_B_PIN, GPIO_PIN_RESET);
}

/**
 * @brief 获取电流采样值（预留）
 */
uint16_t Motor_GetCurrent(void)
{
    /* TODO: 实现电流采样 */
    return 0;
}

/**
 * @brief 获取当前PWM占空比
 */
int16_t Motor_GetCurrentDuty(void)
{
    return s_current_duty;
}
