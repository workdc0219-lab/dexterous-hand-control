/**
 * @file    safety.c
 * @brief   安全保护机制实现
 * @details 急停按钮、过流检测、堵转检测、通信超时检测
 */

#include "safety.h"
#include "motor_ctrl.h"
#include "can_protocol.h"

/* ──────────────── 私有变量 ──────────────── */
static volatile SafetyState_t g_safety_state = SAFETY_NORMAL;
static volatile uint8_t g_estop_reason = ERR_NONE;

/* 各节点心跳时间戳 */
static volatile uint32_t g_heartbeat_ts[6] = {0};  /* 0=master, 1~5=fingers */

/* 堵转检测：上次编码器值和时间 */
static uint16_t g_stall_encoder[5] = {0};
static uint32_t g_stall_timestamp[5] = {0};

/* ──────────────── 函数实现 ──────────────── */

/**
 * @brief  初始化安全模块
 */
HAL_StatusTypeDef Safety_Init(void)
{
    GPIO_InitTypeDef gpio = {0};

    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* PC13 - 急停按钮 (外部上拉，下降沿触发) */
    gpio.Pin = GPIO_PIN_13;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOC, &gpio);

    HAL_NVIC_SetPriority(EXTI15_10_IRQn, 0, 0);  /* 最高优先级 */
    HAL_NVIC_EnableIRQ(EXTI15_10_IRQn);

    /* PB8 - 过流检测 (外部上拉，下降沿触发) */
    gpio.Pin = GPIO_PIN_8;
    gpio.Mode = GPIO_MODE_IT_FALLING;
    gpio.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &gpio);

    HAL_NVIC_SetPriority(EXTI9_5_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(EXTI9_5_IRQn);

    return HAL_OK;
}

/**
 * @brief  检测电机堵转
 * @details 如果电流超过阈值且编码器值长时间不变，则判定为堵转
 */
bool Safety_CheckStall(uint8_t motor, uint16_t current_ma, uint16_t encoder)
{
    if (motor >= 5) return false;

    uint32_t now = HAL_GetTick();

    /* 电流未超阈值，重置 */
    if (current_ma < STALL_CURRENT_MA) {
        g_stall_encoder[motor] = encoder;
        g_stall_timestamp[motor] = now;
        return false;
    }

    /* 检查编码器是否变化 */
    if (encoder != g_stall_encoder[motor]) {
        g_stall_encoder[motor] = encoder;
        g_stall_timestamp[motor] = now;
        return false;
    }

    /* 电流超阈值且编码器未变化，检查超时 */
    if ((now - g_stall_timestamp[motor]) >= STALL_TIMEOUT_MS) {
        return true;
    }

    return false;
}

/**
 * @brief  CAN心跳超时检测
 */
bool Safety_CheckCommTimeout(void)
{
    uint32_t now = HAL_GetTick();

    /* 检查各手指节点心跳 (NODE_ID_THUMB~NODE_ID_PINKY = 1~5) */
    for (int i = 1; i <= 5; i++) {
        if (g_heartbeat_ts[i] == 0) continue;  /* 未收到过心跳，跳过 */

        if ((now - g_heartbeat_ts[i]) > CAN_TIMEOUT_MS) {
            return true;  /* 超时 */
        }
    }

    return false;
}

/**
 * @brief  角度限幅
 */
void Safety_CheckAngleLimit(uint16_t *angle)
{
    uint16_t min_angle = ANGLE_MIN_DEG * 10;
    uint16_t max_angle = ANGLE_MAX_DEG * 10;

    if (*angle < min_angle) {
        *angle = min_angle;
    } else if (*angle > max_angle) {
        *angle = max_angle;
    }
}

/**
 * @brief  触发紧急停止
 */
void Safety_TriggerEStop(uint8_t reason)
{
    if (g_safety_state == SAFETY_SAFE_STOP) return;

    g_safety_state = SAFETY_SAFE_STOP;
    g_estop_reason = reason;

    /* 停止所有电机 */
    Motor_StopAll();

    /* 通知所有节点 */
    CAN_SendEmergencyStop(reason);
}

/**
 * @brief  从安全状态恢复
 */
HAL_StatusTypeDef Safety_Recover(void)
{
    if (g_safety_state != SAFETY_SAFE_STOP) {
        return HAL_OK;  /* 不在停机状态 */
    }

    /* 检查恢复条件 */
    /* 1. 急停按钮已释放 */
    if (HAL_GPIO_ReadPin(GPIOC, GPIO_PIN_13) == GPIO_PIN_RESET) {
        return HAL_ERROR;  /* 按钮仍按下 */
    }

    /* 2. 过流信号已清除 */
    if (HAL_GPIO_ReadPin(GPIOB, GPIO_PIN_8) == GPIO_PIN_RESET) {
        return HAL_ERROR;  /* 仍然过流 */
    }

    /* 进入恢复状态 */
    g_safety_state = SAFETY_RECOVERING;

    /* 重置PID等控制器 */
    /* 主控侧主要是转发，节点侧自行恢复 */

    /* 短暂延时后恢复正常 */
    HAL_Delay(100);
    g_safety_state = SAFETY_NORMAL;
    g_estop_reason = ERR_NONE;

    return HAL_OK;
}

/**
 * @brief  获取当前安全状态
 */
SafetyState_t Safety_GetState(void)
{
    return g_safety_state;
}

/**
 * @brief  定期安全检查（在定时器中断中调用）
 */
void Safety_PeriodicCheck(void)
{
    /* 已在急停状态则跳过 */
    if (g_safety_state == SAFETY_SAFE_STOP) return;

    /* 检查通信超时 */
    if (Safety_CheckCommTimeout()) {
        Safety_TriggerEStop(ERR_COMM_TIMEOUT);
    }
}

/**
 * @brief  更新心跳时间戳
 */
void Safety_UpdateHeartbeat(NodeId_t node)
{
    if (node <= NODE_ID_PINKY) {
        g_heartbeat_ts[node] = HAL_GetTick();
    }
}

/**
 * @brief  PC13急停按钮中断回调
 */
void Safety_EStopButtonCallback(void)
{
    Safety_TriggerEStop(ERR_OVERCURRENT);  /* 按钮触发统一用过流码 */
}

/**
 * @brief  PB8过流检测中断回调
 */
void Safety_OvercurrentCallback(void)
{
    Safety_TriggerEStop(ERR_OVERCURRENT);
}

/**
 * @brief  EXTI中断处理
 */
void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    if (GPIO_Pin == GPIO_PIN_13) {
        Safety_EStopButtonCallback();
    } else if (GPIO_Pin == GPIO_PIN_8) {
        Safety_OvercurrentCallback();
    }
}

/**
 * @brief  获取急停原因
 */
uint8_t Safety_GetEStopReason(void)
{
    return g_estop_reason;
}
