/**
 * @file    motor_ctrl.h
 * @brief   电机驱动控制接口
 * @details 使用TIM1生成5路PWM (20kHz)，GPIO控制TB6612FNG方向
 *          PWM引脚: PA8(TIM1_CH1), PA9(TIM1_CH2), PA10(TIM1_CH3),
 *                   PE13(TIM1_CH3N), PE14(TIM1_CH4)
 *          方向引脚: PB12-PB15 (AIN1/AIN2)
 */

#ifndef __MOTOR_CTRL_H
#define __MOTOR_CTRL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include <stdint.h>

/* ──────────────── 电机参数 ──────────────── */
#define MOTOR_COUNT             5       /**< 电机数量 */
#define PWM_FREQUENCY           20000   /**< PWM频率 20kHz */
#define PWM_MAX_DUTY            1000    /**< 最大占空比 */
#define PWM_MIN_DUTY            (-1000) /**< 最小占空比（反转） */

/* 电机通道定义 */
#define MOTOR_CH_THUMB          0
#define MOTOR_CH_INDEX          1
#define MOTOR_CH_MIDDLE         2
#define MOTOR_CH_RING           3
#define MOTOR_CH_PINKY          4

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化TIM1 5路PWM + GPIO方向控制
 * @retval HAL状态
 */
HAL_StatusTypeDef Motor_Init(void);

/**
 * @brief  设置PWM占空比
 * @param  channel: 电机通道 (0~4)
 * @param  duty: 占空比 (-1000~+1000, 负值=反转)
 * @retval HAL状态
 */
HAL_StatusTypeDef Motor_SetPWM(uint8_t channel, int16_t duty);

/**
 * @brief  设置电机方向
 * @param  motor: 电机编号 (0~4)
 * @param  direction: 0=正转, 1=反转, 2=制动
 */
void Motor_SetDirection(uint8_t motor, uint8_t direction);

/**
 * @brief  停止指定电机
 * @param  motor: 电机编号 (0~4)
 */
void Motor_Stop(uint8_t motor);

/**
 * @brief  停止所有电机
 */
void Motor_StopAll(void);

#ifdef __cplusplus
}
#endif

#endif /* __MOTOR_CTRL_H */
