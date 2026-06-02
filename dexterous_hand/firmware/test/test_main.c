/**
 * @file    test_main.c
 * @brief   固件单元测试主程序
 * @details 在主机上运行的测试框架，验证各模块功能
 *
 * 编译: gcc -I../shared/Inc -I. test_main.c test_pid.c test_can.c test_safety.c -o test_firmware -lm
 * 运行: ./test_firmware
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <assert.h>

/* 测试计数器 */
static int tests_run = 0;
static int tests_passed = 0;
static int tests_failed = 0;

/* 测试宏 */
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

#define TEST_ASSERT_FLOAT(expected, actual, tolerance, message) \
    do { \
        tests_run++; \
        if (fabs((double)(expected) - (double)(actual)) <= (tolerance)) { \
            tests_passed++; \
            printf("  ✓ %s\n", message); \
        } else { \
            tests_failed++; \
            printf("  ✗ %s: expected %.2f, got %.2f (line %d)\n", \
                   message, (double)(expected), (double)(actual), __LINE__); \
        } \
    } while(0)

/* 外部测试函数声明 */
extern void test_pid_controller(void);
extern void test_can_protocol(void);
extern void test_safety_module(void);

/* ──────────────── 测试套件 ──────────────── */

/**
 * @brief 运行所有测试
 */
void run_all_tests(void)
{
    printf("\n");
    printf("╔═══════════════════════════════════════════════════════════╗\n");
    printf("║         灵巧手固件单元测试                                ║\n");
    printf("╚═══════════════════════════════════════════════════════════╝\n");
    printf("\n");

    printf("━━━ PID控制器测试 ━━━\n");
    test_pid_controller();
    printf("\n");

    printf("━━━ CAN协议测试 ━━━\n");
    test_can_protocol();
    printf("\n");

    printf("━━━ 安全模块测试 ━━━\n");
    test_safety_module();
    printf("\n");
}

/**
 * @brief 打印测试结果
 */
void print_results(void)
{
    printf("╔═══════════════════════════════════════════════════════════╗\n");
    printf("║ 测试结果: %d 通过, %d 失败, 共 %d 个测试                 \n",
           tests_passed, tests_failed, tests_run);
    printf("╚═══════════════════════════════════════════════════════════╝\n");

    if (tests_failed == 0) {
        printf("\n✅ 所有测试通过！\n\n");
    } else {
        printf("\n❌ 有 %d 个测试失败！\n\n", tests_failed);
    }
}

/* ──────────────── 主函数 ──────────────── */

int main(int argc, char *argv[])
{
    (void)argc;
    (void)argv;

    run_all_tests();
    print_results();

    return (tests_failed == 0) ? 0 : 1;
}
