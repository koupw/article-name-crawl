"""历史记录管理，用于跨次去重"""

import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from models.paper import Paper

logger = logging.getLogger(__name__)

# 历史记录文件名
HISTORY_FILE = "crawled_papers.json"


def get_history_path(output_path: Path) -> Path:
    """获取历史记录文件路径

    Args:
        output_path: 输出目录路径

    Returns:
        历史记录文件路径
    """
    return output_path / HISTORY_FILE


def load_history(output_path: Path) -> dict[str, dict]:
    """加载历史记录

    Args:
        output_path: 输出目录路径

    Returns:
        历史记录字典，key 为论文唯一标识，value 为论文信息
    """
    history_path = get_history_path(output_path)
    if not history_path.exists():
        return {}

    try:
        with open(history_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"加载历史记录: {len(data)} 篇论文")
            return data
    except Exception as e:
        logger.warning(f"加载历史记录失败: {e}")
        return {}


def save_history(output_path: Path, history: dict[str, dict]) -> None:
    """保存历史记录

    Args:
        output_path: 输出目录路径
        history: 历史记录字典
    """
    output_path.mkdir(parents=True, exist_ok=True)
    history_path = get_history_path(output_path)

    try:
        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info(f"保存历史记录: {len(history)} 篇论文")
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")


def get_paper_key(paper: Paper) -> str:
    """获取论文的唯一标识

    优先级: DOI > arXiv ID > 标题（标准化）

    Args:
        paper: 论文对象

    Returns:
        唯一标识字符串
    """
    if paper.doi:
        return f"doi:{paper.doi.lower().strip()}"
    if paper.arxiv_id:
        return f"arxiv:{paper.arxiv_id.strip()}"
    # 使用标准化标题作为标识
    from utils.dedup import normalize_title
    return f"title:{normalize_title(paper.title)}"


def deduplicate_with_history(
    papers: list[Paper],
    output_path: Path,
) -> tuple[list[Paper], dict[str, dict]]:
    """与历史记录去重

    Args:
        papers: 论文列表
        output_path: 输出目录路径

    Returns:
        (新论文列表, 更新后的历史记录)
    """
    history = load_history(output_path)
    new_papers = []

    for paper in papers:
        key = get_paper_key(paper)
        if key not in history:
            new_papers.append(paper)
            # 添加到历史记录
            history[key] = {
                "title": paper.title,
                "source": paper.source,
                "domain": paper.domain,
                "crawled_at": datetime.now().isoformat(),
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
            }

    logger.info(f"跨次去重: {len(papers)} -> {len(new_papers)} 篇新论文")
    return new_papers, history


def clear_history(output_path: Path) -> None:
    """清除历史记录

    Args:
        output_path: 输出目录路径
    """
    history_path = get_history_path(output_path)
    if history_path.exists():
        history_path.unlink()
        logger.info("历史记录已清除")
