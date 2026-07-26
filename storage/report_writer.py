#!/usr/bin/env python3
"""
论文分析报告写入器

职责：
1. 将 LLM 分析报告写入 analysis.md
2. 将 MinerU 原始解析内容复制为 full.md（修复图片路径为同级 images/）
3. 确保 images/ 目录共享于 analysis/ 下
4. 写入 meta.json（元数据、评分、缓存键）

目录结构（per-paper）：
    papers/analysis/{slug}/
        ├── analysis.md
        ├── full.md
        ├── meta.json
        └── images/
            ├── figure-1.jpg
            └── figure-2.jpg
"""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def write_analysis_report(
    analysis_result: dict,
    output_dir: Path,
    paper_metadata: Optional[dict] = None,
    mineru_md_path: Optional[Path] = None,
    mineru_images_dir: Optional[Path] = None,
    language: str = "zh",
) -> Path:
    """
    写入完整的分析报告目录。

    Args:
        analysis_result: LLMAnalyzer.analyze() 的返回字典，
                        必须包含 "report_md" 键。
        output_dir: 输出根目录（如 papers/analysis/{slug}/）。
        paper_metadata: 论文元数据（title, authors, year, venue, url 等）。
        mineru_md_path: MinerU 原始解析出的 .md 文件路径。
        mineru_images_dir: MinerU 原始解析出的图片目录路径。
        language: 语言代码 (zh/en)。

    Returns:
        最终 analysis.md 的 Path。
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    img_dir = output_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 1. 处理图片：从 MinerU 输出复制到分析目录的 images/
    if mineru_images_dir and mineru_images_dir.exists():
        _copy_images(mineru_images_dir, img_dir)
        logger.info("图片已复制到: %s", img_dir)

    # 2. 写入 analysis.md（LLM 报告）
    analysis_md = output_dir / "analysis.md"
    report_md = analysis_result.get("report_md", "")
    # 最终确保图片引用是同级目录的 wikilink
    report_md = _normalize_image_refs(report_md)
    analysis_md.write_text(report_md, encoding="utf-8")
    logger.info("分析报告已写入: %s", analysis_md)

    # 3. 写入 full.md（原始 MinerU 内容，路径修复为同级 images/）
    if mineru_md_path and mineru_md_path.exists():
        full_md = output_dir / "full.md"
        raw_text = mineru_md_path.read_text(encoding="utf-8")
        # 修复路径：{stem}/images/xxx.jpg -> images/xxx.jpg
        # 因为 full.md 现在和 images/ 在同一目录
        stem = mineru_md_path.stem
        raw_text = raw_text.replace(f"{stem}/images/", "images/")
        # 同时把标准 markdown 图片也修复为 wikilink
        raw_text = _normalize_image_refs(raw_text)
        full_md.write_text(raw_text, encoding="utf-8")
        logger.info("原始 Markdown 已复制: %s", full_md)

    # 4. 写入 meta.json
    meta = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "language": language,
        "metadata": paper_metadata or {},
        "scores": analysis_result.get("scores", {}),
        "exec_summary": analysis_result.get("exec_summary", ""),
        "tokens_used": analysis_result.get("tokens_used", 0),
    }
    meta_path = output_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("元数据已写入: %s", meta_path)

    return analysis_md


def _copy_images(src_dir: Path, dst_dir: Path) -> None:
    """复制图片，同时清理目标目录的旧残留。"""
    if dst_dir.exists():
        # 清理旧图片（避免残留）
        for f in dst_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                f.unlink()
    dst_dir.mkdir(parents=True, exist_ok=True)
    for src in src_dir.iterdir():
        if src.is_file() and src.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            shutil.copy2(src, dst_dir / src.name)


def _normalize_image_refs(text: str) -> str:
    """统一图片引用为 Obsidian wikilink。
    - ![](images/figure-1.jpg) → ![[images/figure-1.jpg|800]]
    - ![](path/to/images/figure-1.jpg) → ![[images/figure-1.jpg|800]]
    - ![[figure-1.jpg]] → ![[images/figure-1.jpg|800]]
    """
    # 1. 标准 md，路径含 images/ → 保留 images/ 及之后
    text = re.sub(
        r"!\[([^\]]*)\]\([^)]*/(images/[^)]+)\)",
        r"![[\2|800]]",
        text,
        flags=re.IGNORECASE,
    )
    # 2. 裸 wikilink 文件名 → 补 images/ 前缀
    text = re.sub(
        r"!\[\[(figure-\d+[a-z]?\.(?:jpg|jpeg|png|webp|gif))\|?(\d*)\]\]",
        r"![[images/\1|800]]",
        text,
        flags=re.IGNORECASE,
    )
    return text


def load_meta(analysis_dir: Path) -> Optional[dict]:
    """读取已存在的 meta.json。"""
    meta_path = Path(analysis_dir) / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None
