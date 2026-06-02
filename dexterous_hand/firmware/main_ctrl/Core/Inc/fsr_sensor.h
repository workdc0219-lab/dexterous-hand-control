/**
 * @file    fsr_sensor.h
 * @brief   FSR力传感器采集接口
 * @details 使用ADC1 + DMA，5通道扫描采集
 *          ADC引脚: PA0(拇指), PA1(食指), PA5(中指), PA6(无名指), PA4(小指)
 *          滑动窗口均值滤波（窗口大小10）
 */

#ifndef __FSR_SENSOR_H
#define __FSR_SENSOR_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* ──────────────── 参数定义 ──────────────── */
#define FSR_CHANNEL_COUNT       5       /**< FSR通道数量 */
#define FSR_FILTER_WINDOW       10      /**< 滑动窗口大小 */
#define FSR_ADC_MAX             4095    /**< ADC最大值 (12bit) */
#define FSR_ADC_VREF            3.3f    /**< 参考电压 */
#define FSR_OVERLOAD_N          20.0f   /**< 过载阈值 (N) */

/* 手指索引（与ADC通道对应） */
#define FSR_THUMB               0       /**< PA0 - ADC_CH0 */
#define FSR_INDEX               1       /**< PA1 - ADC_CH1 */
#define FSR_MIDDLE              2       /**< PA5 - ADC_CH5 */
#define FSR_RING                3       /**< PA6 - ADC_CH6 */
#define FSR_PINKY               4       /**< PA4 - ADC_CH4 */

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化ADC1 + DMA，5通道扫描
 * @retval HAL状态
 */
HAL_StatusTypeDef FSR_Init(void);

/**
 * @brief  启动ADC转换
 * @retval HAL状态
 */
HAL_StatusTypeDef FSR_StartConversion(void);

/**
 * @brief  获取ADC原始值（滤波后）
 * @param  finger: 手指索引 (0~4)
 * @retval ADC原始值 (0~4095)
 */
uint16_t FSR_GetRawValue(uint8_t finger);

/**
 * @brief  获取归一化力值
 * @param  finger: 手指索引 (0~4)
 * @retval 力值 (单位N)
 */
float FSR_GetForce(uint8_t finger);

/**
 * @brief  标定FSR传感器
 * @param  finger: 手指索引
 * @param  adc_ref: 标定ADC参考值
 * @param  force_ref: 标定力值参考 (N)
 */
void FSR_Calibrate(uint8_t finger, uint16_t adc_ref, float force_ref);

/**
 * @brief  过载检测
 * @param  finger: 手指索引
 * @retval true=过载
 */
bool FSR_IsOverload(uint8_t finger);

/**
 * @brief  DMA转换完成回调
 */
void FSR_DMACompleteCallback(void);

#ifdef __cplusplus
}
#endif

#endif /* __FSR_SENSOR_H */
