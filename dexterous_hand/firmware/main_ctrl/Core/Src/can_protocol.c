/**
 * @file    can_protocol.c
 * @brief   CAN协议栈实现 - 主控板CAN通信
 */

#include "can_protocol.h"
#include <string.h>

/* ──────────────── 私有变量 ──────────────── */
static CAN_HandleTypeDef hcan1;
static uint8_t g_rx_seq = 0;                    /**< 接收序列号 */

/* 接收环形缓冲区 */
#define CAN_RX_BUF_SIZE  16
static CanFrame_t g_rx_buf[CAN_RX_BUF_SIZE];
static volatile uint8_t g_rx_head = 0;
static volatile uint8_t g_rx_tail = 0;

/* 命令回调表 */
static CAN_RxCmdCallback_t g_cmd_callbacks[256] = {0};

/* ──────────────── 私有函数声明 ──────────────── */
static void CAN_FilterConfig(void);
static void CAN_GPIO_Init(void);

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief  初始化CAN1外设，配置波特率1Mbps和过滤器
 */
HAL_StatusTypeDef CAN_Init(void)
{
    CAN_GPIO_Init();

    hcan1.Instance = CAN1;
    hcan1.Init.Prescaler = 3;                  /* APB1=42MHz, 42/(3*(1+9+4))=1MHz */
    hcan1.Init.Mode = CAN_MODE_NORMAL;
    hcan1.Init.SyncJumpWidth = CAN_SJW_1TQ;
    hcan1.Init.TimeSeg1 = CAN_BS1_9TQ;
    hcan1.Init.TimeSeg2 = CAN_BS2_4TQ;
    hcan1.Init.TimeTriggeredMode = DISABLE;
    hcan1.Init.AutoBusOff = ENABLE;
    hcan1.Init.AutoWakeUp = DISABLE;
    hcan1.Init.AutoRetransmission = ENABLE;
    hcan1.Init.ReceiveFifoLocked = DISABLE;
    hcan1.Init.TransmitFifoPriority = DISABLE;

    if (HAL_CAN_Init(&hcan1) != HAL_OK) {
        return HAL_ERROR;
    }

    CAN_FilterConfig();

    /* 启用CAN */
    if (HAL_CAN_Start(&hcan1) != HAL_OK) {
        return HAL_ERROR;
    }

    /* 使能接收中断 */
    HAL_CAN_ActivateNotification(&hcan1, CAN_IT_RX_FIFO0_MSG_PENDING);

    return HAL_OK;
}

/**
 * @brief  配置CAN过滤器，接收所有帧
 */
static void CAN_FilterConfig(void)
{
    CAN_FilterTypeDef filter;
    filter.FilterBank = 0;
    filter.FilterMode = CAN_FILTERMODE_IDMASK;
    filter.FilterScale = CAN_FILTERSCALE_32BIT;
    filter.FilterIdHigh = 0x0000;
    filter.FilterIdLow = 0x0000;
    filter.FilterMaskIdHigh = 0x0000;
    filter.FilterMaskIdLow = 0x0000;
    filter.FilterFIFOAssignment = CAN_RX_FIFO0;
    filter.FilterActivation = ENABLE;
    HAL_CAN_ConfigFilter(&hcan1, &filter);
}

/**
 * @brief  初始化CAN1的GPIO引脚 (PB8=RX, PB9=TX)
 */
static void CAN_GPIO_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_CAN1_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    gpio.Pin = GPIO_PIN_8 | GPIO_PIN_9;
    gpio.Mode = GPIO_MODE_AF_PP;
    gpio.Pull = GPIO_NOPULL;
    gpio.Speed = GPIO_SPEED_FREQ_HIGH;
    gpio.Alternate = GPIO_AF9_CAN1;
    HAL_GPIO_Init(GPIOB, &gpio);
}

/**
 * @brief  发送CAN帧
 */
HAL_StatusTypeDef CAN_SendFrame(const CanFrame_t *frame)
{
    CAN_TxHeaderTypeDef header;
    uint32_t mailbox;

    header.StdId = frame->id;
    header.ExtId = 0;
    header.IDE = CAN_ID_STD;
    header.RTR = CAN_RTR_DATA;
    header.DLC = CAN_DLC;

    /* 组装数据: [CMD][SEQ][DATA...] */
    uint8_t tx_data[8];
    tx_data[0] = frame->cmd;
    tx_data[1] = frame->seq;
    memcpy(&tx_data[2], frame->data, 6);

    /* 等待空邮箱 */
    uint32_t timeout = 100;
    while (HAL_CAN_GetTxMailboxesFreeLevel(&hcan1) == 0) {
        if (--timeout == 0) return HAL_BUSY;
    }

    return HAL_CAN_AddTxMessage(&hcan1, &header, tx_data, &mailbox);
}

/**
 * @brief  接收CAN帧（从环形缓冲区读取）
 */
HAL_StatusTypeDef CAN_ReceiveFrame(CanFrame_t *frame)
{
    if (g_rx_head == g_rx_tail) {
        return HAL_BUSY;  /* 缓冲区空 */
    }

    memcpy(frame, &g_rx_buf[g_rx_tail], sizeof(CanFrame_t));
    g_rx_tail = (g_rx_tail + 1) % CAN_RX_BUF_SIZE;

    return HAL_OK;
}

/**
 * @brief  发送角度指令到指定节点
 */
HAL_StatusTypeDef CAN_SendAngleCmd(NodeId_t node, uint16_t angle, uint16_t speed)
{
    CanFrame_t frame;
    CmdSetAngle_t cmd;

    cmd.angle = angle;
    cmd.speed = speed;
    memset(cmd.reserved, 0, sizeof(cmd.reserved));

    can_frame_build(&frame, 1, node, NODE_ID_MASTER,
                    CMD_SET_ANGLE, 0, (const uint8_t *)&cmd, sizeof(cmd));

    return CAN_SendFrame(&frame);
}

/**
 * @brief  发送心跳帧
 */
HAL_StatusTypeDef CAN_SendHeartbeat(void)
{
    CanFrame_t frame;
    CmdHeartbeat_t hb;

    extern SystemState_t g_sys;
    hb.status = g_sys.system_status;
    memset(hb.reserved, 0, sizeof(hb.reserved));

    can_frame_build(&frame, 3, NODE_ID_BROADCAST, NODE_ID_MASTER,
                    CMD_HEARTBEAT, 0, (const uint8_t *)&hb, sizeof(hb));

    return CAN_SendFrame(&frame);
}

/**
 * @brief  发送紧急停止指令到所有节点
 */
HAL_StatusTypeDef CAN_SendEmergencyStop(uint8_t reason)
{
    CanFrame_t frame;
    CmdEmergencyStop_t cmd;

    cmd.reason = reason;
    memset(cmd.reserved, 0, sizeof(cmd.reserved));

    can_frame_build(&frame, 0, NODE_ID_BROADCAST, NODE_ID_MASTER,
                    CMD_EMERGENCY_STOP, 0, (const uint8_t *)&cmd, sizeof(cmd));

    return CAN_SendFrame(&frame);
}

/**
 * @brief  广播所有手指角度（逐个发送）
 */
HAL_StatusTypeDef CAN_BroadcastAngle(const uint16_t angles[5], uint16_t speed)
{
    NodeId_t nodes[5] = {
        NODE_ID_THUMB, NODE_ID_INDEX, NODE_ID_MIDDLE,
        NODE_ID_RING, NODE_ID_PINKY
    };

    for (int i = 0; i < 5; i++) {
        HAL_StatusTypeDef ret = CAN_SendAngleCmd(nodes[i], angles[i], speed);
        if (ret != HAL_OK) return ret;
    }

    return HAL_OK;
}

/**
 * @brief  注册命令回调
 */
void CAN_RegisterCallback(CanCmd_t cmd, CAN_RxCmdCallback_t cb)
{
    /* 边界检查 */
    if ((uint8_t)cmd < 256) {
        g_cmd_callbacks[(uint8_t)cmd] = cb;
    }
}

/**
 * @brief  CAN1 RX0中断回调 - 将帧存入环形缓冲区
 */
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
    CAN_RxHeaderTypeDef header;
    uint8_t data[8];

    if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &header, data) != HAL_OK) {
        return;
    }

    uint8_t next_head = (g_rx_head + 1) % CAN_RX_BUF_SIZE;
    if (next_head == g_rx_tail) {
        return;  /* 缓冲区满，丢弃 */
    }

    can_frame_parse(&g_rx_buf[g_rx_head], header.StdId, data);
    g_rx_head = next_head;
}

/**
 * @brief  处理接收缓冲区中的帧，分发到回调
 */
void CAN_ProcessRxBuffer(void)
{
    CanFrame_t frame;

    while (CAN_ReceiveFrame(&frame) == HAL_OK) {
        NodeId_t src = (NodeId_t)CAN_GET_SRC(frame.id);

        if (g_cmd_callbacks[frame.cmd] != NULL) {
            g_cmd_callbacks[frame.cmd](src, &frame);
        }
    }
}
