/**
 * @file    uart_comm.c
 * @brief   与AIpro的UART通信实现
 * @details 使用USART2，DMA+空闲中断接收，帧格式13字节
 */

#include "uart_comm.h"
#include <string.h>

/* ──────────────── 私有变量 ──────────────── */
static UART_HandleTypeDef huart2;
static DMA_HandleTypeDef hdma_usart2_rx;

/* 接收双缓冲 */
static uint8_t g_rx_dma_buf[UART_FRAME_SIZE * 2];  /**< DMA接收缓冲区 */
static uint8_t g_rx_frame[UART_FRAME_SIZE];         /**< 当前帧缓冲 */
static volatile bool g_frame_ready = false;          /**< 帧就绪标志 */
static volatile uint16_t g_rx_pos = 0;               /**< 接收位置 */

/* ──────────────── 私有函数 ──────────────── */
static void UART_GPIO_Init(void);
static void UART_DMA_Init(void);

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief  初始化USART2 + DMA接收
 */
HAL_StatusTypeDef UART_Comm_Init(void)
{
    UART_GPIO_Init();
    UART_DMA_Init();

    huart2.Instance = USART2;
    huart2.Init.BaudRate = 115200;
    huart2.Init.WordLength = UART_WORDLENGTH_8B;
    huart2.Init.StopBits = UART_STOPBITS_1;
    huart2.Init.Parity = UART_PARITY_NONE;
    huart2.Init.Mode = UART_MODE_TX_RX;
    huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart2.Init.OverSampling = UART_OVERSAMPLING_16;

    if (HAL_UART_Init(&huart2) != HAL_OK) {
        return HAL_ERROR;
    }

    /* 使能空闲中断 */
    __HAL_UART_ENABLE_IT(&huart2, UART_IT_IDLE);

    /* 启动DMA接收 */
    HAL_UART_Receive_DMA(&huart2, g_rx_dma_buf, sizeof(g_rx_dma_buf));

    return HAL_OK;
}

/**
 * @brief  初始化USART2 GPIO (PA2=TX, PA3=RX)
 */
static void UART_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_USART2_CLK_ENABLE();
    __HAL_RCC_GPIOA_CLK_ENABLE();

    gpio.Pin = GPIO_PIN_2 | GPIO_PIN_3;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_PULLUP;
    gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    gpio.Alternate = GPIO_AF7_USART2;
    HAL_GPIO_Init(GPIOA, &gpio);
}

/**
 * @brief  初始化USART2 DMA接收
 */
static void UART_DMA_Init(void)
{
    __HAL_RCC_DMA1_CLK_ENABLE();

    hdma_usart2_rx.Instance = DMA1_Stream5;
    hdma_usart2_rx.Init.Channel = DMA_CHANNEL_4;
    hdma_usart2_rx.Init.Direction = DMA_PERIPH_TO_MEMORY;
    hdma_usart2_rx.Init.PeriphInc = DMA_PINC_DISABLE;
    hdma_usart2_rx.Init.MemInc = DMA_MINC_ENABLE;
    hdma_usart2_rx.Init.PeriphDataAlignment = DMA_PDATAALIGN_BYTE;
    hdma_usart2_rx.Init.MemDataAlignment = DMA_MDATAALIGN_BYTE;
    hdma_usart2_rx.Init.Mode = DMA_CIRCULAR;
    hdma_usart2_rx.Init.Priority = DMA_PRIORITY_HIGH;
    hdma_usart2_rx.Init.FIFOMode = DMA_FIFOMODE_DISABLE;

    HAL_DMA_Init(&hdma_usart2_rx);
    __HAL_LINKDMA(&huart2, hdmarx, hdma_usart2_rx);

    /* DMA中断 */
    HAL_NVIC_SetPriority(DMA1_Stream5_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(DMA1_Stream5_IRQn);
}

/**
 * @brief  发送5个手指角度
 * @details 帧格式: [0xAA][angle0_L][angle0_H]...[angle4_L][angle4_H][CRC8][0x55]
 */
HAL_StatusTypeDef UART_SendAngles(const uint16_t angles[5])
{
    uint8_t tx_buf[UART_FRAME_SIZE];
    uint8_t idx = 0;

    tx_buf[idx++] = UART_FRAME_HEADER;

    /* 5个角度，小端 */
    for (int i = 0; i < UART_ANGLE_COUNT; i++) {
        tx_buf[idx++] = (uint8_t)(angles[i] & 0xFF);
        tx_buf[idx++] = (uint8_t)((angles[i] >> 8) & 0xFF);
    }

    /* CRC8校验 (对header+angle部分) */
    tx_buf[idx++] = UART_CalcCRC8(tx_buf, idx);
    tx_buf[idx++] = UART_FRAME_TAIL;

    return HAL_UART_Transmit(&huart2, tx_buf, UART_FRAME_SIZE, 10);
}

/**
 * @brief  检查是否收到完整帧
 */
bool UART_IsDataReady(void)
{
    return g_frame_ready;
}

/**
 * @brief  处理接收数据，校验CRC并解析角度
 */
HAL_StatusTypeDef UART_ProcessRxData(uint16_t angles[5])
{
    if (!g_frame_ready) {
        return HAL_BUSY;
    }

    g_frame_ready = false;

    /* 校验帧头帧尾 */
    if (g_rx_frame[0] != UART_FRAME_HEADER ||
        g_rx_frame[UART_FRAME_SIZE - 1] != UART_FRAME_TAIL) {
        return HAL_ERROR;
    }

    /* 校验CRC8 */
    uint8_t crc_calc = UART_CalcCRC8(g_rx_frame, UART_FRAME_SIZE - 2);
    uint8_t crc_recv = g_rx_frame[UART_FRAME_SIZE - 2];
    if (crc_calc != crc_recv) {
        return HAL_ERROR;
    }

    /* 解析角度 */
    for (int i = 0; i < UART_ANGLE_COUNT; i++) {
        uint8_t lo = g_rx_frame[1 + i * 2];
        uint8_t hi = g_rx_frame[2 + i * 2];
        angles[i] = (uint16_t)((hi << 8) | lo);
    }

    return HAL_OK;
}

/**
 * @brief  计算CRC8 (多项式0x07, 初始值0x00)
 */
uint8_t UART_CalcCRC8(const uint8_t *data, uint8_t len)
{
    uint8_t crc = 0x00;
    for (uint8_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t j = 0; j < 8; j++) {
            if (crc & 0x80) {
                crc = (crc << 1) ^ 0x07;
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

/**
 * @brief  USART2空闲中断处理
 * @details 从DMA缓冲区中提取完整帧
 */
void UART_IdleIRQHandler(void)
{
    if (__HAL_UART_GET_FLAG(&huart2, UART_FLAG_IDLE)) {
        __HAL_UART_CLEAR_IDLEFLAG(&huart2);

        /* 计算DMA已接收的数据量 */
        uint16_t dma_remaining = __HAL_DMA_GET_COUNTER(huart2.hdmarx);
        uint16_t dma_total = sizeof(g_rx_dma_buf);
        uint16_t rx_count = dma_total - dma_remaining;

        /* 在DMA缓冲区中查找帧头 */
        for (uint16_t i = 0; i + UART_FRAME_SIZE <= rx_count; i++) {
            if (g_rx_dma_buf[i] == UART_FRAME_HEADER) {
                /* 检查帧尾 */
                if (g_rx_dma_buf[i + UART_FRAME_SIZE - 1] == UART_FRAME_TAIL) {
                    memcpy(g_rx_frame, &g_rx_dma_buf[i], UART_FRAME_SIZE);
                    g_frame_ready = true;
                    break;
                }
            }
        }

        /* 重置DMA */
        HAL_UART_AbortReceive(&huart2);
        HAL_UART_Receive_DMA(&huart2, g_rx_dma_buf, sizeof(g_rx_dma_buf));
    }
}

/**
 * @brief  DMA1 Stream5中断处理
 */
void DMA1_Stream5_IRQHandler(void)
{
    HAL_DMA_IRQHandler(&hdma_usart2_rx);
}
