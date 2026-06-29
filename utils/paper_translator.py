"""论文标题翻译处理（支持并发翻译）"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from models.paper import Paper
from utils.translator import translate_to_chinese

logger = logging.getLogger(__name__)


def translate_paper_titles(papers: list[Paper], max_workers: int = 5) -> list[Paper]:
    """批量翻译论文标题

    使用 ThreadPoolExecutor 并发翻译，显著缩短翻译时间。
    已有翻译（title_zh 不为空）的论文跳过翻译步骤。

    Args:
        papers: 论文列表
        max_workers: 并发翻译线程数

    Returns:
        添加了中文标题的论文列表
    """
    if not papers:
        return papers

    # 只翻译尚未翻译的
    to_translate = [p for p in papers if not p.title_zh]
    already_present = len(papers) - len(to_translate)

    if not to_translate:
        logger.info("所有论文已有翻译，跳过翻译步骤")
        return papers

    logger.info("开始翻译 %d 篇论文标题（%d 篇已有缓存，%d 并发）",
                len(to_translate), already_present, max_workers)

    success = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_translate_one, p): p for p in to_translate
        }

        for future in as_completed(future_map):
            paper = future_map[future]
            try:
                future.result()
                success += 1
            except Exception as e:
                logger.debug("翻译失败: %s - %s", paper.title[:50], e)

    logger.info("翻译完成: %d/%d 篇成功", success, len(to_translate))
    return papers


def _translate_one(paper: Paper) -> None:
    """翻译单篇论文标题（在线程池中执行）"""
    title_zh = translate_to_chinese(paper.title)
    if title_zh:
        paper.title_zh = title_zh
