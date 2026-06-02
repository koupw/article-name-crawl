"""翻译工具模块"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 翻译器实例（延迟初始化）
_translator = None


def _get_translator():
    """获取翻译器实例（延迟初始化）"""
    global _translator
    if _translator is None:
        try:
            from deep_translator import GoogleTranslator
            _translator = GoogleTranslator(source='en', target='zh-CN')
        except ImportError:
            logger.warning("deep-translator 库未安装，翻译功能不可用")
            return None
        except Exception as e:
            logger.warning(f"初始化翻译器失败: {e}")
            return None
    return _translator


def translate_to_chinese(text: str) -> Optional[str]:
    """将英文文本翻译为中文

    Args:
        text: 英文文本

    Returns:
        中文翻译，失败返回 None
    """
    if not text or not text.strip():
        return None

    translator = _get_translator()
    if translator is None:
        return None

    try:
        # deep-translator 有字符数限制，长文本需要分段
        if len(text) > 4500:
            text = text[:4500]

        result = translator.translate(text)
        return result
    except Exception as e:
        logger.debug(f"翻译失败: {e}")
        return None


def batch_translate(texts: list[str], batch_size: int = 10) -> list[Optional[str]]:
    """批量翻译英文文本

    Args:
        texts: 英文文本列表
        batch_size: 批次大小

    Returns:
        中文翻译列表，失败的位置为 None
    """
    results = []
    translator = _get_translator()

    if translator is None:
        return [None] * len(texts)

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        for text in batch:
            if not text or not text.strip():
                results.append(None)
                continue

            try:
                if len(text) > 4500:
                    text = text[:4500]
                result = translator.translate(text)
                results.append(result)
            except Exception as e:
                logger.debug(f"翻译失败: {e}")
                results.append(None)

    return results
