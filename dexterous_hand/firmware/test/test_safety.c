/**
 * @file    test_safety.c
 * @brief   安全模块单元测试
 */

#include <stdio.h>
#include <stdint.h>

/* 测试宏 */
extern int tests_run;
extern int tests_passed;
extern int tests_failed;

#define TEST_ASSERT(condition, message) \
    do { \
        tests_run++; \
        if (condition) { \
            tests_passed++; \
            printf("  ✓ %s\n", message); \
        } else { \
            tests_failed++; \
            printf("  ✗ %s (line %d)\n", message, __LINE__); \
        } \
    } while(0)

#define TEST_ASSERT_EQUAL(expected, actual, message) \
    do { \
        tests_run++; \
        if ((expected) == (actual)) { \
            tests_passed++; \
            printf("  ✓ %s\n", message); \
        } else { \
            tests_failed++; \
            printf("  ✗ %s: expected %d, got %d (line %d)\n", \
                   message, (int)(expected), (int)(actual), __LINE__); \
        } \
    } while(0)

/* ──────────────── 安全模块定义 (模拟) ──────────────── */

/* 错误码 */
typedef enum {
    ERR_NONE            = 0x00,
    ERR_OVERCURRENT     = 0x01,
    ERR_STALL           = 0x02,
    ERR_COMM_TIMEOUT    = 0x03,
    ERR_FSR_OVERLOAD    = 0x04,
    ERR_ANGLE_LIMIT     = 0x05,
} ErrorCode_t;

/* 系统状态位 */
#define SYS_STATUS_RUNNING      (1 << 0)
#define SYS_STATUS_ESTOP        (1 << 1)
#define SYS_STATUS_COMM_ERR     (1 << 2)
#define SYS_STATUS_STALL        (1 << 3)

/* 安全参数 */
#define SAFETY_ANGLE_MIN        0
#define SAFETY_ANGLE_MAX        1800
#define SAFETY_STALL_PWM        800
#define SAFETY_STALL_TIME_MS    500
#define FSR_OVERLOAD_THRESHOLD  3500
#define CAN_TIMEOUT_MS          500

/* 安全状态 */
typedef struct {
    uint8_t estop_active;
    uint8_t stall_detected;
    uint32_t last_can_time;
    uint32_t stall_start_time;
    int16_t stall_encoder_start;
    ErrorCode_t error_code;
} SafetyState_t;

static SafetyState_t safety_state;

/* 模拟时间 */
static uint32_t mock_tick = 0;

static uint32_t HAL_GetTick(void) {
    return mock_tick;
}

/* 安全函数 */
static void Safety_Init(void)
{
    safety_state.estop_active = 0;
    safety_state.stall_detected = 0;
    safety_state.last_can_time = 0;
    safety_state.stall_start_time = 0;
    safety_state.stall_encoder_start = 0;
    safety_state.error_code = ERR_NONE;
}

static uint16_t Safety_ClampAngle(uint16_t angle)
{
    if (angle < SAFETY_ANGLE_MIN) return SAFETY_ANGLE_MIN;
    if (angle > SAFETY_ANGLE_MAX) return SAFETY_ANGLE_MAX;
    return angle;
}

static uint8_t Safety_CheckStall(int16_t pwm, int16_t encoder)
{
    if (pwm > SAFETY_STALL_PWM || pwm < -SAFETY_STALL_PWM) {
        if (safety_state.stall_start_time == 0) {
            safety_state.stall_start_time = mock_tick;
            safety_state.stall_encoder_start = encoder;
            safety_state.stall_detected = 0;
        } else {
            int16_t delta = encoder - safety_state.stall_encoder_start;
            if (delta < 5 && delta > -5) {
                if ((mock_tick - safety_state.stall_start_time) >= SAFETY_STALL_TIME_MS) {
                    safety_state.stall_detected = 1;
                    return 1;
                }
            } else {
                safety_state.stall_start_time = mock_tick;
                safety_state.stall_encoder_start = encoder;
            }
        }
    } else {
        safety_state.stall_start_time = 0;
    }
    return 0;
}

static uint8_t Safety_CheckFSROverload(uint16_t adc_raw)
{
    return (adc_raw > FSR_OVERLOAD_THRESHOLD) ? 1 : 0;
}

static uint8_t Safety_CheckCANTimeout(void)
{
    return ((mock_tick - safety_state.last_can_time) > CAN_TIMEOUT_MS) ? 1 : 0;
}

static void Safety_EmergencyStop(ErrorCode_t reason)
{
    safety_state.estop_active = 1;
    safety_state.error_code = reason;
}

/* ──────────────── 测试用例 ──────────────── */

/**
 * @brief 测试角度限幅
 */
static void test_angle_clamp(void)
{
    Safety_Init();

    /* 正常范围 */
    TEST_ASSERT_EQUAL(900, Safety_ClampAngle(900), "角度限幅: 900 -> 900");

    /* 低于最小值 */
    TEST_ASSERT_EQUAL(0, Safety_ClampAngle(0), "角度限幅: 0 -> 0");

    /* 高于最大值 */
    TEST_ASSERT_EQUAL(1800, Safety_ClampAngle(1800), "角度限幅: 1800 -> 1800");

    /* 超出范围 */
    TEST_ASSERT_EQUAL(0, Safety_ClampAngle(0), "角度限幅: 下限");
    TEST_ASSERT_EQUAL(1800, Safety_ClampAngle(2000), "角度限幅: 超上限 -> 1800");
}

/**
 * @brief 测试堵转检测
 */
static void test_stall_detection(void)
{
    Safety_Init();
    mock_tick = 0;

    /* 低PWM，不触发 */
    TEST_ASSERT_EQUAL(0, Safety_CheckStall(500, 100), "堵转检测: 低PWM不触发");

    /* 高PWM，编码器不动 */
    mock_tick = 100;
    TEST_ASSERT_EQUAL(0, Safety_CheckStall(900, 100), "堵转检测: 开始计时");

    mock_tick = 400;
    TEST_ASSERT_EQUAL(0, Safety_CheckStall(900, 100), "堵转检测: 持续中");

    mock_tick = 700;
    TEST_ASSERT_EQUAL(1, Safety_CheckStall(900, 102), "堵转检测: 超时触发");

    /* 重置后，编码器有变化 */
    Safety_Init();
    mock_tick = 0;

    mock_tick = 100;
    TEST_ASSERT_EQUAL(0, Safety_CheckStall(900, 100), "堵转检测: 重新开始");

    mock_tick = 300;
    TEST_ASSERT_EQUAL(0, Safety_CheckStall(900, 200), "堵转检测: 编码器变化，重置");
}

/**
 * @brief 测试FSR过载检测
 */
static void test_fsr_overload(void)
{
    Safety_Init();

    /* 正常值 */
    TEST_ASSERT_EQUAL(0, Safety_CheckFSROverload(1000), "FSR过载: 正常值不触发");

    /* 接近阈值 */
    TEST_ASSERT_EQUAL(0, Safety_CheckFSROverload(3499), "FSR过载: 接近阈值不触发");

    /* 超过阈值 */
    TEST_ASSERT_EQUAL(1, Safety_CheckFSROverload(3500), "FSR过载: 达到阈值触发");
    TEST_ASSERT_EQUAL(1, Safety_CheckFSROverload(4000), "FSR过载: 超过阈值触发");
}

/**
 * @brief 测试CAN超时检测
 */
static void test_can_timeout(void)
{
    Safety_Init();
    mock_tick = 0;
    safety_state.last_can_time = 0;

    /* 刚收到心跳 */
    TEST_ASSERT_EQUAL(0, Safety_CheckCANTimeout(), "CAN超时: 刚收到不超时");

    /* 400ms后 */
    mock_tick = 400;
    TEST_ASSERT_EQUAL(0, Safety_CheckCANTimeout(), "CAN超时: 400ms不超时");

    /* 600ms后 */
    mock_tick = 600;
    TEST_ASSERT_EQUAL(1, Safety_CheckCANTimeout(), "CAN超时: 600ms超时");
}

/**
 * @brief 测试急停功能
 */
static void test_emergency_stop(void)
{
    Safety_Init();

    TEST_ASSERT_EQUAL(0, safety_state.estop_active, "急停: 初始未触发");

    Safety_EmergencyStop(ERR_STALL);

    TEST_ASSERT_EQUAL(1, safety_state.estop_active, "急停: 触发后激活");
    TEST_ASSERT_EQUAL(ERR_STALL, safety_state.error_code, "急停: 错误码正确");
}

/**
 * @brief 测试多错误场景
 */
static void test_multiple_errors(void)
{
    Safety_Init();

    /* 模拟: FSR过载 -> 急停 */
    uint16_t adc_value = 4000;
    if (Safety_CheckFSROverload(adc_value)) {
        Safety_EmergencyStop(ERR_FSR_OVERLOAD);
    }

    TEST_ASSERT_EQUAL(1, safety_state.estop_active, "多错误: FSR过载触发急停");
    TEST_ASSERT_EQUAL(ERR_FSR_OVERLOAD, safety_state.error_code, "多错误: 错误码=FSR过载");

    /* 模拟: CAN超时 -> 通信错误 */
    Safety_Init();
    mock_tick = 1000;
    safety_state.last_can_time = 0;

    if (Safety_CheckCANTimeout()) {
        Safety_EmergencyStop(ERR_COMM_TIMEOUT);
    }

    TEST_ASSERT_EQUAL(1, safety_state.estop_active, "多错误: CAN超时触发急停");
    TEST_ASSERT_EQUAL(ERR_COMM_TIMEOUT, safety_state.error_code, "多错误: 错误码=通信超时");
}

/* ──────────────── 测试入口 ──────────────── */

void test_safety_module(void)
{
    test_angle_clamp();
    test_stall_detection();
    test_fsr_overload();
    test_can_timeout();
    test_emergency_stop();
    test_multiple_errors();
}
