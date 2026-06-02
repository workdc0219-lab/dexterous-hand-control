#!/bin/bash
# CANN ATC 模型转换脚本
# 将 ONNX 模型转换为 Ascend OM 格式
#
# Usage:
#   ./convert_om.sh [--input INPUT_ONNX] [--output OUTPUT_OM] [--soc SOC_VERSION]
#
# Example:
#   ./convert_om.sh --input best.onnx --output hand_pose.om --soc Ascend310B1

set -e  # 遇到错误立即退出

# 默认参数
INPUT_ONNX="best.onnx"
OUTPUT_OM="hand_pose.om"
SOC_VERSION="Ascend310B1"
INPUT_SHAPE="1,3,640,640"
INPUT_FP="images:0"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            INPUT_ONNX="$2"
            shift 2
            ;;
        --output)
            OUTPUT_OM="$2"
            shift 2
            ;;
        --soc)
            SOC_VERSION="$2"
            shift 2
            ;;
        --input_shape)
            INPUT_SHAPE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --input FILE       输入 ONNX 文件路径 (默认: best.onnx)"
            echo "  --output FILE      输出 OM 文件路径 (默认: hand_pose.om)"
            echo "  --soc VERSION      SoC 版本 (默认: Ascend310B1)"
            echo "  --input_shape SHAPE 输入 shape (默认: 1,3,640,640)"
            echo "  --help, -h         显示帮助信息"
            exit 0
            ;;
        *)
            log_error "未知参数: $1"
            exit 1
            ;;
    esac
done

# 检查 CANN 环境
log_info "检查 CANN 环境..."
if ! command -v atc &> /dev/null; then
    log_error "atc 命令未找到，请确保 CANN 环境已正确安装并配置"
    log_error "请执行: source /usr/local/Ascend/ascend-toolkit/set_env.sh"
    exit 1
fi

# 检查输入文件
log_info "检查输入文件: ${INPUT_ONNX}"
if [ ! -f "${INPUT_ONNX}" ]; then
    log_error "输入文件不存在: ${INPUT_ONNX}"
    exit 1
fi

# 获取输入文件的绝对路径
INPUT_ONNX=$(realpath "${INPUT_ONNX}")
OUTPUT_DIR=$(dirname "${OUTPUT_OM}")
OUTPUT_FILENAME=$(basename "${OUTPUT_OM}")

# 确保输出目录存在
mkdir -p "${OUTPUT_DIR}"

# 打印转换参数
log_info "=" * 50
log_info "开始 ATC 模型转换"
log_info "=" * 50
log_info "输入文件: ${INPUT_ONNX}"
log_info "输出文件: ${OUTPUT_OM}"
log_info "SoC 版本: ${SOC_VERSION}"
log_info "输入 Shape: ${INPUT_SHAPE}"

# 执行 ATC 转换
log_info "执行 ATC 转换..."
atc \
    --model="${INPUT_ONNX}" \
    --framework=5 \
    --output="${OUTPUT_DIR}/${OUTPUT_FILENAME%.*}" \
    --soc_version="${SOC_VERSION}" \
    --input_shape="${INPUT_FP}:${INPUT_SHAPE}" \
    --input_fp16_nodes="${INPUT_FP}" \
    --output_type=FP16 \
    --log=info

# 检查转换结果
if [ $? -eq 0 ]; then
    log_info "ATC 转换成功!"
else
    log_error "ATC 转换失败!"
    exit 1
fi

# 验证输出文件
log_info "验证输出文件..."
if [ -f "${OUTPUT_OM}" ]; then
    FILE_SIZE=$(stat -c%s "${OUTPUT_OM}" 2>/dev/null || stat -f%z "${OUTPUT_OM}" 2>/dev/null)
    log_info "OM 文件生成成功: ${OUTPUT_OM}"
    log_info "文件大小: ${FILE_SIZE} bytes"
else
    # 检查是否生成在当前目录
    if [ -f "${OUTPUT_FILENAME%.*}.om" ]; then
        mv "${OUTPUT_FILENAME%.*}.om" "${OUTPUT_OM}"
        log_info "OM 文件已移动到: ${OUTPUT_OM}"
    else
        log_error "OM 文件未生成!"
        exit 1
    fi
fi

log_info "=" * 50
log_info "转换完成!"
log_info "=" * 50
log_info "输出文件: ${OUTPUT_OM}"
log_info ""
log_info "后续步骤:"
log_info "1. 将 OM 文件部署到 Ascend 设备"
log_info "2. 使用 ACL 推理 API 加载模型"
log_info "3. 参考 inference/pose_detector.py 进行推理"
