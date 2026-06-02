#!/bin/bash
# @file    setup_env.sh
# @brief   环境搭建脚本
# @details 检查Python版本、创建虚拟环境、安装依赖、检查CANN环境、验证MuJoCo安装

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印函数
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

info "灵巧手项目环境搭建"
info "项目根目录: $PROJECT_ROOT"

# ──────────────── 1. 检查Python版本 ────────────────
info "步骤 1/6: 检查Python版本..."

if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    error "未找到Python，请安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    error "Python版本过低: $PYTHON_VERSION，需要3.8+"
    exit 1
fi

info "Python版本: $PYTHON_VERSION ✓"

# ──────────────── 2. 创建虚拟环境 ────────────────
info "步骤 2/6: 创建虚拟环境..."

VENV_DIR="$PROJECT_ROOT/.venv"

if [ -d "$VENV_DIR" ]; then
    warn "虚拟环境已存在: $VENV_DIR"
else
    $PYTHON -m venv "$VENV_DIR"
    info "虚拟环境已创建: $VENV_DIR"
fi

# 激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
    source "$VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
    source "$VENV_DIR/Scripts/activate"
else
    error "无法找到虚拟环境激活脚本"
    exit 1
fi

info "虚拟环境已激活 ✓"

# ──────────────── 3. 安装依赖 ────────────────
info "步骤 3/6: 安装Python依赖..."

if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    pip install --upgrade pip
    pip install -r "$PROJECT_ROOT/requirements.txt"
    info "依赖安装完成 ✓"
else
    warn "未找到requirements.txt，跳过依赖安装"
fi

# ──────────────── 4. 检查CANN环境 ────────────────
info "步骤 4/6: 检查CANN环境..."

if command -v npu-smi &> /dev/null; then
    info "NPU驱动已安装 ✓"
    npu-smi info 2>/dev/null || warn "无法获取NPU信息"
else
    warn "未找到npu-smi命令，NPU驱动可能未安装"
fi

if [ -n "$ASCEND_INSTALL_PATH" ]; then
    info "CANN安装路径: $ASCEND_INSTALL_PATH"
    if command -v atc &> /dev/null; then
        info "ATC工具可用 ✓"
    else
        warn "ATC工具不可用，请检查CANN安装"
    fi
else
    warn "ASCEND_INSTALL_PATH未设置，CANN环境可能未配置"
fi

# ──────────────── 5. 验证MuJoCo安装 ────────────────
info "步骤 5/6: 验证MuJoCo安装..."

$PYTHON -c "import mujoco; print(f'MuJoCo版本: {mujoco.__version__}')" 2>/dev/null
if [ $? -eq 0 ]; then
    info "MuJoCo安装验证通过 ✓"
else
    warn "MuJoCo导入失败，请检查安装"
fi

# ──────────────── 6. 验证其他关键依赖 ────────────────
info "步骤 6/6: 验证其他关键依赖..."

$PYTHON -c "
import sys
deps = {
    'numpy': 'numpy',
    'cv2': 'opencv-python',
    'yaml': 'pyyaml',
    'matplotlib': 'matplotlib',
    'serial': 'pyserial',
    'can': 'python-can',
}
ok = 0
fail = 0
for module, package in deps.items():
    try:
        __import__(module)
        print(f'  {package}: ✓')
        ok += 1
    except ImportError:
        print(f'  {package}: ✗ (未安装)')
        fail += 1
print(f'\n依赖检查: {ok} 通过, {fail} 失败')
"

# ──────────────── 完成 ────────────────
echo ""
info "========================================="
info "环境搭建完成！"
info "========================================="
info ""
info "使用方法:"
info "  1. 激活虚拟环境:"
info "     source .venv/bin/activate (Linux/Mac)"
info "     .venv\\Scripts\\activate (Windows)"
info ""
info "  2. 运行仿真:"
info "     make sim"
info ""
info "  3. 运行测试:"
info "     make test"
info ""
info "  4. 训练模型:"
info "     make train"
info ""
