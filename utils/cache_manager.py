#!/usr/bin/env python3
"""
分析缓存管理器

避免对同一篇论文重复调用 LLM（重复计费）。
缓存键基于输入内容的 SHA-256 哈希（PDF 文件哈希或 Markdown 文本哈希）。

缓存目录：
    {analysis_dir}/.cache/
        ├── <hash_prefix>/
        │   └── meta.json   (原始 meta.json 的软链接或副本)

当命中缓存时，直接将缓存目录的内容硬链接/复制到目标输出目录，
避免重复生成。
"""

import hashlib
import json
import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _file_hash(filepath: Path) -> str:
    """计算文件 SHA-256。"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _text_hash(text: str) -> str:
    """计算文本 SHA-256。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cache_dir(analysis_dir: Path) -> Path:
    """获取缓存根目录（_cache/）。"""
    return Path(analysis_dir).resolve() / "_cache"


def check_cache(
    source_path: Optional[Path] = None,
    md_text: Optional[str] = None,
    analysis_dir: Path = Path("papers/analysis"),
) -> Optional[Path]:
    """
    检查是否已有缓存分析结果。

    Args:
        source_path: 原始文件路径（PDF 或 Markdown）。
        md_text: 原始 Markdown 文本（与 source_path 二选一）。
        analysis_dir: 分析输出根目录。

    Returns:
        若命中缓存，返回缓存的论文分析目录 Path；否则返回 None。
    """
    if source_path:
        h = _file_hash(source_path)
    elif md_text:
        h = _text_hash(md_text)
    else:
        return None

    cache_root = get_cache_dir(analysis_dir)
    cache_entry = cache_root / h[:2] / h
    meta_path = cache_entry / "meta.json"

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            logger.info("缓存命中: %s -> %s", h[:16], cache_entry)
            return cache_entry
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_cache(
    result_dir: Path,
    source_path: Optional[Path] = None,
    md_text: Optional[str] = None,
    analysis_dir: Path = Path("papers/analysis"),
) -> None:
    """
    将分析结果目录保存到缓存。

    Args:
        result_dir: 刚生成的分析结果目录（含 analysis.md, meta.json 等）。
        source_path: 原始文件路径。
        md_text: 原始 Markdown 文本。
        analysis_dir: 分析输出根目录。
    """
    if source_path:
        h = _file_hash(source_path)
    elif md_text:
        h = _text_hash(md_text)
    else:
        return

    cache_root = get_cache_dir(analysis_dir)
    cache_entry = cache_root / h[:2] / h
    cache_entry.mkdir(parents=True, exist_ok=True)

    # 复制 result_dir 下所有文件到缓存（跳过 .cache 自身）
    for src in Path(result_dir).iterdir():
        if src.name == ".cache":
            continue
        dst = cache_entry / src.name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    logger.info("缓存已保存: %s -> %s", h[:16], cache_entry)


def restore_from_cache(
    cache_entry: Path,
    target_dir: Path,
) -> None:
    """将缓存内容复制/恢复到目标分析目录。"""
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for src in cache_entry.iterdir():
        dst = target_dir / src.name
        if src.is_dir():
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    logger.info("缓存恢复完成: %s", target_dir)
