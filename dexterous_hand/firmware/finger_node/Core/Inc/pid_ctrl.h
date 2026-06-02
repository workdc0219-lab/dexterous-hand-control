/**
 * @file    pid_ctrl.h
 * @brief   PID控制器头文件
 * @details 增量式PID，支持位置环/力矩环双模态
 */

#ifndef __PID_CTRL_H
#define __PID_CTRL_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── PID参数 ──────────────── */
#define PID_POS_KP_DEFAULT      10.0f
#define PID_POS_KI_DEFAULT      0.5f
#define PID_POS_KD_DEFAULT      1.0f

#define PID_FORCE_KP_DEFAULT    5.0f
#define PID_FORCE_KI_DEFAULT    0.3f
#define PID_FORCE_KD_DEFAULT    0.5f

#define PID_OUTPUT_MIN          (-1000)
#define PID_OUTPUT_MAX          1000

/* ──────────────── PID实例结构体 ──────────────── */
typedef struct {
    float kp;
    float ki;
    float kd;
    float err;
    float err_last;
    float err_prev;
    float output;
    float out_min;
    float out_max;
} PID_t;

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化PID控制器
 */
void PID_Init(void);

/**
 * @brief 设置位置环PID参数
 * @param kp 比例系数 (×100)
 * @param ki 积分系数 (×100)
 * @param kd 微分系数 (×100)
 */
void PID_SetPositionParams(uint16_t kp, uint16_t ki, uint16_t kd);

/**
 * @brief 设置力矩环PID参数
 * @param kp 比例系数 (×100)
 * @param ki 积分系数 (×100)
 * @param kd 微分系数 (×100)
 */
void PID_SetForceParams(uint16_t kp, uint16_t ki, uint16_t kd);

/**
 * @brief 位置环PID计算 (1kHz)
 * @param target 目标角度 (×10)
 * @param actual 实际角度 (×10)
 * @return PWM输出 (-1000 ~ +1000)
 */
int16_t PID_PositionCalc(uint16_t target, uint16_t actual);

/**
 * @brief 力矩环PID计算 (500Hz)
 * @param target 目标力 (×100, N)
 * @param actual 实际力 (×100, N)
 * @return PWM输出 (-1000 ~ +1000)
 */
int16_t PID_ForceCalc(uint16_t target, uint16_t actual);

/**
 * @brief 重置PID状态
 */
void PID_Reset(void);

#ifdef __cplusplus
}
#endif

#endif /* __PID_CTRL_H */
