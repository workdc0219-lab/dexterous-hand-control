/**
 * @file    pid_ctrl.h
 * @brief   PID控制器接口
 * @details 增量式PID，支持位置环(1kHz)和力矩环(500Hz)
 */

#ifndef __PID_CTRL_H
#define __PID_CTRL_H

#ifdef __cplusplus
extern "C" {
#endif

#include <stdint.h>

/* ──────────────── PID参数结构体 ──────────────── */
typedef struct {
    float Kp;           /**< 比例系数 */
    float Ki;           /**< 积分系数 */
    float Kd;           /**< 微分系数 */
    float out_min;      /**< 输出下限 */
    float out_max;      /**< 输出上限 */
    float integral;     /**< 积分累积 */
    float integral_max; /**< 积分限幅 */
    float prev_error;   /**< 上一次误差 */
    float prev_error2;  /**< 上上次误差 (增量式) */
    float output;       /**< 当前输出 */
} PID_t;

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化PID控制器
 * @param  pid: PID结构体指针
 * @param  kp: 比例系数
 * @param  ki: 积分系数
 * @param  kd: 微分系数
 * @param  out_min: 输出下限
 * @param  out_max: 输出上限
 */
void PID_Init(PID_t *pid, float kp, float ki, float kd,
              float out_min, float out_max);

/**
 * @brief  增量式PID计算
 * @param  pid: PID结构体指针
 * @param  setpoint: 目标值
 * @param  measurement: 测量值
 * @retval PID输出
 */
float PID_Compute(PID_t *pid, float setpoint, float measurement);

/**
 * @brief  重置PID积分项和历史误差
 * @param  pid: PID结构体指针
 */
void PID_Reset(PID_t *pid);

/**
 * @brief  在线修改PID参数
 * @param  pid: PID结构体指针
 * @param  kp: 新比例系数
 * @param  ki: 新积分系数
 * @param  kd: 新微分系数
 */
void PID_SetParams(PID_t *pid, float kp, float ki, float kd);

#ifdef __cplusplus
}
#endif

#endif /* __PID_CTRL_H */
