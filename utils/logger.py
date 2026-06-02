"""日志配置"""

import logging
import sys
from rich.logging import RichHandler


def setup_logger(verbose: bool = False) -> None:
    """配置日志

    Args:
        verbose: 是否启用详细日志
    """
    level = logging.DEBUG if verbose else logging.INFO

    # 清除现有处理器
    logging.root.handlers.clear()

    # 配置 rich 处理器
    rich_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_path=verbose,
    )

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[rich_handler],
    )

    # 设置第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
