/**
 * @file    pid_ctrl.c
 * @brief   PID控制器实现
 * @details 增量式PID算法，适用于位置环和力矩环控制
 */

#include "pid_ctrl.h"

/**
 * @brief  初始化PID控制器
 */
void PID_Init(PID_t *pid, float kp, float ki, float kd,
              float out_min, float out_max)
{
    pid->Kp = kp;
    pid->Ki = ki;
    pid->Kd = kd;
    pid->out_min = out_min;
    pid->out_max = out_max;
    pid->integral = 0.0f;
    pid->integral_max = out_max * 0.8f;  /* 积分限幅默认为输出上限的80% */
    pid->prev_error = 0.0f;
    pid->prev_error2 = 0.0f;
    pid->output = 0.0f;
}

/**
 * @brief  增量式PID计算
 * @details 增量式PID公式:
 *          Δu = Kp*(e[k]-e[k-1]) + Ki*e[k] + Kd*(e[k]-2*e[k-1]+e[k-2])
 *          u[k] = u[k-1] + Δu
 */
float PID_Compute(PID_t *pid, float setpoint, float measurement)
{
    float error = setpoint - measurement;

    /* 增量计算 */
    float delta = pid->Kp * (error - pid->prev_error)
                + pid->Ki * error
                + pid->Kd * (error - 2.0f * pid->prev_error + pid->prev_error2);

    /* 更新输出 */
    pid->output += delta;

    /* 输出限幅 */
    if (pid->output > pid->out_max) {
        pid->output = pid->out_max;
    } else if (pid->output < pid->out_min) {
        pid->output = pid->out_min;
    }

    /* 积分累积（用于监控，增量式不需要显式积分项） */
    pid->integral += error;
    if (pid->integral > pid->integral_max) {
        pid->integral = pid->integral_max;
    } else if (pid->integral < -pid->integral_max) {
        pid->integral = -pid->integral_max;
    }

    /* 更新历史误差 */
    pid->prev_error2 = pid->prev_error;
    pid->prev_error = error;

    return pid->output;
}

/**
 * @brief  重置PID控制器
 */
void PID_Reset(PID_t *pid)
{
    pid->integral = 0.0f;
    pid->prev_error = 0.0f;
    pid->prev_error2 = 0.0f;
    pid->output = 0.0f;
}

/**
 * @brief  在线修改PID参数
 */
void PID_SetParams(PID_t *pid, float kp, float ki, float kd)
{
    pid->Kp = kp;
    pid->Ki = ki;
    pid->Kd = kd;
}
