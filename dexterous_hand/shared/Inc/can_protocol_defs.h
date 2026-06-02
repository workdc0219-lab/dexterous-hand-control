/**
 * @file    can_protocol_defs.h
 * @brief   CAN通信协议定义（主控与手指节点共享）
 * @details 定义CAN帧格式、命令集、节点ID等，主控和节点固件共同包含此文件。
 *
 * 帧格式: CAN 2.0B 标准帧 (11-bit ID), DLC=8
 * ID编码: [优先级(2bit)][目标节点(5bit)][源节点(4bit)]
 * 数据:   [CMD(1B)][SEQ(1B)][DATA(6B)]
 */

#ifndef __CAN_PROTOCOL_DEFS_H
#define __CAN_PROTOCOL_DEFS_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────── 版本 ──────────────── */
#define CAN_PROTOCOL_VERSION        0x01

/* ──────────────── CAN参数 ──────────────── */
#define CAN_BAUDRATE                1000000UL   /* 1 Mbps */
#define CAN_DLC                     8           /* 固定8字节 */
#define CAN_TIMEOUT_MS              500         /* 心跳超时 500ms */
#define CAN_HEARTBEAT_INTERVAL_MS   100         /* 心跳发送间隔 100ms */

/* ──────────────── 节点ID ──────────────── */
typedef enum {
    NODE_ID_MASTER  = 0x00,     /* 主控板 */
    NODE_ID_THUMB   = 0x01,     /* 拇指 */
    NODE_ID_INDEX   = 0x02,     /* 食指 */
    NODE_ID_MIDDLE  = 0x03,     /* 中指 */
    NODE_ID_RING    = 0x04,     /* 无名指 */
    NODE_ID_PINKY   = 0x05,     /* 小指 */
    NODE_ID_BROADCAST = 0x1F,   /* 广播 */
} NodeId_t;

/* ──────────────── CAN ID编码 ──────────────── */
/*
 * ID = [优先级(2bit)][目标节点(5bit)][源节点(4bit)]
 * 优先级: 0=最高, 3=最低
 */
#define CAN_ID_PRIORITY_POS     9
#define CAN_ID_DST_POS          4
#define CAN_ID_SRC_POS          0

#define CAN_ID_PRIORITY_MASK    (0x03 << CAN_ID_PRIORITY_POS)
#define CAN_ID_DST_MASK         (0x1F << CAN_ID_DST_POS)
#define CAN_ID_SRC_MASK         (0x0F << CAN_ID_SRC_POS)

#define CAN_MAKE_ID(priority, dst, src) \
    (((priority) << CAN_ID_PRIORITY_POS) | \
     ((dst) << CAN_ID_DST_POS) | \
     ((src) << CAN_ID_SRC_POS))

#define CAN_GET_PRIORITY(id)    (((id) >> CAN_ID_PRIORITY_POS) & 0x03)
#define CAN_GET_DST(id)         (((id) >> CAN_ID_DST_POS) & 0x1F)
#define CAN_GET_SRC(id)         (((id) >> CAN_ID_SRC_POS) & 0x0F)

/* 常用ID */
#define CAN_ID_MASTER_TO(dst)   CAN_MAKE_ID(1, dst, NODE_ID_MASTER)
#define CAN_ID_NODE_TO_MASTER   CAN_MAKE_ID(2, NODE_ID_MASTER, 0)  /* src由节点填充 */

/* ──────────────── 命令定义 ──────────────── */
typedef enum {
    /* 主→从 */
    CMD_SET_ANGLE       = 0x01,     /* 设置关节角度 */
    CMD_QUERY_FORCE     = 0x02,     /* 查询力传感器 */
    CMD_SET_PID         = 0x03,     /* 设置PID参数 */
    CMD_SET_MODE        = 0x10,     /* 设置控制模式 */
    CMD_SET_TARGET_FORCE= 0x11,     /* 设置目标抓取力 */
    CMD_HEARTBEAT       = 0xFE,     /* 心跳 */
    CMD_EMERGENCY_STOP  = 0xFF,     /* 紧急停止 */

    /* 从→主 */
    CMD_ANGLE_REPORT    = 0x81,     /* 角度回传 */
    CMD_FORCE_REPORT    = 0x82,     /* 力数据回传 */
    CMD_PID_REPORT      = 0x83,     /* PID参数回传 */
    CMD_ESTOP_ACK       = 0x84,     /* 急停确认 */
    CMD_ERROR_REPORT    = 0x85,     /* 错误报告 */
} CanCmd_t;

/* ──────────────── 控制模式 ──────────────── */
typedef enum {
    CTRL_MODE_POSITION  = 0x00,     /* 位置环控制 */
    CTRL_MODE_FORCE     = 0x01,     /* 力矩闭环 */
    CTRL_MODE_AUTO      = 0x02,     /* 自动模式（双模态切换） */
} CtrlMode_t;

/* ──────────────── 错误码 ──────────────── */
typedef enum {
    ERR_NONE            = 0x00,
    ERR_OVERCURRENT     = 0x01,     /* 过流 */
    ERR_STALL           = 0x02,     /* 堵转 */
    ERR_COMM_TIMEOUT    = 0x03,     /* 通信超时 */
    ERR_FSR_OVERLOAD    = 0x04,     /* FSR过载 */
    ERR_ANGLE_LIMIT     = 0x05,     /* 角度超限 */
} ErrorCode_t;

/* ──────────────── 数据帧结构 ──────────────── */

/**
 * @brief CMD_SET_ANGLE (0x01) DATA字段
 * Byte0-1: 目标角度 (uint16, 0.1度精度, 0~1800=0~180°)
 * Byte2-3: 运动速度 (uint16, 0.1度/秒)
 * Byte4-5: 保留
 */
typedef struct __attribute__((packed)) {
    uint16_t angle;         /* 目标角度 × 10 */
    uint16_t speed;         /* 运动速度 × 10 */
    uint8_t  reserved[2];
} CmdSetAngle_t;

/**
 * @brief CMD_QUERY_FORCE (0x02) DATA字段
 * Byte0: 手指ID
 * Byte1-5: 保留
 */
typedef struct __attribute__((packed)) {
    uint8_t  finger_id;
    uint8_t  reserved[5];
} CmdQueryForce_t;

/**
 * @brief CMD_SET_PID (0x03) DATA字段
 * Byte0-1: Kp (uint16, ×100)
 * Byte2-3: Ki (uint16, ×100)
 * Byte4-5: Kd (uint16, ×100)
 */
typedef struct __attribute__((packed)) {
    uint16_t kp;
    uint16_t ki;
    uint16_t kd;
} CmdSetPid_t;

/**
 * @brief CMD_SET_MODE (0x10) DATA字段
 * Byte0: 控制模式 (CtrlMode_t)
 * Byte1-5: 保留
 */
typedef struct __attribute__((packed)) {
    uint8_t  mode;
    uint8_t  reserved[5];
} CmdSetMode_t;

/**
 * @brief CMD_HEARTBEAT (0xFE) DATA字段
 * Byte0: 系统状态 (bit0=运行, bit1=急停, bit2=通信错误)
 * Byte1-5: 保留
 */
typedef struct __attribute__((packed)) {
    uint8_t  status;
    uint8_t  reserved[5];
} CmdHeartbeat_t;

/**
 * @brief CMD_EMERGENCY_STOP (0xFF) DATA字段
 * Byte0: 停机原因 (ErrorCode_t)
 * Byte1-5: 保留
 */
typedef struct __attribute__((packed)) {
    uint8_t  reason;
    uint8_t  reserved[5];
} CmdEmergencyStop_t;

/**
 * @brief CMD_ANGLE_REPORT (0x81) DATA字段
 * Byte0-1: 当前角度 (uint16, ×10)
 * Byte2-3: 编码器原始值 (uint16)
 * Byte4: 状态标志
 * Byte5: 保留
 */
typedef struct __attribute__((packed)) {
    uint16_t angle;
    uint16_t encoder;
    uint8_t  status;
    uint8_t  reserved;
} RptAngle_t;

/**
 * @brief CMD_FORCE_REPORT (0x82) DATA字段
 * Byte0-1: 力值 (uint16, ×100, 单位N)
 * Byte2-3: ADC原始值 (uint16)
 * Byte4: 状态标志 (bit0=接触)
 * Byte5: 保留
 */
typedef struct __attribute__((packed)) {
    uint16_t force;
    uint16_t adc_raw;
    uint8_t  status;
    uint8_t  reserved;
} RptForce_t;

/* ──────────────── 通用CAN帧 ──────────────── */
typedef struct {
    uint32_t id;
    uint8_t  cmd;
    uint8_t  seq;
    uint8_t  data[6];
} CanFrame_t;

/* ──────────────── 安全参数 ──────────────── */
#define ANGLE_MIN_DEG       0       /* 最小角度 (度) */
#define ANGLE_MAX_DEG       180     /* 最大角度 (度) */
#define FORCE_MAX_N         20.0f   /* 最大力 (N) */
#define STALL_TIMEOUT_MS    500     /* 堵转检测超时 */
#define STALL_CURRENT_MA    1500    /* 堵转电流阈值 */

/* ──────────────── 系统状态位 ──────────────── */
#define SYS_STATUS_RUNNING      (1 << 0)
#define SYS_STATUS_ESTOP        (1 << 1)
#define SYS_STATUS_COMM_ERR     (1 << 2)
#define SYS_STATUS_STALL        (1 << 3)
#define SYS_STATUS_FORCE_OK     (1 << 4)

/* ──────────────── 工具函数 ──────────────── */

/**
 * @brief 构建CAN帧
 */
static inline void can_frame_build(CanFrame_t *frame, uint8_t priority,
                                    uint8_t dst, uint8_t src,
                                    uint8_t cmd, uint8_t seq,
                                    const uint8_t *data, uint8_t len)
{
    frame->id = CAN_MAKE_ID(priority, dst, src);
    frame->cmd = cmd;
    frame->seq = seq;
    for (uint8_t i = 0; i < 6 && i < len; i++) {
        frame->data[i] = data[i];
    }
    for (uint8_t i = len; i < 6; i++) {
        frame->data[i] = 0x00;
    }
}

/**
 * @brief 从CAN硬件帧解析为CanFrame_t
 */
static inline void can_frame_parse(CanFrame_t *frame, uint32_t id,
                                    const uint8_t *data)
{
    frame->id = id;
    frame->cmd = data[0];
    frame->seq = data[1];
    for (uint8_t i = 0; i < 6; i++) {
        frame->data[i] = data[i + 2];
    }
}

#ifdef __cplusplus
}
#endif

#endif /* __CAN_PROTOCOL_DEFS_H */
