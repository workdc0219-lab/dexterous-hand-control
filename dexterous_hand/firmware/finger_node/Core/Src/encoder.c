/**
 * @file    encoder.c
 * @brief   编码器读取实现
 * @details TIM2编码器模式 (PA0/PA1)
 */

#include "encoder.h"

/* ──────────────── 私有变量 ──────────────── */
static TIM_HandleTypeDef htim_encoder;
static int32_t s_total_count = 0;
static int16_t s_last_count = 0;

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief 初始化编码器
 */
void Encoder_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    /* 使能时钟 */
    __HAL_RCC_TIM2_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    /* PA0, PA1 编码器输入 */
    gpio.Pin = GPIO_PIN_0 | GPIO_PIN_1;
    gpio.Mode = GPIO_MODE_INPUT;
    gpio.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &gpio);

    /* TIM2 编码器模式配置 */
    htim_encoder.Instance = TIM2;
    htim_encoder.Init.Prescaler = 0;
    htim_encoder.Init.CounterMode = TIM_COUNTERMODE_UP;
    htim_encoder.Init.Period = 0xFFFF;
    htim_encoder.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    htim_encoder.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;

    /* 编码器模式: 双边沿计数 */
    TIM_Encoder_InitTypeDef encoder_config = {0};
    encoder_config.EncoderMode = TIM_ENCODERMODE_TI12;
    encoder_config.IC1Polarity = TIM_ICPOLARITY_RISING;
    encoder_config.IC1Selection = TIM_ICSELECTION_DIRECTTI;
    encoder_config.IC1Prescaler = TIM_ICPSC_DIV1;
    encoder_config.IC1Filter = 0x0F;
    encoder_config.IC2Polarity = TIM_ICPOLARITY_RISING;
    encoder_config.IC2Selection = TIM_ICSELECTION_DIRECTTI;
    encoder_config.IC2Prescaler = TIM_ICPSC_DIV1;
    encoder_config.IC2Filter = 0x0F;

    HAL_TIM_Encoder_Init(&htim_encoder, &encoder_config);

    /* 启动编码器 */
    HAL_TIM_Encoder_Start(&htim_encoder, TIM_CHANNEL_ALL);

    /* 初始计数值 */
    __HAL_TIM_SET_COUNTER(&htim_encoder, 0x8000);
    s_last_count = 0x8000;
    s_total_count = 0;
}

/**
 * @brief 获取编码器计数值
 */
int16_t Encoder_GetCount(void)
{
    int16_t current = (int16_t)__HAL_TIM_GET_COUNTER(&htim_encoder);
    int16_t delta = current - s_last_count;

    s_total_count += delta;
    s_last_count = current;

    return (int16_t)s_total_count;
}

/**
 * @brief 获取角度值
 */
uint16_t Encoder_GetAngle(void)
{
    int16_t count = Encoder_GetCount();

    /* 转换为角度 (×10) */
    int32_t angle = (int32_t)(count * ENCODER_ANGLE_SCALE);

    /* 限幅 */
    if (angle < 0) angle = 0;
    if (angle > 1800) angle = 1800;

    return (uint16_t)angle;
}

/**
 * @brief 编码器计数清零
 */
void Encoder_Reset(void)
{
    __HAL_TIM_SET_COUNTER(&htim_encoder, 0x8000);
    s_last_count = 0x8000;
    s_total_count = 0;
}
