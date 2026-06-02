/**
 * @file    safety.c
 * @brief   安全保护模块实现
 * @details 堵转检测、角度限幅、FSR过载、CAN超时、急停
 */

#include "safety.h"
#include "main.h"
#include "motor_ctrl.h"
#include "encoder.h"
#include "fsr_sensor.h"
#include "can_protocol.h"

/* ──────────────── 私有变量 ──────────────── */
static uint32_t s_stall_start_time = 0;
static int16_t s_stall_encoder_start = 0;
static uint8_t s_stall_detected = 0;

static uint32_t s_last_can_time = 0;
static uint8_t s_estop_active = 0;

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 初始化安全模块
 */
void Safety_Init(void)
{
    s_stall_start_time = 0;
    s_stall_encoder_start = 0;
    s_stall_detected = 0;
    s_last_can_time = HAL_GetTick();
    s_estop_active = 0;
}

/**
 * @brief 安全检查（主循环调用）
 */
ErrorCode_t Safety_Check(void)
{
    ErrorCode_t err = ERR_NONE;

    /* 急停状态不检查 */
    if (s_estop_active) {
        return g_finger.error_code;
    }

    /* 1. CAN超时检查 */
    if (Safety_CheckCANTimeout()) {
        err = ERR_COMM_TIMEOUT;
        Safety_EmergencyStop(err);
        return err;
    }

    /* 2. 堵转检测 */
    if (Safety_CheckStall()) {
        err = ERR_STALL;
        Safety_EmergencyStop(err);
        return err;
    }

    /* 3. FSR过载检查 */
    if (Safety_CheckFSROverload()) {
        err = ERR_FSR_OVERLOAD;
        Safety_EmergencyStop(err);
        return err;
    }

    return ERR_NONE;
}

/**
 * @brief 堵转检测
 * @details 编码器不变 + PWM>80% 持续500ms
 */
uint8_t Safety_CheckStall(void)
{
    /* 获取当前PWM (简化: 检查电机是否在驱动) */
    int16_t pwm = 0;  /* TODO: 从Motor模块获取当前PWM */
    int16_t encoder = Encoder_GetCount();

    /* 检查条件: PWM > 80% */
    if (pwm > SAFETY_STALL_PWM || pwm < -SAFETY_STALL_PWM) {
        if (s_stall_start_time == 0) {
            /* 开始计时 */
            s_stall_start_time = HAL_GetTick();
            s_stall_encoder_start = encoder;
            s_stall_detected = 0;
        } else {
            /* 检查编码器是否变化 */
            int16_t delta = encoder - s_stall_encoder_start;
            if (delta < 5 && delta > -5) {
                /* 编码器几乎没动 */
                if ((HAL_GetTick() - s_stall_start_time) >= SAFETY_STALL_TIME_MS) {
                    s_stall_detected = 1;
                    return 1;
                }
            } else {
                /* 编码器有变化，重置 */
                s_stall_start_time = HAL_GetTick();
                s_stall_encoder_start = encoder;
            }
        }
    } else {
        /* PWM低，重置检测 */
        s_stall_start_time = 0;
    }

    return 0;
}

/**
 * @brief 角度限幅
 */
uint16_t Safety_ClampAngle(uint16_t angle)
{
    if (angle < SAFETY_ANGLE_MIN) return SAFETY_ANGLE_MIN;
    if (angle > SAFETY_ANGLE_MAX) return SAFETY_ANGLE_MAX;
    return angle;
}

/**
 * @brief FSR过载检查
 */
uint8_t Safety_CheckFSROverload(void)
{
    uint16_t adc_raw = FSR_GetRawValue();
    return (adc_raw > FSR_OVERLOAD_THRESHOLD) ? 1 : 0;
}

/**
 * @brief CAN超时检查
 */
uint8_t Safety_CheckCANTimeout(void)
{
    if ((HAL_GetTick() - s_last_can_time) > CAN_TIMEOUT_MS) {
        return 1;
    }
    return 0;
}

/**
 * @brief 触发急停
 */
void Safety_EmergencyStop(ErrorCode_t reason)
{
    s_estop_active = 1;
    g_finger.error_code = reason;
    g_finger.sys_status |= SYS_STATUS_ESTOP;

    /* 停止电机 */
    Motor_Stop();
}

/**
 * @brief 更新CAN通信时间戳
 */
void Safety_UpdateCANTimestamp(void)
{
    s_last_can_time = HAL_GetTick();
    g_finger.last_can_time = s_last_can_time;
}
