"""论文质量筛选逻辑"""

import logging
from typing import Optional

from models.paper import Paper
from config.loader import FilterConfig

logger = logging.getLogger(__name__)


def filter_papers(papers: list[Paper], filters: FilterConfig) -> list[Paper]:
    """根据筛选条件过滤论文

    Args:
        papers: 论文列表
        filters: 筛选配置

    Returns:
        符合条件的论文列表
    """
    if not _has_any_filter(filters):
        return papers

    filtered = []
    for paper in papers:
        if _passes_filter(paper, filters):
            filtered.append(paper)
        else:
            logger.debug(f"筛选排除: {paper.title}")

    logger.info(f"质量筛选: {len(papers)} -> {len(filtered)} 篇论文")
    return filtered


def _has_any_filter(filters: FilterConfig) -> bool:
    """检查是否有任何筛选条件"""
    return (
        filters.min_citations > 0
        or filters.year_from is not None
        or filters.year_to is not None
        or filters.require_doi
        or filters.open_access_only
    )


def _passes_filter(paper: Paper, filters: FilterConfig) -> bool:
    """检查论文是否通过筛选条件

    Args:
        paper: 论文对象
        filters: 筛选配置

    Returns:
        True 表示通过筛选
    """
    # 引用数筛选
    if filters.min_citations > 0 and paper.citations < filters.min_citations:
        return False

    # 年份筛选
    if paper.year is not None:
        if filters.year_from is not None and paper.year < filters.year_from:
            return False
        if filters.year_to is not None and paper.year > filters.year_to:
            return False

    # DOI 筛选
    if filters.require_doi and not paper.doi:
        return False

    # 开放获取筛选
    if filters.open_access_only and not paper.is_open_access:
        return False

    return True
