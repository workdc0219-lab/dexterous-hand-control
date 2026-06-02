/**
 * @file    fsr_sensor.h
 * @brief   FSR力传感器采集头文件
 * @details ADC采集 + 滑动窗口滤波
 */

#ifndef __FSR_SENSOR_H
#define __FSR_SENSOR_H

#include "stm32f1xx_hal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 参数定义 ──────────────── */
#define FSR_ADC_CHANNEL         ADC_CHANNEL_4   /* PA4 (避免与编码器PA0冲突) */
#define FSR_FILTER_SIZE         8               /* 滑动窗口大小 */
#define FSR_CONTACT_THRESHOLD   100             /* 接触判定阈值 (ADC值) */
#define FSR_OVERLOAD_THRESHOLD  3800            /* 过载阈值 (ADC值) */

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化FSR传感器
 * @note  配置ADC (PA0)
 */
void FSR_Init(void);

/**
 * @brief 获取ADC原始值（滤波后）
 * @return ADC值 (0~4095)
 */
uint16_t FSR_GetRawValue(void);

/**
 * @brief 获取力值
 * @return 力值 (×100, 单位N)
 */
uint16_t FSR_GetForce(void);

/**
 * @brief 判断是否有接触
 * @return 1=有接触, 0=无接触
 */
uint8_t FSR_IsContact(void);

/**
 * @brief ADC采样（定时调用）
 */
void FSR_Sample(void);

#ifdef __cplusplus
}
#endif

#endif /* __FSR_SENSOR_H */
