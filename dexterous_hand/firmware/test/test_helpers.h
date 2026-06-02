/**
 * @file    test_helpers.h
 * @brief   测试辅助宏定义
 * @details 所有测试文件共享的断言宏
 */

#ifndef __TEST_HELPERS_H
#define __TEST_HELPERS_H

#include <stdio.h>
#include <math.h>

/* 测试计数器 (在test_main.c中定义) */
extern int tests_run;
extern int tests_passed;
extern int tests_failed;

/* ──────────────── 断言宏 ──────────────── */

/**
 * @brief 布尔断言
 */
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

/**
 * @brief 整数相等断言
 */
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

/**
 * @brief 浮点数近似相等断言
 */
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

/**
 * @brief 浮点数范围断言
 */
#define TEST_ASSERT_IN_RANGE(actual, min_val, max_val, message) \
    do { \
        tests_run++; \
        if ((actual) >= (min_val) && (actual) <= (max_val)) { \
            tests_passed++; \
            printf("  ✓ %s\n", message); \
        } else { \
            tests_failed++; \
            printf("  ✗ %s: %.2f not in range [%.2f, %.2f] (line %d)\n", \
                   message, (double)(actual), (double)(min_val), \
                   (double)(max_val), __LINE__); \
        } \
    } while(0)

#endif /* __TEST_HELPERS_H */
