/**
 * @file    can_protocol.h
 * @brief   CAN协议栈 - 主控板CAN通信接口
 */

#ifndef __CAN_PROTOCOL_H
#define __CAN_PROTOCOL_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f4xx_hal.h"
#include "can_protocol_defs.h"

/* ──────────────── 接收回调函数类型 ──────────────── */
typedef void (*CAN_RxCmdCallback_t)(NodeId_t src, const CanFrame_t *frame);

/* ──────────────── 函数声明 ──────────────── */

/**
 * @brief  初始化CAN1，配置过滤器
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_Init(void);

/**
 * @brief  发送CAN帧
 * @param  frame: 待发送的CAN帧
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_SendFrame(const CanFrame_t *frame);

/**
 * @brief  接收CAN帧（从接收缓冲区读取）
 * @param  frame: 接收缓冲区
 * @retval HAL_OK=有新帧, HAL_BUSY=无新帧
 */
HAL_StatusTypeDef CAN_ReceiveFrame(CanFrame_t *frame);

/**
 * @brief  发送角度指令到指定节点
 * @param  node: 目标节点ID
 * @param  angle: 目标角度 (×10度)
 * @param  speed: 运动速度 (×10度/秒)
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_SendAngleCmd(NodeId_t node, uint16_t angle, uint16_t speed);

/**
 * @brief  发送心跳帧
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_SendHeartbeat(void);

/**
 * @brief  发送紧急停止指令
 * @param  reason: 停机原因 (ErrorCode_t)
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_SendEmergencyStop(uint8_t reason);

/**
 * @brief  广播所有手指角度
 * @param  angles: 5个手指角度数组 (×10度)
 * @param  speed: 统一运动速度 (×10度/秒)
 * @retval HAL状态
 */
HAL_StatusTypeDef CAN_BroadcastAngle(const uint16_t angles[5], uint16_t speed);

/**
 * @brief  注册命令接收回调
 * @param  cmd: 命令类型
 * @param  cb: 回调函数
 */
void CAN_RegisterCallback(CanCmd_t cmd, CAN_RxCmdCallback_t cb);

/**
 * @brief  CAN接收中断处理（在CAN1_RX0_IRQHandler中调用）
 */
void CAN_IRQHandler(void);

/**
 * @brief  从接收FIFO读取并分发帧（在主循环中调用）
 */
void CAN_ProcessRxBuffer(void);

#ifdef __cplusplus
}
#endif

#endif /* __CAN_PROTOCOL_H */
