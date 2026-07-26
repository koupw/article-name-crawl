"""历史记录管理器（拆分索引 + 翻译缓存）

将单一的 crawled_papers.json 拆分为：
- history_index.json: 去重索引（DOI/arXiv ID/标题 hash -> 元数据）
- translation_cache.json: 翻译缓存（key -> title_zh）

职责分离后：
- 索引有大小上限，超限自动清理最旧条目
- 翻译缓存长期保留（翻译结果不过时）
- 自动迁移旧格式 crawled_papers.json
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from models.paper import Paper
from utils.dedup import normalize_title

logger = logging.getLogger(__name__)

# 文件名
INDEX_FILE = "history_index.json"
CACHE_FILE = "translation_cache.json"
LEGACY_FILE = "crawled_papers.json"

# 索引大小上限（默认 50MB）
MAX_INDEX_SIZE_BYTES = 50 * 1024 * 1024


def _get_key(paper: Paper) -> str:
    """论文唯一标识"""
    if paper.doi:
        return f"doi:{paper.doi.lower().strip()}"
    if paper.arxiv_id:
        return f"arxiv:{paper.arxiv_id.strip()}"
    return f"title:{normalize_title(paper.title)}"


class HistoryManager:
    """历史记录管理器"""

    def __init__(self, output_path: Path, max_size: int = MAX_INDEX_SIZE_BYTES):
        self.output_path = output_path
        self.max_size = max_size
        self._index: dict[str, dict] = {}
        self._cache: dict[str, str] = {}
        self._load()

    # ------------------------------------------------------------------
    # 内部加载/保存
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """加载历史记录。优先新格式，兼容旧格式自动迁移。"""
        index_path = self.output_path / INDEX_FILE
        cache_path = self.output_path / CACHE_FILE
        legacy_path = self.output_path / LEGACY_FILE

        # 1. 新格式存在时直接加载
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.warning("加载 history_index 失败: %s", e)
                self._index = {}

        if cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning("加载 translation_cache 失败: %s", e)
                self._cache = {}

        if self._index:
            logger.info("加载历史索引: %d 篇，翻译缓存: %d 条", len(self._index), len(self._cache))
            return

        # 2. 新格式不存在但旧格式存在 -> 自动迁移
        if legacy_path.exists():
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    legacy = json.load(f)
                self._migrate_from_legacy(legacy)
                logger.info("历史记录迁移完成: %d 篇 -> 新格式", len(self._index))
            except Exception as e:
                logger.warning("迁移旧历史记录失败: %s", e)

    def _save(self) -> None:
        """保存两个文件"""
        self.output_path.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.output_path / INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(self._index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存 history_index 失败: %s", e)

        try:
            with open(self.output_path / CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("保存 translation_cache 失败: %s", e)

    def _migrate_from_legacy(self, legacy: dict) -> None:
        """从旧格式 crawled_papers.json 迁移"""
        for key, entry in legacy.items():
            # 拆分元数据和翻译
            self._index[key] = {
                "title": entry.get("title", ""),
                "source": entry.get("source", ""),
                "domain": entry.get("domain", ""),
                "crawled_at": entry.get("crawled_at", datetime.now().isoformat()),
                "doi": entry.get("doi"),
                "arxiv_id": entry.get("arxiv_id"),
            }
            title_zh = entry.get("title_zh")
            if title_zh:
                self._cache[key] = title_zh
        self._save()
        # 可选：迁移后删除旧文件（保守做法：保留，让用户手动确认后删除）
        # (self.output_path / LEGACY_FILE).rename(self.output_path / f"{LEGACY_FILE}.backup")

    # ------------------------------------------------------------------
    # 公共接口（与旧 utils/history.py 对齐）
    # ------------------------------------------------------------------

    def has(self, paper: Paper) -> bool:
        """论文是否已在历史记录中"""
        return _get_key(paper) in self._index

    def get_cached_translation(self, paper: Paper) -> Optional[str]:
        """获取缓存的中文标题"""
        return self._cache.get(_get_key(paper))

    def add(self, paper: Paper) -> None:
        """添加论文到历史索引"""
        key = _get_key(paper)
        self._index[key] = {
            "title": paper.title,
            "source": paper.source,
            "domain": paper.domain,
            "crawled_at": datetime.now().isoformat(),
            "doi": paper.doi,
            "arxiv_id": paper.arxiv_id,
        }
        if paper.title_zh:
            self._cache[key] = paper.title_zh
        self._cleanup_if_needed()
        self._save()

    def update_translation(self, paper: Paper) -> None:
        """更新翻译缓存"""
        if not paper.title_zh:
            return
        key = _get_key(paper)
        self._cache[key] = paper.title_zh
        self._save()

    def to_legacy_dict(self) -> dict[str, dict]:
        """导出兼容旧格式的字典（用于过渡期的 utils/history.py 调用）"""
        result = {}
        for key, meta in self._index.items():
            entry = dict(meta)
            if key in self._cache:
                entry["title_zh"] = self._cache[key]
            result[key] = entry
        return result

    def clear(self) -> None:
        """清除所有历史记录（删除文件）"""
        self._index.clear()
        self._cache.clear()
        for fname in (INDEX_FILE, CACHE_FILE):
            fpath = self.output_path / fname
            if fpath.exists():
                fpath.unlink()
        logger.info("历史记录已清除")

    # ------------------------------------------------------------------
    # 清理策略
    # ------------------------------------------------------------------

    def _cleanup_if_needed(self) -> None:
        """索引超过大小上限时清理最旧条目"""
        import sys
        index_size = sys.getsizeof(json.dumps(self._index, ensure_ascii=False))
        if index_size < self.max_size:
            return

        # 按 crawled_at 排序，删除最旧的 20%
        sorted_keys = sorted(
            self._index.keys(),
            key=lambda k: self._index[k].get("crawled_at", ""),
        )
        to_remove = int(len(sorted_keys) * 0.2)
        for key in sorted_keys[:to_remove]:
            del self._index[key]
            # 不删除翻译缓存（翻译结果可长期保留）
        logger.info("历史索引超限清理: 删除 %d 条最旧记录", to_remove)
