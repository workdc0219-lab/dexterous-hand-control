# Firmware Unit Test Makefile
# 编译: make
# 运行: make test
# 清理: make clean

# 编译器
CC = gcc
CFLAGS = -Wall -Wextra -I../shared/Inc -I. -lm
BUILD_DIR = build

# 源文件
SOURCES = test_main.c test_pid.c test_can.c test_safety.c
TARGET = test_firmware

# 目标文件
OBJECTS = $(addprefix $(BUILD_DIR)/,$(notdir $(SOURCES:.c=.o)))

# 默认目标
all: $(BUILD_DIR)/$(TARGET)

# 编译
$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) $(CFLAGS) -o $@
	@echo "编译完成: $@"

# 创建构建目录
$(BUILD_DIR):
	mkdir -p $@

# 运行测试
test: $(BUILD_DIR)/$(TARGET)
	@echo ""
	@echo "运行固件单元测试..."
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	./$(BUILD_DIR)/$(TARGET)

# 清理
clean:
	rm -rf $(BUILD_DIR)

# 帮助
help:
	@echo "固件单元测试 Makefile"
	@echo ""
	@echo "用法:"
	@echo "  make          编译测试程序"
	@echo "  make test     编译并运行测试"
	@echo "  make clean    清理构建文件"
	@echo "  make help     显示帮助"

.PHONY: all test clean help
