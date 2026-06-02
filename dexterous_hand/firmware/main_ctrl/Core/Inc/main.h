/**
 * @file    main.h
 * @brief   灵巧手主控板主头文件
 * @details 包含所有模块头文件，定义系统状态结构体和主循环周期
 */

#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* 模块头文件 */
#include "can_protocol.h"
#include "uart_comm.h"
#include "motor_ctrl.h"
#include "fsr_sensor.h"
#include "pid_ctrl.h"
#include "safety.h"

/* ──────────────── 系统参数 ──────────────── */
#define MAIN_LOOP_PERIOD_MS     10      /**< 主循环周期 10ms */
#define FINGER_COUNT            5       /**< 手指数量 */

/* ──────────────── 手指索引 ──────────────── */
typedef enum {
    FINGER_THUMB  = 0,  /**< 拇指 */
    FINGER_INDEX  = 1,  /**< 食指 */
    FINGER_MIDDLE = 2,  /**< 中指 */
    FINGER_RING   = 3,  /**< 无名指 */
    FINGER_PINKY  = 4,  /**< 小指 */
} FingerIndex_t;

/* ──────────────── 系统状态结构体 ──────────────── */
typedef struct {
    uint16_t target_angles[FINGER_COUNT];   /**< 目标角度 (×10度) */
    uint16_t current_angles[FINGER_COUNT];  /**< 当前角度 (×10度) */
    uint16_t force_values[FINGER_COUNT];    /**< 力传感器值 (×100 N) */
    CtrlMode_t control_mode;                /**< 控制模式 */
    uint8_t  system_status;                 /**< 系统状态位 (SYS_STATUS_xxx) */
    ErrorCode_t error_code;                 /**< 当前错误码 */
    uint32_t heartbeat_counter;             /**< 心跳计数器 */
    bool     node_online[FINGER_COUNT];     /**< 各节点在线状态 */
} SystemState_t;

/* 全局系统状态 */
extern SystemState_t g_sys;

/* ──────────────── 函数声明 ──────────────── */
void SystemClock_Config(void);
void Error_Handler(void);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
