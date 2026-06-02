/**
 * @file    motor_ctrl.h
 * @brief   单路电机驱动头文件
 * @details PWM输出 + GPIO方向控制
 */

#ifndef __MOTOR_CTRL_H
#define __MOTOR_CTRL_H

#include "stm32f1xx_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 引脚定义 ──────────────── */
/* TIM3_CH1 - PB4 (PWM输出) */
/* PB2 - 方向A, PB3 - 方向B */

#define MOTOR_PWM_TIM           TIM3
#define MOTOR_PWM_TIM_CH        TIM_CHANNEL_1
#define MOTOR_PWM_MAX           1000

/* 方向引脚 */
#define MOTOR_DIR_A_PORT        GPIOB
#define MOTOR_DIR_A_PIN         GPIO_PIN_2
#define MOTOR_DIR_B_PORT        GPIOB
#define MOTOR_DIR_B_PIN         GPIO_PIN_3

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化电机驱动
 * @note  配置TIM3_CH1 PWM + PB2/PB3方向GPIO
 */
void Motor_Init(void);

/**
 * @brief 设置PWM占空比
 * @param duty 占空比 (-1000 ~ +1000), 负值反转
 */
void Motor_SetPWM(int16_t duty);

/**
 * @brief 设置电机方向
 * @param dir 0=正转, 1=反转
 */
void Motor_SetDirection(uint8_t dir);

/**
 * @brief 停止电机
 */
void Motor_Stop(void);

/**
 * @brief 获取电流采样值（预留）
 * @return ADC值, 0=未实现
 */
uint16_t Motor_GetCurrent(void);

/**
 * @brief 获取当前PWM占空比
 * @return 当前占空比 (-1000 ~ +1000)
 */
int16_t Motor_GetCurrentDuty(void);

#ifdef __cplusplus
}
#endif

#endif /* __MOTOR_CTRL_H */
