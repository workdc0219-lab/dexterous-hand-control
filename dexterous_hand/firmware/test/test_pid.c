/**
 * @file    test_pid.c
 * @brief   PID控制器单元测试
 */

#include <stdio.h>
#include <math.h>
#include "test_helpers.h"

/* ──────────────── PID 模拟实现 ──────────────── */

/* PID参数 */
typedef struct {
    float kp;
    float ki;
    float kd;
    float out_min;
    float out_max;
    float err;
    float err_last;
    float err_prev;
    float output;
} PID_Test_t;

/**
 * @brief 增量式PID计算 (测试用)
 */
static float PID_CalcIncremental(PID_Test_t *pid, float error)
{
    pid->err = error;

    float delta = pid->kp * (pid->err - pid->err_last)
                + pid->ki * pid->err
                + pid->kd * (pid->err - 2.0f * pid->err_last + pid->err_prev);

    pid->output += delta;

    /* 输出限幅 */
    if (pid->output > pid->out_max) pid->output = pid->out_max;
    if (pid->output < pid->out_min) pid->output = pid->out_min;

    /* 更新历史误差 */
    pid->err_prev = pid->err_last;
    pid->err_last = pid->err;

    return pid->output;
}

/**
 * @brief 初始化PID (测试用)
 */
static void PID_Init_Test(PID_Test_t *pid, float kp, float ki, float kd)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->out_min = -1000.0f;
    pid->out_max = 1000.0f;
    pid->err = 0;
    pid->err_last = 0;
    pid->err_prev = 0;
    pid->output = 0;
}

/* ──────────────── 测试用例 ──────────────── */

/**
 * @brief 测试PID初始化
 */
static void test_pid_init(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 1.0f, 0.1f, 0.01f);

    TEST_ASSERT_FLOAT(1.0f, pid.kp, 0.001f, "PID Kp初始化正确");
    TEST_ASSERT_FLOAT(0.1f, pid.ki, 0.001f, "PID Ki初始化正确");
    TEST_ASSERT_FLOAT(0.01f, pid.kd, 0.001f, "PID Kd初始化正确");
    TEST_ASSERT_FLOAT(0.0f, pid.output, 0.001f, "PID输出初始化为0");
}

/**
 * @brief 测试PID比例控制
 */
static void test_pid_proportional(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 1.0f, 0.0f, 0.0f);

    /* 第一次计算: error=100 */
    float output = PID_CalcIncremental(&pid, 100.0f);
    TEST_ASSERT_FLOAT(100.0f, output, 0.1f, "比例控制: error=100, output=100");

    /* 第二次计算: error=100 (保持) */
    output = PID_CalcIncremental(&pid, 100.0f);
    TEST_ASSERT_FLOAT(100.0f, output, 0.1f, "比例控制: error不变, output不变");

    /* 第三次计算: error=50 (减小) */
    output = PID_CalcIncremental(&pid, 50.0f);
    TEST_ASSERT_FLOAT(50.0f, output, 0.1f, "比例控制: error=50, output=50");
}

/**
 * @brief 测试PID积分控制
 */
static void test_pid_integral(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 0.0f, 0.1f, 0.0f);

    /* 多次计算相同误差 */
    float output;
    for (int i = 0; i < 10; i++) {
        output = PID_CalcIncremental(&pid, 100.0f);
    }

    /* 积分累积: 0.1 * 100 * 10 = 100 */
    TEST_ASSERT_FLOAT(100.0f, output, 1.0f, "积分控制: 10次error=100, output≈100");
}

/**
 * @brief 测试PID微分控制
 */
static void test_pid_derivative(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 0.0f, 0.0f, 1.0f);

    /* 第一次: error=0 -> 100 */
    float output = PID_CalcIncremental(&pid, 100.0f);
    TEST_ASSERT_FLOAT(100.0f, output, 0.1f, "微分控制: error变化100, output=100");

    /* 第二次: error保持100 */
    output = PID_CalcIncremental(&pid, 100.0f);
    TEST_ASSERT_FLOAT(100.0f, output, 0.1f, "微分控制: error不变, output不变");

    /* 第三次: error从100变到50 */
    output = PID_CalcIncremental(&pid, 50.0f);
    TEST_ASSERT_FLOAT(50.0f, output, 0.1f, "微分控制: error减小50, output减小");
}

/**
 * @brief 测试PID输出限幅
 */
static void test_pid_output_clamp(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 10.0f, 0.0f, 0.0f);
    pid.out_max = 500.0f;
    pid.out_min = -500.0f;

    /* 大误差，输出应该被限幅 */
    float output = PID_CalcIncremental(&pid, 1000.0f);
    TEST_ASSERT_FLOAT(500.0f, output, 0.1f, "输出限幅: 大误差限制到500");

    /* 负误差 */
    PID_Init_Test(&pid, 10.0f, 0.0f, 0.0f);
    pid.out_max = 500.0f;
    pid.out_min = -500.0f;

    output = PID_CalcIncremental(&pid, -1000.0f);
    TEST_ASSERT_FLOAT(-500.0f, output, 0.1f, "输出限幅: 大负误差限制到-500");
}

/**
 * @brief 测试PID收敛性
 */
static void test_pid_convergence(void)
{
    PID_Test_t pid;
    PID_Init_Test(&pid, 0.5f, 0.01f, 0.1f);

    float target = 100.0f;
    float actual = 0.0f;
    float output = 0.0f;

    /* 模拟100次迭代 */
    for (int i = 0; i < 100; i++) {
        float error = target - actual;
        output = PID_CalcIncremental(&pid, error);
        actual += output * 0.01f;  /* 模拟系统响应 */
    }

    /* 应该收敛到目标值附近 */
    TEST_ASSERT(fabs(actual - target) < 10.0f,
                "PID收敛性: 100次迭代后接近目标值");
}

/* ──────────────── 测试入口 ──────────────── */

void test_pid_controller(void)
{
    test_pid_init();
    test_pid_proportional();
    test_pid_integral();
    test_pid_derivative();
    test_pid_output_clamp();
    test_pid_convergence();
}
