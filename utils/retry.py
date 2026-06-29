"""指数退避 HTTP 请求重试

可重试的异常类型：
- ConnectionError (连接失败)
- TimeoutError (超时)
- HTTP 429/5xx (限流/服务器错误)
"""

import time
import logging

logger = logging.getLogger(__name__)

# 可重试的 HTTP 状态码
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def retryable_request(
    method: str,
    url: str,
    session,
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    **kwargs,
):
    """带指数退避的 HTTP 请求重试

    Args:
        method: HTTP 方法 (GET, POST, ...)
        url: 请求 URL
        session: requests.Session 实例
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        backoff: 退避因子
        **kwargs: 传递给 session.request 的额外参数

    Returns:
        requests.Response 对象

    Raises:
        最后一次尝试的异常（所有重试均失败后）
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            response = session.request(method, url, **kwargs)

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries - 1:
                delay = base_delay * (backoff**attempt)
                logger.warning(
                    "HTTP %s on %s, retry %d/%d, wait %.1fs",
                    response.status_code,
                    url[:60],
                    attempt + 1,
                    max_retries,
                    delay,
                )
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response

        except (ConnectionError, TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (backoff**attempt)
                logger.warning(
                    "Request failed: %s, retry %d/%d, wait %.1fs",
                    e,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error("Request failed after %d retries: %s", max_retries, e)
                raise

    raise last_error  # type: ignore
