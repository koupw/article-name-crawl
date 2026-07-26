"""历史记录管理，用于跨次去重（底层已拆分为 history_index + translation_cache）

对外接口保持完全不变，内部自动处理新旧格式兼容。
"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from models.paper import Paper
from storage.history_manager import HistoryManager, LEGACY_FILE

logger = logging.getLogger(__name__)

# 保留旧常量以兼容可能的直接引用
HISTORY_FILE = LEGACY_FILE


def _resolve_path(output_path: Path) -> Path:
    """将输出路径指向 _output/ 子目录（与 markdown_writer 保持一致）。"""
    p = output_path / "_output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_history_path(output_path: Path) -> Path:
    """获取历史记录文件路径"""
    return _resolve_path(output_path) / LEGACY_FILE


def load_history(output_path: Path) -> dict[str, dict]:
    """加载历史记录（兼容旧格式，自动读取新格式合成 legacy dict）

    Args:
        output_path: 输出目录路径

    Returns:
        历史记录字典（兼容旧格式，含 title_zh）
    """
    mgr = HistoryManager(_resolve_path(output_path))
    legacy = mgr.to_legacy_dict()
    if legacy:
        logger.info("加载历史记录: %d 篇论文", len(legacy))
    return legacy


def save_history(output_path: Path, history: dict[str, dict]) -> None:
    """保存历史记录（将 legacy dict 拆分写入新格式双文件）

    Args:
        output_path: 输出目录路径
        history: 历史记录字典（含 title_zh）
    """
    output_path.mkdir(parents=True, exist_ok=True)
    mgr = HistoryManager(_resolve_path(output_path))

    # 同步 legacy dict 的内容到 manager
    for key, entry in history.items():
        mgr._index[key] = {
            "title": entry.get("title", ""),
            "source": entry.get("source", ""),
            "domain": entry.get("domain", ""),
            "crawled_at": entry.get("crawled_at", datetime.now().isoformat()),
            "doi": entry.get("doi"),
            "arxiv_id": entry.get("arxiv_id"),
        }
        title_zh = entry.get("title_zh")
        if title_zh:
            mgr._cache[key] = title_zh

    mgr._save()
    logger.info("保存历史记录: %d 篇论文", len(history))


def get_paper_key(paper: Paper) -> str:
    """获取论文的唯一标识

    优先级: DOI > arXiv ID > 标题（标准化）
    """
    if paper.doi:
        return f"doi:{paper.doi.lower().strip()}"
    if paper.arxiv_id:
        return f"arxiv:{paper.arxiv_id.strip()}"
    from utils.dedup import normalize_title
    return f"title:{normalize_title(paper.title)}"


def deduplicate_with_history(
    papers: list[Paper],
    output_path: Path,
) -> tuple[list[Paper], dict[str, dict]]:
    """与历史记录去重

    对于已历史记录的论文，恢复缓存的翻译结果到 paper.title_zh。
    对于新论文，预创建历史记录条目（不含翻译，翻译后需调用 update_history_translations）。

    Args:
        papers: 论文列表
        output_path: 输出目录路径

    Returns:
        (新论文列表, 更新后的历史记录 legacy dict)
    """
    mgr = HistoryManager(_resolve_path(output_path))
    new_papers = []
    history = mgr.to_legacy_dict()

    for paper in papers:
        key = get_paper_key(paper)
        if key in history:
            # 从历史记录恢复缓存的翻译
            cached_zh = history[key].get("title_zh")
            if cached_zh:
                paper.title_zh = cached_zh
        else:
            new_papers.append(paper)
            # 预创建历史条目（不含 title_zh，翻译后更新）
            history[key] = {
                "title": paper.title,
                "source": paper.source,
                "domain": paper.domain,
                "crawled_at": datetime.now().isoformat(),
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
            }

    logger.info("跨次去重: %d -> %d 篇新论文", len(papers), len(new_papers))
    return new_papers, history


def update_history_translations(history: dict[str, dict], papers: list[Paper]) -> None:
    """将翻译结果更新到历史记录

    Args:
        history: 历史记录字典（由 deduplicate_with_history 返回）
        papers: 已翻译的论文列表
    """
    for paper in papers:
        if not paper.title_zh:
            continue
        key = get_paper_key(paper)
        if key in history:
            history[key]["title_zh"] = paper.title_zh


def clear_history(output_path: Path) -> None:
    """清除历史记录（同时清理新格式的双文件）"""
    mgr = HistoryManager(_resolve_path(output_path))
    mgr.clear()
    # 同时清理可能存在的旧文件
    legacy = get_history_path(output_path)
    if legacy.exists():
        legacy.unlink()
        logger.info("旧历史记录文件已清除")
