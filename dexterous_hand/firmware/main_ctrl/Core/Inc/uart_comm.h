/**
 * @file    uart_comm.h
 * @brief   与AIpro的UART通信接口
 * @details 帧格式: [0xAA][5×angle(2B each)][CRC8][0x55] = 13字节
 *          angle为小端uint16_t，×10度精度
 */

#ifndef __UART_COMM_H
#define __UART_COMM_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include <stdint.h>
#include <stdbool.h>

/* 帧格式常量 */
#define UART_FRAME_HEADER       0xAA
#define UART_FRAME_TAIL         0x55
#define UART_FRAME_SIZE         13      /* 1+10+1+1 = 13字节 */
#define UART_ANGLE_COUNT        5

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化USART2 (PA2=TX, PA3=RX) + DMA接收
 * @retval HAL状态
 */
HAL_StatusTypeDef UART_Comm_Init(void);

/**
 * @brief  发送5个手指角度到AIpro
 * @param  angles: 角度数组 (×10度, 小端)
 * @retval HAL状态
 */
HAL_StatusTypeDef UART_SendAngles(const uint16_t angles[5]);

/**
 * @brief  检查是否收到完整帧
 * @retval true=有新数据
 */
bool UART_IsDataReady(void);

/**
 * @brief  处理接收数据，校验CRC并解析角度
 * @param  angles: 输出角度数组
 * @retval HAL_OK=数据有效, HAL_ERROR=CRC错误或帧无效
 */
HAL_StatusTypeDef UART_ProcessRxData(uint16_t angles[5]);

/**
 * @brief  USART2空闲中断处理（在USART2_IRQHandler中调用）
 */
void UART_IdleIRQHandler(void);

/**
 * @brief  计算CRC8校验和
 * @param  data: 数据指针
 * @param  len: 数据长度
 * @retval CRC8值
 */
uint8_t UART_CalcCRC8(const uint8_t *data, uint8_t len);

#ifdef __cplusplus
}
#endif

#endif /* __UART_COMM_H */
