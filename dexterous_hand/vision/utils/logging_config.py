"""统一日志配置模块.

所有视觉模块应使用此模块配置日志，避免重复调用 logging.basicConfig()。

Usage:
    from vision.utils.logging_config import setup_logging, get_logger

    # 在入口脚本的 main() 中调用一次
    setup_logging(level=logging.INFO)

    # 各模块获取 logger
    logger = get_logger(__name__)
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    format_str: Optional[str] = None,
    datefmt: str = "%Y-%m-%d %H:%M:%S",
    stream=None,
) -> None:
    """配置全局日志.

    应在入口脚本的 main() 函数中调用一次。

    Args:
        level: 日志级别
        format_str: 日志格式字符串
        datefmt: 日期格式
        stream: 输出流 (默认 stderr)
    """
    if format_str is None:
        format_str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_str,
        datefmt=datefmt,
        stream=stream or sys.stderr,
    )


def get_logger(name: str) -> logging.Logger:
    """获取模块专用的 logger.

    Args:
        name: 模块名称，通常传入 __name__

    Returns:
        logging.Logger: logger 实例
    """
    return logging.getLogger(name)
