/**
 * @file    test_can.c
 * @brief   CAN协议单元测试
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "test_helpers.h"

/* ──────────────── CAN 协议定义 (模拟) ──────────────── */

/* 节点ID */
typedef enum {
    NODE_ID_MASTER  = 0x00,
    NODE_ID_THUMB   = 0x01,
    NODE_ID_INDEX   = 0x02,
    NODE_ID_MIDDLE  = 0x03,
    NODE_ID_RING    = 0x04,
    NODE_ID_PINKY   = 0x05,
    NODE_ID_BROADCAST = 0x1F,
} NodeId_t;

/* 命令定义 */
typedef enum {
    CMD_SET_ANGLE       = 0x01,
    CMD_QUERY_FORCE     = 0x02,
    CMD_SET_PID         = 0x03,
    CMD_SET_MODE        = 0x10,
    CMD_HEARTBEAT       = 0xFE,
    CMD_EMERGENCY_STOP  = 0xFF,
    CMD_ANGLE_REPORT    = 0x81,
    CMD_FORCE_REPORT    = 0x82,
} CanCmd_t;

/* CAN帧结构 */
typedef struct {
    uint32_t id;
    uint8_t cmd;
    uint8_t seq;
    uint8_t data[6];
} CanFrame_t;

/* CAN ID编码 */
#define CAN_ID_PRIORITY_POS     9
#define CAN_ID_DST_POS          4
#define CAN_ID_SRC_POS          0

#define CAN_MAKE_ID(priority, dst, src) \
    (((priority) << CAN_ID_PRIORITY_POS) | \
     ((dst) << CAN_ID_DST_POS) | \
     ((src) << CAN_ID_SRC_POS))

#define CAN_GET_PRIORITY(id)    (((id) >> CAN_ID_PRIORITY_POS) & 0x03)
#define CAN_GET_DST(id)         (((id) >> CAN_ID_DST_POS) & 0x1F)
#define CAN_GET_SRC(id)         (((id) >> CAN_ID_SRC_POS) & 0x0F)

/* 工具函数 */
static void can_frame_build(CanFrame_t *frame, uint8_t priority,
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

static void can_frame_parse(CanFrame_t *frame, uint32_t id, const uint8_t *data)
{
    frame->id = id;
    frame->cmd = data[0];
    frame->seq = data[1];
    for (uint8_t i = 0; i < 6; i++) {
        frame->data[i] = data[i + 2];
    }
}

/* 数据帧结构 */
typedef struct __attribute__((packed)) {
    uint16_t angle;
    uint16_t speed;
    uint8_t  reserved[2];
} CmdSetAngle_t;

typedef struct __attribute__((packed)) {
    uint16_t angle;
    uint16_t encoder;
    uint8_t  status;
    uint8_t  reserved;
} RptAngle_t;

/* ──────────────── 测试用例 ──────────────── */

/**
 * @brief 测试CAN ID编码
 */
static void test_can_id_encoding(void)
{
    uint32_t id;

    /* 主控 -> 拇指 */
    id = CAN_MAKE_ID(1, NODE_ID_THUMB, NODE_ID_MASTER);
    TEST_ASSERT_EQUAL(1, CAN_GET_PRIORITY(id), "主控->拇指: 优先级=1");
    TEST_ASSERT_EQUAL(NODE_ID_THUMB, CAN_GET_DST(id), "主控->拇指: 目标=拇指");
    TEST_ASSERT_EQUAL(NODE_ID_MASTER, CAN_GET_SRC(id), "主控->拇指: 源=主控");

    /* 食指 -> 主控 */
    id = CAN_MAKE_ID(2, NODE_ID_MASTER, NODE_ID_INDEX);
    TEST_ASSERT_EQUAL(2, CAN_GET_PRIORITY(id), "食指->主控: 优先级=2");
    TEST_ASSERT_EQUAL(NODE_ID_MASTER, CAN_GET_DST(id), "食指->主控: 目标=主控");
    TEST_ASSERT_EQUAL(NODE_ID_INDEX, CAN_GET_SRC(id), "食指->主控: 源=食指");

    /* 广播 */
    id = CAN_MAKE_ID(1, NODE_ID_BROADCAST, NODE_ID_MASTER);
    TEST_ASSERT_EQUAL(NODE_ID_BROADCAST, CAN_GET_DST(id), "广播: 目标=0x1F");
}

/**
 * @brief 测试CAN帧构建
 */
static void test_can_frame_build(void)
{
    CanFrame_t frame;
    uint8_t data[6] = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06};

    can_frame_build(&frame, 1, NODE_ID_THUMB, NODE_ID_MASTER,
                    CMD_SET_ANGLE, 0, data, 6);

    TEST_ASSERT_EQUAL(CMD_SET_ANGLE, frame.cmd, "帧构建: 命令正确");
    TEST_ASSERT_EQUAL(0, frame.seq, "帧构建: 序列号正确");
    TEST_ASSERT_EQUAL(0x01, frame.data[0], "帧构建: 数据[0]正确");
    TEST_ASSERT_EQUAL(0x06, frame.data[5], "帧构建: 数据[5]正确");
}

/**
 * @brief 测试CAN帧解析
 */
static void test_can_frame_parse(void)
{
    CanFrame_t frame;
    uint8_t raw_data[8] = {CMD_ANGLE_REPORT, 0x05, 0x64, 0x00, 0x10, 0x27, 0x01, 0x00};

    uint32_t id = CAN_MAKE_ID(2, NODE_ID_MASTER, NODE_ID_INDEX);
    can_frame_parse(&frame, id, raw_data);

    TEST_ASSERT_EQUAL(CMD_ANGLE_REPORT, frame.cmd, "帧解析: 命令正确");
    TEST_ASSERT_EQUAL(0x05, frame.seq, "帧解析: 序列号正确");
    TEST_ASSERT_EQUAL(0x64, frame.data[0], "帧解析: 数据[0]正确");
    TEST_ASSERT_EQUAL(0x00, frame.data[1], "帧解析: 数据[1]正确");
}

/**
 * @brief 测试角度指令帧
 */
static void test_angle_command_frame(void)
{
    CanFrame_t frame;
    CmdSetAngle_t cmd;

    cmd.angle = 900;    /* 90度 */
    cmd.speed = 500;    /* 50度/秒 */

    can_frame_build(&frame, 1, NODE_ID_THUMB, NODE_ID_MASTER,
                    CMD_SET_ANGLE, 0, (uint8_t*)&cmd, sizeof(cmd));

    /* 解析验证 */
    CmdSetAngle_t *parsed = (CmdSetAngle_t*)frame.data;
    TEST_ASSERT_EQUAL(900, parsed->angle, "角度指令: 角度=900");
    TEST_ASSERT_EQUAL(500, parsed->speed, "角度指令: 速度=500");
}

/**
 * @brief 测试角度上报帧
 */
static void test_angle_report_frame(void)
{
    CanFrame_t frame;
    RptAngle_t rpt;

    rpt.angle = 450;     /* 45度 */
    rpt.encoder = 1234;
    rpt.status = 0x01;

    can_frame_build(&frame, 2, NODE_ID_MASTER, NODE_ID_INDEX,
                    CMD_ANGLE_REPORT, 0, (uint8_t*)&rpt, sizeof(rpt));

    /* 解析验证 */
    RptAngle_t *parsed = (RptAngle_t*)frame.data;
    TEST_ASSERT_EQUAL(450, parsed->angle, "角度上报: 角度=450");
    TEST_ASSERT_EQUAL(1234, parsed->encoder, "角度上报: 编码器=1234");
    TEST_ASSERT_EQUAL(0x01, parsed->status, "角度上报: 状态=0x01");
}

/**
 * @brief 测试多节点通信
 */
static void test_multi_node_comm(void)
{
    NodeId_t nodes[] = {NODE_ID_THUMB, NODE_ID_INDEX, NODE_ID_MIDDLE,
                        NODE_ID_RING, NODE_ID_PINKY};

    for (int i = 0; i < 5; i++) {
        CanFrame_t frame;
        uint32_t id = CAN_MAKE_ID(1, nodes[i], NODE_ID_MASTER);

        can_frame_build(&frame, 1, nodes[i], NODE_ID_MASTER,
                        CMD_SET_ANGLE, i, NULL, 0);

        TEST_ASSERT_EQUAL(nodes[i], CAN_GET_DST(frame.id), "多节点: 目标节点正确");
        TEST_ASSERT_EQUAL(NODE_ID_MASTER, CAN_GET_SRC(frame.id), "多节点: 源节点正确");
    }
}

/* ──────────────── 测试入口 ──────────────── */

void test_can_protocol(void)
{
    test_can_id_encoding();
    test_can_frame_build();
    test_can_frame_parse();
    test_angle_command_frame();
    test_angle_report_frame();
    test_multi_node_comm();
}
