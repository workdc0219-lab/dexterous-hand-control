/**
 * @file    fsr_sensor.c
 * @brief   FSR力传感器采集实现
 * @details ADC采集 + 滑动窗口滤波
 */

#include "fsr_sensor.h"

/* ──────────────── 私有变量 ──────────────── */
static ADC_HandleTypeDef hadc;
static uint16_t s_filter_buf[FSR_FILTER_SIZE];
static uint8_t s_filter_idx = 0;
static uint8_t s_filter_count = 0;
static uint16_t s_filtered_value = 0;

/* ──────────────── 私有函数 ──────────────── */

/**
 * @brief ADC硬件初始化
 */
static void FSR_ADC_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* 使能时钟 */
    __HAL_RCC_ADC1_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    /* PA4 模拟输入 (避免与编码器PA0冲突) */
    gpio.Pin = GPIO_PIN_4;
    gpio.Mode = GPIO_MODE_ANALOG;
    HAL_GPIO_Init(GPIOA, &gpio);

    /* ADC配置 */
    hadc.Instance = ADC1;
    hadc.Init.ScanConvMode = DISABLE;
    hadc.Init.ContinuousConvMode = DISABLE;
    hadc.Init.DiscontinuousConvMode = DISABLE;
    hadc.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc.Init.NbrOfConversion = 1;
    HAL_ADC_Init(&hadc);

    /* ADC校准 */
    HAL_ADCEx_Calibration_Start(&hadc);
}

/**
 * @brief 读取单次ADC值
 */
static uint16_t FSR_ReadADC(void)
{
    ADC_ChannelConfTypeDef ch = {0};

    ch.Channel = FSR_ADC_CHANNEL;
    ch.Rank = ADC_REGULAR_RANK_1;
    ch.SamplingTime = ADC_SAMPLETIME_239CYCLES_5;

    HAL_ADC_ConfigChannel(&hadc, &ch);
    HAL_ADC_Start(&hadc);
    HAL_ADC_PollForConversion(&hadc, 10);

    uint16_t value = 0;
    if (HAL_ADC_GetState(&hadc) == HAL_ADC_STATE_EOC_REG) {
        value = (uint16_t)HAL_ADC_GetValue(&hadc);
    }

    HAL_ADC_Stop(&hadc);
    return value;
}

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 初始化FSR传感器
 */
void FSR_Init(void)
{
    FSR_ADC_Init();

    /* 清空滤波缓冲区 */
    for (uint8_t i = 0; i < FSR_FILTER_SIZE; i++) {
        s_filter_buf[i] = 0;
    }
    s_filter_idx = 0;
    s_filter_count = 0;
    s_filtered_value = 0;
}

/**
 * @brief ADC采样（定时调用，建议1kHz）
 */
void FSR_Sample(void)
{
    uint16_t raw = FSR_ReadADC();

    /* 写入滑动窗口 */
    s_filter_buf[s_filter_idx] = raw;
    s_filter_idx = (s_filter_idx + 1) % FSR_FILTER_SIZE;

    if (s_filter_count < FSR_FILTER_SIZE) {
        s_filter_count++;
    }

    /* 计算滑动窗口均值 */
    uint32_t sum = 0;
    for (uint8_t i = 0; i < s_filter_count; i++) {
        sum += s_filter_buf[i];
    }
    s_filtered_value = (uint16_t)(sum / s_filter_count);
}

/**
 * @brief 获取ADC原始值（滤波后）
 */
uint16_t FSR_GetRawValue(void)
{
    return s_filtered_value;
}

/**
 * @brief 获取力值
 * @note  简单线性映射，实际需要标定
 */
uint16_t FSR_GetForce(void)
{
    /* ADC -> 力值的简单映射
     * 假设: 0~4095 ADC -> 0~20N
     * force_N = adc * 20.0 / 4095
     * 返回值 ×100 */
    uint32_t force = (uint32_t)s_filtered_value * 2000 / 4095;
    return (uint16_t)force;
}

/**
 * @brief 判断是否有接触
 */
uint8_t FSR_IsContact(void)
{
    return (s_filtered_value > FSR_CONTACT_THRESHOLD) ? 1 : 0;
}
