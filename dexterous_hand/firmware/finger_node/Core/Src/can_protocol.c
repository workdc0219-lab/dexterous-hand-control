/**
 * @file    can_protocol.c
 * @brief   CAN协议栈实现（节点侧）
 * @details CAN初始化、过滤器配置、收发、上报
 */

#include "can_protocol.h"
#include "main.h"
#include <string.h>

/* ──────────────── 私有变量 ──────────────── */
static CAN_HandleTypeDef hcan;
static NodeId_t s_self_id = NODE_ID_INDEX;
static uint8_t s_seq = 0;

/* 接收缓冲区 */
#define CAN_RX_BUF_SIZE     16
static CanFrame_t s_rx_buf[CAN_RX_BUF_SIZE];
static volatile uint8_t s_rx_head = 0;
static volatile uint8_t s_rx_tail = 0;

/* ──────────────── 私有函数 ──────────────── */

/**
 * @brief 配置CAN过滤器，只接收发给本节点和广播帧
 */
static void CAN_ConfigureFilter(void)
{
    CAN_FilterTypeDef filter;

    /* 过滤器0: 接收目标为本节点的帧 */
    filter.FilterBank = 0;
    filter.FilterMode = CAN_FILTERMODE_IDMASK;
    filter.FilterScale = CAN_FILTERSCALE_32BIT;

    /* ID: 目标节点 = self_id */
    uint32_t id = CAN_MAKE_ID(0, s_self_id, 0) << 5;
    uint32_t mask = CAN_ID_DST_MASK << 5;

    filter.FilterIdHigh = (id >> 16) & 0xFFFF;
    filter.FilterIdLow = id & 0xFFFF;
    filter.FilterMaskIdHigh = (mask >> 16) & 0xFFFF;
    filter.FilterMaskIdLow = mask & 0xFFFF;

    filter.FilterFIFOAssignment = CAN_FILTER_FIFO0;
    filter.FilterActivation = ENABLE;
    filter.SlaveStartFilterBank = 14;

    HAL_CAN_ConfigFilter(&hcan, &filter);

    /* 过滤器1: 接收广播帧 */
    CAN_FilterTypeDef filter_bc;
    filter_bc.FilterBank = 1;
    filter_bc.FilterMode = CAN_FILTERMODE_IDMASK;
    filter_bc.FilterScale = CAN_FILTERSCALE_32BIT;

    uint32_t bc_id = CAN_MAKE_ID(0, NODE_ID_BROADCAST, 0) << 5;
    uint32_t bc_mask = CAN_ID_DST_MASK << 5;

    filter_bc.FilterIdHigh = (bc_id >> 16) & 0xFFFF;
    filter_bc.FilterIdLow = bc_id & 0xFFFF;
    filter_bc.FilterMaskIdHigh = (bc_mask >> 16) & 0xFFFF;
    filter_bc.FilterMaskIdLow = bc_mask & 0xFFFF;

    filter_bc.FilterFIFOAssignment = CAN_FILTER_FIFO0;
    filter_bc.FilterActivation = ENABLE;
    filter_bc.SlaveStartFilterBank = 14;

    HAL_CAN_ConfigFilter(&hcan, &filter_bc);
}

/**
 * @brief 处理接收到的CAN帧
 * @param frame 接收到的帧
 */
static void CAN_ProcessFrame(CanFrame_t *frame)
{
    uint8_t cmd = frame->cmd;

    switch (cmd) {
    case CMD_SET_ANGLE: {
        /* 设置目标角度 */
        CmdSetAngle_t *p = (CmdSetAngle_t *)frame->data;
        g_finger.target_angle = p->angle;
        g_finger.speed = p->speed;
        Safety_UpdateCANTimestamp();
        break;
    }

    case CMD_QUERY_FORCE: {
        /* 查询力传感器，立即上报 */
        CAN_ReportForce(g_finger.force, g_finger.adc_raw, g_finger.contact);
        Safety_UpdateCANTimestamp();
        break;
    }

    case CMD_SET_PID: {
        /* 设置PID参数 */
        CmdSetPid_t *p = (CmdSetPid_t *)frame->data;
        if (g_finger.ctrl_mode == CTRL_MODE_POSITION) {
            PID_SetPositionParams(p->kp, p->ki, p->kd);
        } else {
            PID_SetForceParams(p->kp, p->ki, p->kd);
        }
        Safety_UpdateCANTimestamp();
        break;
    }

    case CMD_SET_MODE: {
        /* 设置控制模式 */
        CmdSetMode_t *p = (CmdSetMode_t *)frame->data;
        g_finger.ctrl_mode = (CtrlMode_t)p->mode;
        PID_Reset();
        Safety_UpdateCANTimestamp();
        break;
    }

    case CMD_SET_TARGET_FORCE: {
        /* 设置目标抓取力 */
        uint16_t force = (frame->data[1] << 8) | frame->data[0];
        g_finger.target_force = force;
        Safety_UpdateCANTimestamp();
        break;
    }

    case CMD_HEARTBEAT: {
        /* 心跳，更新时间戳 */
        Safety_UpdateCANTimestamp();

        /* 如果处于急停状态，尝试恢复 */
        if (Safety_IsEStopActive()) {
            Safety_TryRecover();
        }
        break;
    }

    case CMD_EMERGENCY_STOP: {
        /* 急停 */
        CmdEmergencyStop_t *p = (CmdEmergencyStop_t *)frame->data;
        Safety_EmergencyStop((ErrorCode_t)p->reason);
        CAN_SendEstoAck();
        break;
    }

    default:
        break;
    }
}

/* ──────────────── 公共函数实现 ──────────────── */

/**
 * @brief 初始化CAN外设
 */
void CAN_Protocol_Init(NodeId_t self_id)
{
    s_self_id = self_id;

    /* CAN外设初始化 */
    hcan.Instance = CAN1;
    hcan.Init.Prescaler = 2;             /* APB1=36MHz, 36MHz/2/18=1Mbps */
    hcan.Init.Mode = CAN_MODE_NORMAL;
    hcan.Init.SyncJumpWidth = CAN_SJW_1TQ;
    hcan.Init.TimeSeg1 = CAN_BS1_15TQ;
    hcan.Init.TimeSeg2 = CAN_BS2_2TQ;
    hcan.Init.TimeTriggeredMode = DISABLE;
    hcan.Init.AutoBusOff = ENABLE;
    hcan.Init.AutoWakeUp = DISABLE;
    hcan.Init.AutoRetransmission = ENABLE;
    hcan.Init.ReceiveFifoLocked = DISABLE;
    hcan.Init.TransmitFifoPriority = DISABLE;

    HAL_CAN_Init(&hcan);

    /* 配置过滤器 */
    CAN_ConfigureFilter();

    /* 启动CAN */
    HAL_CAN_Start(&hcan);

    /* 使能接收中断 */
    HAL_CAN_ActivateNotification(&hcan, CAN_IT_RX_FIFO0_MSG_PENDING);
}

/**
 * @brief 发送CAN帧
 */
HAL_StatusTypeDef CAN_SendFrame(CanFrame_t *frame)
{
    CAN_TxHeaderTypeDef header;
    uint32_t mailbox;

    header.StdId = frame->id & 0x7FF;
    header.ExtId = 0;
    header.RTR = CAN_RTR_DATA;
    header.IDE = CAN_ID_STD;
    header.DLC = CAN_DLC;

    /* 组装数据: [CMD][SEQ][DATA...] */
    uint8_t tx_data[8];
    tx_data[0] = frame->cmd;
    tx_data[1] = frame->seq;
    memcpy(&tx_data[2], frame->data, 6);

    return HAL_CAN_AddTxMessage(&hcan, &header, tx_data, &mailbox);
}

/**
 * @brief 接收CAN帧（从缓冲区读取）
 */
uint8_t CAN_ReceiveFrame(CanFrame_t *frame)
{
    if (s_rx_head == s_rx_tail) {
        return 0;   /* 缓冲区空 */
    }

    *frame = s_rx_buf[s_rx_tail];
    s_rx_tail = (s_rx_tail + 1) % CAN_RX_BUF_SIZE;

    return 1;
}

/**
 * @brief 上报角度数据
 */
void CAN_ReportAngle(uint16_t angle, uint16_t encoder)
{
    CanFrame_t frame;
    uint8_t data[6] = {0};

    RptAngle_t *rpt = (RptAngle_t *)data;
    rpt->angle = angle;
    rpt->encoder = encoder;
    rpt->status = g_finger.sys_status;

    can_frame_build(&frame, 2, NODE_ID_MASTER, s_self_id,
                    CMD_ANGLE_REPORT, s_seq++, data, 6);

    CAN_SendFrame(&frame);
}

/**
 * @brief 上报力传感器数据
 */
void CAN_ReportForce(uint16_t force, uint16_t adc_raw, uint8_t contact)
{
    CanFrame_t frame;
    uint8_t data[6] = {0};

    RptForce_t *rpt = (RptForce_t *)data;
    rpt->force = force;
    rpt->adc_raw = adc_raw;
    rpt->status = contact ? 0x01 : 0x00;

    can_frame_build(&frame, 2, NODE_ID_MASTER, s_self_id,
                    CMD_FORCE_REPORT, s_seq++, data, 6);

    CAN_SendFrame(&frame);
}

/**
 * @brief 上报错误
 */
void CAN_ReportError(ErrorCode_t error)
{
    CanFrame_t frame;
    uint8_t data[6] = {0};

    data[0] = (uint8_t)error;

    can_frame_build(&frame, 0, NODE_ID_MASTER, s_self_id,
                    CMD_ERROR_REPORT, s_seq++, data, 6);

    CAN_SendFrame(&frame);
}

/**
 * @brief 发送急停确认
 */
void CAN_SendEstoAck(void)
{
    CanFrame_t frame;
    uint8_t data[6] = {0};

    data[0] = (uint8_t)g_finger.error_code;

    can_frame_build(&frame, 0, NODE_ID_MASTER, s_self_id,
                    CMD_ESTOP_ACK, s_seq++, data, 6);

    CAN_SendFrame(&frame);
}

/**
 * @brief CAN接收处理（主循环调用）
 */
void CAN_ProcessRx(void)
{
    CanFrame_t frame;

    while (CAN_ReceiveFrame(&frame)) {
        CAN_ProcessFrame(&frame);
    }
}

/**
 * @brief CAN接收中断回调
 */
void CAN_RxCallback(CAN_HandleTypeDef *hcan_ptr)
{
    CAN_RxHeaderTypeDef header;
    uint8_t data[8];

    if (HAL_CAN_GetRxMessage(hcan_ptr, CAN_RX_FIFO0, &header, data) == HAL_OK) {
        uint8_t next = (s_rx_head + 1) % CAN_RX_BUF_SIZE;
        if (next != s_rx_tail) {
            /* 解析帧 */
            can_frame_parse(&s_rx_buf[s_rx_head], header.StdId, data);
            s_rx_head = next;
        }
    }
}

/**
 * @brief HAL CAN接收回调
 */
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan_ptr)
{
    CAN_RxCallback(hcan_ptr);
}
