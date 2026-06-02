/**
 * @file    safety.h
 * @brief   安全保护模块头文件
 * @details 堵转检测、角度限幅、FSR过载、CAN超时、急停
 */

#ifndef __SAFETY_H
#define __SAFETY_H

#include "stm32f1xx_hal.h"
#include "can_protocol_defs.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 安全参数 ──────────────── */
#define SAFETY_ANGLE_MIN        (ANGLE_MIN_DEG * 10)    /* 最小角度 (×10) */
#define SAFETY_ANGLE_MAX        (ANGLE_MAX_DEG * 10)    /* 最大角度 (×10) */
#define SAFETY_STALL_PWM        800                     /* 堵转PWM阈值 (80%) */
#define SAFETY_STALL_TIME_MS    500                     /* 堵转检测时间 */

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化安全模块
 */
void Safety_Init(void);

/**
 * @brief 安全检查（主循环调用）
 * @return 错误码, ERR_NONE=正常
 */
ErrorCode_t Safety_Check(void);

/**
 * @brief 堵转检测
 * @return 1=检测到堵转, 0=正常
 */
uint8_t Safety_CheckStall(void);

/**
 * @brief 角度限幅检查
 * @param angle 目标角度 (×10)
 * @return 限幅后的角度
 */
uint16_t Safety_ClampAngle(uint16_t angle);

/**
 * @brief FSR过载检查
 * @return 1=过载, 0=正常
 */
uint8_t Safety_CheckFSROverload(void);

/**
 * @brief CAN超时检查
 * @return 1=超时, 0=正常
 */
uint8_t Safety_CheckCANTimeout(void);

/**
 * @brief 触发急停
 * @param reason 停机原因
 */
void Safety_EmergencyStop(ErrorCode_t reason);

/**
 * @brief 更新CAN通信时间戳
 */
void Safety_UpdateCANTimestamp(void);

#ifdef __cplusplus
}
#endif

#endif /* __SAFETY_H */
