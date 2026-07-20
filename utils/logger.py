"""日志配置"""

import logging
import sys
from rich.logging import RichHandler


def setup_logger(verbose: bool = False, replace_handlers: bool = True) -> None:
    """配置日志

    Args:
        verbose: 是否启用详细日志
        replace_handlers: 为 False 时保留已有 handlers（Web 模式使用），
                         仅调整日志级别，避免覆盖 web 框架的日志系统
    """
    level = logging.DEBUG if verbose else logging.INFO

    if replace_handlers:
        # 清除现有处理器（CLI 模式）
        logging.root.handlers.clear()

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
    else:
        # Web 模式：保留已有 handlers，仅调整级别
        logging.root.setLevel(level)

    # 设置第三方库日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
