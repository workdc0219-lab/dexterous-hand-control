/**
 * @file    safety.h
 * @brief   安全保护机制接口
 * @details 急停按钮(PC13)、过流检测(PB8 EXTI)、堵转检测、通信超时
 *          安全状态机: NORMAL -> SAFE_STOP -> RECOVERING -> NORMAL
 */

#ifndef __SAFETY_H
#define __SAFETY_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include "can_protocol_defs.h"
#include <stdint.h>
#include <stdbool.h>

/* ──────────────── 安全状态枚举 ──────────────── */
typedef enum {
    SAFETY_NORMAL = 0,      /**< 正常运行 */
    SAFETY_SAFE_STOP,       /**< 安全停机 */
    SAFETY_RECOVERING,      /**< 恢复中 */
} SafetyState_t;

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化安全模块：急停按钮(PC13)、过流检测(PB8 EXTI)
 * @retval HAL状态
 */
HAL_StatusTypeDef Safety_Init(void);

/**
 * @brief  检测电机堵转
 * @param  motor: 电机编号
 * @param  current_ma: 当前电流 (mA)
 * @param  encoder: 编码器值
 * @retval true=检测到堵转
 */
bool Safety_CheckStall(uint8_t motor, uint16_t current_ma, uint16_t encoder);

/**
 * @brief  CAN心跳超时检测
 * @retval true=通信超时
 */
bool Safety_CheckCommTimeout(void);

/**
 * @brief  角度限幅（就地修改）
 * @param  angle: 角度指针 (×10度)
 */
void Safety_CheckAngleLimit(uint16_t *angle);

/**
 * @brief  触发紧急停止
 * @param  reason: 停机原因 (ErrorCode_t)
 */
void Safety_TriggerEStop(uint8_t reason);

/**
 * @brief  从安全状态恢复
 * @retval HAL_OK=恢复成功, HAL_ERROR=条件不满足
 */
HAL_StatusTypeDef Safety_Recover(void);

/**
 * @brief  获取当前安全状态
 * @retval SafetyState_t
 */
SafetyState_t Safety_GetState(void);

/**
 * @brief  定期安全检查（在定时器中断中调用）
 */
void Safety_PeriodicCheck(void);

/**
 * @brief  更新心跳时间戳（收到节点心跳时调用）
 * @param  node: 节点ID
 */
void Safety_UpdateHeartbeat(NodeId_t node);

/**
 * @brief  PC13急停按钮中断回调
 */
void Safety_EStopButtonCallback(void);

/**
 * @brief  PB8过流检测中断回调
 */
void Safety_OvercurrentCallback(void);

#ifdef __cplusplus
}
#endif

#endif /* __SAFETY_H */
