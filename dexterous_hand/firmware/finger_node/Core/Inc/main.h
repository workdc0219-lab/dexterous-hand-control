/**
 * @file    main.h
 * @brief   手指节点主头文件
 * @details 包含所有模块头文件，定义节点状态结构体和配置
 */

#ifndef __MAIN_H
#define __MAIN_H

#include "stm32f1xx_hal.h"
#include <stdint.h>

/* 协议定义 */
#include "can_protocol_defs.h"

/* 模块头文件 */
#include "can_protocol.h"
#include "motor_ctrl.h"
#include "encoder.h"
#include "fsr_sensor.h"
#include "pid_ctrl.h"
#include "safety.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 节点ID配置 ──────────────── */
/**
 * 通过编译时常量配置本节点ID
 * 可选值: NODE_ID_THUMB(1), NODE_ID_INDEX(2), NODE_ID_MIDDLE(3),
 *         NODE_ID_RING(4), NODE_ID_PINKY(5)
 * 编译时通过 -DNODE_ID=0x02 传入
 */
#ifndef NODE_ID
#define NODE_ID     NODE_ID_INDEX   /* 默认食指 */
#endif

/* ──────────────── 版本信息 ──────────────── */
#define FW_VERSION_MAJOR    1
#define FW_VERSION_MINOR    0
#define FW_VERSION_PATCH    0

/* ──────────────── 系统时钟 ──────────────── */
#define SYSCLK_FREQ_HZ     72000000UL
#define APB1_TIM_FREQ_HZ    72000000UL

/* ──────────────── 节点状态结构体 ──────────────── */
/**
 * @brief 手指节点全局状态
 */
typedef struct {
    /* 传感器数据 */
    uint16_t    angle;          /* 当前角度 (×10, 0.1度精度) */
    uint16_t    encoder_raw;    /* 编码器原始计数 */
    uint16_t    force;          /* 当前力值 (×100, 单位N) */
    uint16_t    adc_raw;        /* ADC原始值 */
    uint8_t     contact;        /* 接触标志 */

    /* 控制参数 */
    uint16_t    target_angle;   /* 目标角度 (×10) */
    uint16_t    target_force;   /* 目标力 (×100) */
    CtrlMode_t  ctrl_mode;      /* 控制模式 */
    uint16_t    speed;          /* 运动速度 (×10) */

    /* PID参数 */
    float       pid_kp;
    float       pid_ki;
    float       pid_kd;

    /* 系统状态 */
    uint8_t     sys_status;     /* 系统状态位 */
    ErrorCode_t error_code;     /* 错误码 */
    uint32_t    last_can_time;  /* 上次CAN通信时间 */
    uint32_t    tick;           /* 系统tick */
} FingerState_t;

/* 全局状态变量声明 */
extern FingerState_t g_finger;

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 系统时钟配置
 */
void SystemClock_Config(void);

/**
 * @brief 获取系统tick (ms)
 */
uint32_t HAL_GetTick(void);

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */
