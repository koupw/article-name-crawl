"""翻译工具模块（支持 Google / 百度翻译）"""

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# 翻译器实例缓存（延迟初始化），key 为 (backend, app_id)
_translators: dict = {}

# 百度翻译免费版限制 1 QPS，每次调用后需间隔
BAIDU_CALL_INTERVAL = 1.0


def _get_google_translator():
    """获取 Google 翻译器实例（延迟初始化）"""
    key = ("google", "")
    if key not in _translators:
        try:
            from deep_translator import GoogleTranslator
            _translators[key] = GoogleTranslator(source="en", target="zh-CN")
        except ImportError:
            logger.warning("deep-translator 库未安装，翻译功能不可用")
            _translators[key] = None
        except Exception as e:
            logger.warning(f"初始化 Google 翻译器失败: {e}")
            _translators[key] = None
    return _translators[key]


def _get_baidu_translator(app_id: str, app_key: str):
    """获取百度翻译器实例（延迟初始化）"""
    key = ("baidu", app_id)
    if key not in _translators:
        if not (app_id and app_key):
            logger.warning("百度翻译未配置 app_id/app_key，翻译功能不可用")
            _translators[key] = None
            return None
        try:
            from deep_translator import BaiduTranslator
            _translators[key] = BaiduTranslator(
                source="en", target="zh", appid=app_id, appkey=app_key,
            )
        except ImportError:
            logger.warning("deep-translator 库未安装，翻译功能不可用")
            _translators[key] = None
        except Exception as e:
            logger.warning(f"初始化百度翻译器失败: {e}")
            _translators[key] = None
    return _translators[key]


def translate_to_chinese(
    text: str,
    backend: str = "google",
    baidu_app_id: str = "",
    baidu_app_key: str = "",
) -> Optional[str]:
    """将英文文本翻译为中文

    Args:
        text: 英文文本
        backend: 翻译引擎 (google | baidu)
        baidu_app_id: 百度翻译 APP ID（backend 为 baidu 时必填）
        baidu_app_key: 百度翻译 Secret Key

    Returns:
        中文翻译，失败返回 None
    """
    if not text or not text.strip():
        return None

    if backend == "baidu":
        translator = _get_baidu_translator(baidu_app_id, baidu_app_key)
    else:
        translator = _get_google_translator()
    if translator is None:
        return None

    try:
        # deep-translator 有字符数限制，长文本需要截断
        if len(text) > 4500:
            text = text[:4500]

        result = translator.translate(text)

        # 百度免费版 1 QPS，主动限速避免触发限流
        if backend == "baidu":
            time.sleep(BAIDU_CALL_INTERVAL)

        return result
    except Exception as e:
        logger.debug(f"翻译失败: {e}")
        return None
