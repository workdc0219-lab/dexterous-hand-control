/**
 * @file    pid_ctrl.c
 * @brief   PID控制器实现
 * @details 增量式PID，位置环/力矩环双模态
 */

#include "pid_ctrl.h"

/* ──────────────── 私有变量 ──────────────── */
static PID_t s_pos_pid;     /* 位置环PID */
static PID_t s_force_pid;   /* 力矩环PID */

/* ──────────────── 私有函数 ──────────────── */

/**
 * @brief 增量式PID计算
 * @param pid PID实例
 * @param error 误差
 * @return PID输出
 */
static float PID_CalcIncremental(PID_t *pid, float error)
{
    pid->err = error;

    /* 增量式PID公式:
     * delta_u = Kp*(e(k)-e(k-1)) + Ki*e(k) + Kd*(e(k)-2*e(k-1)+e(k-2))
     */
    float delta = pid->kp * (pid->err - pid->err_last)
                + pid->ki * pid->err
                + pid->kd * (pid->err - 2.0f * pid->err_last + pid->err_prev);

    pid->output += delta;

    /* 输出限幅 */
    if (pid->output > pid->out_max) pid->output = pid->out_max;
    if (pid->output < pid->out_min) pid->output = pid->out_min;

    /* 更新历史误差 */
    pid->err_prev = pid->err_last;
    pid->err_last = pid->err;

    return pid->output;
}

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 初始化PID控制器
 */
void PID_Init(void)
{
    /* 位置环默认参数 */
    s_pos_pid.kp = PID_POS_KP_DEFAULT;
    s_pos_pid.ki = PID_POS_KI_DEFAULT;
    s_pos_pid.kd = PID_POS_KD_DEFAULT;
    s_pos_pid.out_min = PID_OUTPUT_MIN;
    s_pos_pid.out_max = PID_OUTPUT_MAX;
    s_pos_pid.err = 0;
    s_pos_pid.err_last = 0;
    s_pos_pid.err_prev = 0;
    s_pos_pid.output = 0;

    /* 力矩环默认参数 */
    s_force_pid.kp = PID_FORCE_KP_DEFAULT;
    s_force_pid.ki = PID_FORCE_KI_DEFAULT;
    s_force_pid.kd = PID_FORCE_KD_DEFAULT;
    s_force_pid.out_min = PID_OUTPUT_MIN;
    s_force_pid.out_max = PID_OUTPUT_MAX;
    s_force_pid.err = 0;
    s_force_pid.err_last = 0;
    s_force_pid.err_prev = 0;
    s_force_pid.output = 0;
}

/**
 * @brief 设置位置环PID参数
 */
void PID_SetPositionParams(uint16_t kp, uint16_t ki, uint16_t kd)
{
    s_pos_pid.kp = (float)kp / 100.0f;
    s_pos_pid.ki = (float)ki / 100.0f;
    s_pos_pid.kd = (float)kd / 100.0f;
}

/**
 * @brief 设置力矩环PID参数
 */
void PID_SetForceParams(uint16_t kp, uint16_t ki, uint16_t kd)
{
    s_force_pid.kp = (float)kp / 100.0f;
    s_force_pid.ki = (float)ki / 100.0f;
    s_force_pid.kd = (float)kd / 100.0f;
}

/**
 * @brief 位置环PID计算 (1kHz)
 */
int16_t PID_PositionCalc(uint16_t target, uint16_t actual)
{
    float error = (float)target - (float)actual;
    float output = PID_CalcIncremental(&s_pos_pid, error);

    return (int16_t)output;
}

/**
 * @brief 力矩环PID计算 (500Hz)
 */
int16_t PID_ForceCalc(uint16_t target, uint16_t actual)
{
    float error = (float)target - (float)actual;
    float output = PID_CalcIncremental(&s_force_pid, error);

    return (int16_t)output;
}

/**
 * @brief 重置PID状态
 */
void PID_Reset(void)
{
    s_pos_pid.err = 0;
    s_pos_pid.err_last = 0;
    s_pos_pid.err_prev = 0;
    s_pos_pid.output = 0;

    s_force_pid.err = 0;
    s_force_pid.err_last = 0;
    s_force_pid.err_prev = 0;
    s_force_pid.output = 0;
}
