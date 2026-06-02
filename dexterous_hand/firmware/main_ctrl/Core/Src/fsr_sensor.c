/**
 * @file    fsr_sensor.c
 * @brief   FSR力传感器采集实现
 * @details ADC1 + DMA扫描5通道，滑动窗口均值滤波
 */

#include "fsr_sensor.h"
#include <string.h>

/* ──────────────── 私有变量 ──────────────── */
static ADC_HandleTypeDef hadc1;
static DMA_HandleTypeDef hdma_adc1;

/* ADC通道表 (对应PA0,PA1,PA5,PA6,PA4) */
static const uint32_t g_adc_channels[FSR_CHANNEL_COUNT] = {
    ADC_CHANNEL_0,  /* PA0 - 拇指 */
    ADC_CHANNEL_1,  /* PA1 - 食指 */
    ADC_CHANNEL_5,  /* PA5 - 中指 */
    ADC_CHANNEL_6,  /* PA6 - 无名指 */
    ADC_CHANNEL_4,  /* PA4 - 小指 */
};

/* ADC通道排序 (Rank) */
static const uint8_t g_adc_rank[FSR_CHANNEL_COUNT] = {
    ADC_REGULAR_RANK_1,
    ADC_REGULAR_RANK_2,
    ADC_REGULAR_RANK_3,
    ADC_REGULAR_RANK_4,
    ADC_REGULAR_RANK_5,
};

/* DMA接收缓冲区 */
static uint16_t g_adc_raw[FSR_CHANNEL_COUNT] = {0};

/* 滑动窗口滤波 */
static uint16_t g_filter_buf[FSR_CHANNEL_COUNT][FSR_FILTER_WINDOW] = {0};
static uint8_t  g_filter_idx[FSR_CHANNEL_COUNT] = {0};
static uint32_t g_filter_sum[FSR_CHANNEL_COUNT] = {0};
static uint8_t  g_filter_count[FSR_CHANNEL_COUNT] = {0};

/* 标定参数 */
static float g_calib_slope[FSR_CHANNEL_COUNT] = {1.0f, 1.0f, 1.0f, 1.0f, 1.0f};
static float g_calib_offset[FSR_CHANNEL_COUNT] = {0.0f, 0.0f, 0.0f, 0.0f, 0.0f};

/* 滤波后的值 */
static uint16_t g_filtered[FSR_CHANNEL_COUNT] = {0};

/* ──────────────── 私有函数声明 ──────────────── */
static void FSR_ADC_GPIO_Init(void);
static void FSR_ADC_DMA_Init(void);
static uint16_t FSR_ApplyFilter(uint8_t channel, uint16_t new_val);

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief  初始化ADC1 + DMA，5通道扫描
 */
HAL_StatusTypeDef FSR_Init(void)
{
    FSR_ADC_GPIO_Init();
    FSR_ADC_DMA_Init();

    __HAL_RCC_ADC1_CLK_ENABLE();

    hadc1.Instance = ADC1;
    hadc1.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
    hadc1.Init.Resolution = ADC_RESOLUTION_12B;
    hadc1.Init.ScanConvMode = ENABLE;
    hadc1.Init.ContinuousConvMode = DISABLE;
    hadc1.Init.DiscontinuousConvMode = DISABLE;
    hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc1.Init.NbrOfConversion = FSR_CHANNEL_COUNT;
    hadc1.Init.DMAContinuousRequests = ENABLE;
    hadc1.Init.EOCSelection = ADC_EOC_SEQ_CONV;

    if (HAL_ADC_Init(&hadc1) != HAL_OK) {
        return HAL_ERROR;
    }

    /* 配置5个通道 */
    ADC_ChannelConfTypeDef ch = {0};
    ch.SamplingTime = ADC_SAMPLETIME_84CYCLES;

    for (int i = 0; i < FSR_CHANNEL_COUNT; i++) {
        ch.Channel = g_adc_channels[i];
        ch.Rank = g_adc_rank[i];
        if (HAL_ADC_ConfigChannel(&hadc1, &ch) != HAL_OK) {
            return HAL_ERROR;
        }
    }

    return HAL_OK;
}

/**
 * @brief  初始化ADC GPIO引脚
 */
static void FSR_ADC_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Mode = GPIO_MODE_ANALOG;
    gpio.Pull = GPIO_NOPULL;

    /* PA0, PA1, PA4, PA5, PA6 */
    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_4 |
               GPIO_PIN_5 | GPIO_PIN_6;
    HAL_GPIO_Init(GPIOA, &gpio);
}

/**
 * @brief  初始化ADC DMA
 */
static void FSR_ADC_DMA_Init(void)
{
    __HAL_RCC_DMA2_CLK_ENABLE();

    hdma_adc1.Instance = DMA2_Stream0;
    hdma_adc1.Init.Channel = DMA_CHANNEL_0;
    hdma_adc1.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_adc1.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_adc1.Init.MemInc = DMA_MINC_ENABLE;
    hdma_adc1.Init.PeriphDataAlignment = DMA_PDATAALIGN_HALFWORD;
    hdma_adc1.Init.MemDataAlignment = DMA_MDATAALIGN_HALFWORD;
    hdma_adc1.Init.Mode = DMA_CIRCULAR;
    hdma_adc1.Init.Priority = DMA_PRIORITY_HIGH;
    hdma_adc1.Init.FIFOMode = DMA_FIFOMODE_DISABLE;

    HAL_DMA_Init(&hdma_adc1);
    __HAL_LINKDMA(&hadc1, DMA_Handle, hdma_adc1);

    HAL_NVIC_SetPriority(DMA2_Stream0_IRQn, 2, 0);
    HAL_NVIC_EnableIRQ(DMA2_Stream0_IRQn);
}

/**
 * @brief  启动ADC转换
 */
HAL_StatusTypeDef FSR_StartConversion(void)
{
    return HAL_ADC_Start_DMA(&hadc1, (uint32_t *)g_adc_raw, FSR_CHANNEL_COUNT);
}

/**
 * @brief  获取ADC原始值（滤波后）
 */
uint16_t FSR_GetRawValue(uint8_t finger)
{
    if (finger >= FSR_CHANNEL_COUNT) return 0;
    return g_filtered[finger];
}

/**
 * @brief  获取归一化力值 (N)
 */
float FSR_GetForce(uint8_t finger)
{
    if (finger >= FSR_CHANNEL_COUNT) return 0.0f;

    uint16_t raw = g_filtered[finger];
    float force = g_calib_slope[finger] * (float)raw + g_calib_offset[finger];

    if (force < 0.0f) force = 0.0f;
    return force;
}

/**
 * @brief  标定FSR传感器
 */
void FSR_Calibrate(uint8_t finger, uint16_t adc_ref, float force_ref)
{
    if (finger >= FSR_CHANNEL_COUNT) return;
    if (adc_ref == 0) return;

    /* 线性标定: force = slope * adc + offset */
    /* 假设零点为0N，通过参考点计算斜率 */
    g_calib_slope[finger] = force_ref / (float)adc_ref;
    g_calib_offset[finger] = 0.0f;
}

/**
 * @brief  过载检测
 */
bool FSR_IsOverload(uint8_t finger)
{
    return (FSR_GetForce(finger) >= FSR_OVERLOAD_N);
}

/**
 * @brief  滑动窗口均值滤波
 */
static uint16_t FSR_ApplyFilter(uint8_t channel, uint16_t new_val)
{
    /* 移除旧值 */
    if (g_filter_count[channel] >= FSR_FILTER_WINDOW) {
        g_filter_sum[channel] -= g_filter_buf[channel][g_filter_idx[channel]];
    } else {
        g_filter_count[channel]++;
    }

    /* 添加新值 */
    g_filter_buf[channel][g_filter_idx[channel]] = new_val;
    g_filter_sum[channel] += new_val;
    g_filter_idx[channel] = (g_filter_idx[channel] + 1) % FSR_FILTER_WINDOW;

    return (uint16_t)(g_filter_sum[channel] / g_filter_count[channel]);
}

/**
 * @brief  DMA转换完成回调 - 更新滤波值
 */
void FSR_DMACompleteCallback(void)
{
    for (int i = 0; i < FSR_CHANNEL_COUNT; i++) {
        g_filtered[i] = FSR_ApplyFilter(i, g_adc_raw[i]);
    }
}

/**
 * @brief  DMA2 Stream0中断处理
 */
void DMA2_Stream0_IRQHandler(void)
{
    HAL_DMA_IRQHandler(&hdma_adc1);
}

/**
 * @brief  ADC DMA转换完成回调
 */
void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc)
{
    if (hadc->Instance == ADC1) {
        FSR_DMACompleteCallback();
    }
}
