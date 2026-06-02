/**
 * @file    encoder.h
 * @brief   编码器读取头文件
 * @details TIM2编码器模式 (PA0/PA1)
 */

#ifndef __ENCODER_H
#define __ENCODER_H

#include "stm32f1xx_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 参数定义 ──────────────── */
#define ENCODER_PPR             1024    /* 编码器每转脉冲数 */
#define ENCODER_GEAR_RATIO      1.0f    /* 减速比 */
#define ENCODER_ANGLE_SCALE     (3600.0f / (ENCODER_PPR * 4.0f * ENCODER_GEAR_RATIO))

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化编码器
 * @note  配置TIM2编码器模式 (PA0/PA1)
 */
void Encoder_Init(void);

/**
 * @brief 获取编码器计数值
 * @return 当前计数 (int16_t)
 */
int16_t Encoder_GetCount(void);

/**
 * @brief 获取角度值
 * @return 角度 (×10, 0.1度精度)
 */
uint16_t Encoder_GetAngle(void);

/**
 * @brief 编码器计数清零
 */
void Encoder_Reset(void);

#ifdef __cplusplus
}
#endif

#endif /* __ENCODER_H */
