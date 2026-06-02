/**
 * @file    can_protocol.h
 * @brief   CAN协议栈头文件（节点侧）
 * @details CAN初始化、收发、上报函数声明
 */

#ifndef __CAN_PROTOCOL_H
#define __CAN_PROTOCOL_H

#include "stm32f1xx_hal.h"
#include "can_protocol_defs.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief 初始化CAN外设
 * @param self_id 本节点ID
 */
void CAN_Protocol_Init(NodeId_t self_id);

/**
 * @brief 发送CAN帧
 * @param frame 帧结构体指针
 * @return HAL状态
 */
HAL_StatusTypeDef CAN_SendFrame(CanFrame_t *frame);

/**
 * @brief 接收CAN帧（从接收缓冲区读取）
 * @param frame 帧结构体指针
 * @return 1=有数据, 0=无数据
 */
uint8_t CAN_ReceiveFrame(CanFrame_t *frame);

/**
 * @brief 上报角度数据
 * @param angle 当前角度 (×10)
 * @param encoder 编码器原始值
 */
void CAN_ReportAngle(uint16_t angle, uint16_t encoder);

/**
 * @brief 上报力传感器数据
 * @param force 力值 (×100, N)
 * @param adc_raw ADC原始值
 * @param contact 接触标志
 */
void CAN_ReportForce(uint16_t force, uint16_t adc_raw, uint8_t contact);

/**
 * @brief 上报错误
 * @param error 错误码
 */
void CAN_ReportError(ErrorCode_t error);

/**
 * @brief 发送急停确认
 */
void CAN_SendEstoAck(void);

/**
 * @brief CAN接收处理（在主循环中调用）
 */
void CAN_ProcessRx(void);

/**
 * @brief CAN中断回调
 * @param hcan CAN句柄
 */
void CAN_RxCallback(CAN_HandleTypeDef *hcan);

#ifdef __cplusplus
}
#endif

#endif /* __CAN_PROTOCOL_H */
