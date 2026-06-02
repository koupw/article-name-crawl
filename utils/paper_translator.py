"""论文标题翻译处理"""

import logging
from typing import Optional

from models.paper import Paper
from utils.translator import translate_to_chinese

logger = logging.getLogger(__name__)


def translate_paper_titles(papers: list[Paper]) -> list[Paper]:
    """批量翻译论文标题

    Args:
        papers: 论文列表

    Returns:
        添加了中文标题的论文列表
    """
    if not papers:
        return papers

    logger.info(f"开始翻译 {len(papers)} 篇论文标题...")

    translated_count = 0
    for i, paper in enumerate(papers):
        if paper.title_zh:
            # 已有翻译，跳过
            continue

        title_zh = translate_to_chinese(paper.title)
        if title_zh:
            paper.title_zh = title_zh
            translated_count += 1
            logger.debug(f"[{i+1}] {paper.title}")
            logger.debug(f"    -> {title_zh}")

        # 每 10 篇打印进度
        if (i + 1) % 10 == 0:
            logger.info(f"已翻译 {i+1}/{len(papers)} 篇")

    logger.info(f"翻译完成: {translated_count}/{len(papers)} 篇成功")
    return papers
