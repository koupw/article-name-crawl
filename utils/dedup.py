"""论文去重逻辑"""

import re
import logging
from typing import Optional

from models.paper import Paper

logger = logging.getLogger(__name__)

# 标题相似度阈值
SIMILARITY_THRESHOLD = 0.85


def normalize_title(title: str) -> str:
    """标准化标题用于比较

    Args:
        title: 原始标题

    Returns:
        标准化后的标题
    """
    # 转小写
    title = title.lower()
    # 移除标点符号
    title = re.sub(r"[^\w\s]", "", title)
    # 移除多余空格
    title = " ".join(title.split())
    return title


def calculate_similarity(str1: str, str2: str) -> float:
    """计算两个字符串的相似度（使用 Levenshtein 距离）

    Args:
        str1: 字符串 1
        str2: 字符串 2

    Returns:
        相似度分数 (0-1)
    """
    try:
        from Levenshtein import ratio
        return ratio(str1, str2)
    except ImportError:
        # 如果 Levenshtein 库不可用，使用简单的 Jaccard 相似度
        return jaccard_similarity(str1, str2)


def jaccard_similarity(str1: str, str2: str) -> float:
    """计算 Jaccard 相似度

    Args:
        str1: 字符串 1
        str2: 字符串 2

    Returns:
        相似度分数 (0-1)
    """
    set1 = set(str1.split())
    set2 = set(str2.split())
    intersection = set1 & set2
    union = set1 | set2
    if not union:
        return 0.0
    return len(intersection) / len(union)


def deduplicate(papers: list[Paper]) -> list[Paper]:
    """对论文列表进行去重

    去重策略（按优先级）：
    1. DOI 相同 -> 重复
    2. arXiv ID 相同 -> 重复
    3. 标题相似度 > 阈值 -> 重复

    Args:
        papers: 论文列表

    Returns:
        去重后的论文列表
    """
    seen_dois: set[str] = set()
    seen_arxiv_ids: set[str] = set()
    seen_titles: list[str] = []  # 存储标准化后的标题
    unique_papers: list[Paper] = []

    for paper in papers:
        # 1. DOI 去重
        if paper.doi:
            doi_lower = paper.doi.lower().strip()
            if doi_lower in seen_dois:
                logger.debug(f"DOI 重复: {paper.title}")
                continue
            seen_dois.add(doi_lower)

        # 2. arXiv ID 去重
        if paper.arxiv_id:
            arxiv_id = paper.arxiv_id.strip()
            if arxiv_id in seen_arxiv_ids:
                logger.debug(f"arXiv ID 重复: {paper.title}")
                continue
            seen_arxiv_ids.add(arxiv_id)

        # 3. 标题相似度去重
        normalized = normalize_title(paper.title)
        is_duplicate = False

        for seen_title in seen_titles:
            similarity = calculate_similarity(normalized, seen_title)
            if similarity >= SIMILARITY_THRESHOLD:
                logger.debug(f"标题相似 ({similarity:.2f}): {paper.title}")
                is_duplicate = True
                break

        if is_duplicate:
            continue

        seen_titles.append(normalized)
        unique_papers.append(paper)

    logger.info(f"去重: {len(papers)} -> {len(unique_papers)} 篇论文")
    return unique_papers
