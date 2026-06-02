.PHONY: install train export convert sim test lint clean help

# 默认目标
help:
	@echo "灵巧手项目 Makefile"
	@echo ""
	@echo "用法:"
	@echo "  make install    安装Python依赖"
	@echo "  make train      训练YOLOv8-pose模型"
	@echo "  make export     导出ONNX"
	@echo "  make convert    转换为OM模型"
	@echo "  make sim        运行MuJoCo仿真"
	@echo "  make test       运行所有测试"
	@echo "  make lint       代码检查"
	@echo "  make clean      清理编译产物"

# 安装Python依赖
install:
	pip install -r requirements.txt

# 训练YOLOv8-pose模型
train:
	python vision/train.py

# 导出ONNX
export:
	python vision/export_onnx.py

# 转换为OM模型（需要CANN环境）
convert:
	atc --model=models/best.onnx --framework=5 --output=models/best --soc_version=Ascend310

# 运行MuJoCo仿真
sim:
	python simulation/scripts/load_hand.py

# 运行所有测试
test:
	pytest test/ -v --tb=short

# 代码检查
lint:
	python -m py_compile simulation/scripts/*.py
	python -m py_compile tools/*.py
	python -m py_compile test/*.py
	@echo "代码检查通过"

# 清理编译产物
clean:
	rm -rf __pycache__ .pytest_cache
	rm -rf build/ dist/ *.egg-info
	rm -rf firmware/*/build/
	rm -rf *.pyc
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "清理完成"
