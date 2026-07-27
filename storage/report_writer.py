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

import base64
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
    report_md = _normalize_image_refs(report_md)
    report_md = _inject_figures(report_md, img_dir)
    analysis_md.write_text(report_md, encoding="utf-8")
    logger.info("分析报告已写入: %s", analysis_md)

    # 3. 写入 full.md（原始 MinerU 内容，路径修复为同级 images/）
    if mineru_md_path and mineru_md_path.exists():
        full_md = output_dir / "full.md"
        raw_text = mineru_md_path.read_text(encoding="utf-8")
        stem = mineru_md_path.stem
        raw_text = raw_text.replace(f"{stem}/images/", "images/")
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
    """统一图片引用为 note-relative 标准 markdown（Obsidian 可靠格式）。

    - ![](images/figure-1.jpg) → 保持原样
    - ![](path/to/images/figure-1.jpg) → ![](images/figure-1.jpg)
    - ![[figure-1.jpg]] → ![Figure 1](images/figure-1.jpg)
    - ![[anything/images/figure-1.jpg|800]] → ![Figure 1](images/figure-1.jpg)
    """
    # 1. 标准 md 带前缀路径 → 提取 images/ 相对路径
    text = re.sub(
        r"!\[([^\]]*)\]\((?:[^)]*?/)?(images/figure-[^)]+)\)",
        r"![\1](\2)",
        text,
        flags=re.IGNORECASE,
    )
    # 2. 裸 wikilink 文件名 → 标准 md（支持 figure-3-7 等多段编号）
    text = re.sub(
        r"!\[\[figure-([\d-]+[a-z]?)\.(jpg|jpeg|png|webp|gif)\|?\d*\]\]",
        r"![Figure \1](images/figure-\1.\2)",
        text,
        flags=re.IGNORECASE,
    )
    # 3. wikilink 含 images/ 路径 → 标准 md
    text = re.sub(
        r"!\[\[(?:.*?/)?images/(figure-[\d-]+[a-z]?)\.(jpg|jpeg|png|webp|gif)\|?\d*\]\]",
        r"![Figure \1](images/figure-\1.\2)",
        text,
        flags=re.IGNORECASE,
    )
    # 4. 清理旧残留：![Figure figure-1] → ![Figure 1]
    text = re.sub(
        r"!\[Figure figure-([\d-]+[a-z]?)\.(\w+)\]\((?:[^)]*?/)?images/figure-[^)]+\)",
        r"![Figure \1](images/figure-\1.\2)",
        text,
        flags=re.IGNORECASE,
    )
    # 5. 去除图片引用周围的 backtick（LLM 偶尔会输出 `![...](...)` 代码块）
    text = re.sub(r"`(!\[(?:[^\]]*)\]\(images/[^)]+\))`", r"\1", text)
    text = re.sub(r"`(!\[\[.*?\]\])`", r"\1", text)
    return text


def _inject_figures(report_md: str, img_dir: Path) -> str:
    """将 images/ 目录中的图片注入到分析报告中。

    策略：
    1. 扫描报告中已有的图片引用，避免重复注入
    2. 扫描报告中的图号提及（Fig. N / Figure N / 图N），
       在首次提及的段落后插入对应图片
    3. 未被提及的图片追加到"论文图表"附录
    """
    if not img_dir.exists():
        return report_md

    # 收集所有图片文件，按序号排序（支持 figure-3-7 等多段编号）
    img_files: dict[str, str] = {}  # figure_id -> filename
    for f in sorted(img_dir.iterdir()):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            continue
        m = re.match(r"figure-([\d-]+[a-z]?)", f.stem, re.IGNORECASE)
        if m:
            img_files[m.group(1)] = f.name

    if not img_files:
        return report_md

    # 查找报告中已存在的图片引用（标准 md 或 wikilink）
    existing = set()
    for m in re.finditer(
        r"!\[(?:[^\]]*)\]\((?:[^)]*/)?images/figure-([\d-]+[a-z]?)\.\w+\)"
        r"|!\[\[(?:.*?/)?(?:images/)?figure-([\d-]+[a-z]?)\.\w+\|?\d*\]\]",
        report_md, re.IGNORECASE,
    ):
        num = m.group(1) or m.group(2)
        existing.add(num)

    # 查找报告中提及的图号位置（支持 Fig. 3-7 等多段编号）
    fig_pattern = re.compile(
        r"(?:Figure|Fig\.?|图)\s*(\d+(?:-\d+)*[a-z]?)(?!\d)",
        re.IGNORECASE,
    )
    fig_mentions: dict[str, int] = {}  # fig_id -> paragraph index
    paragraphs = report_md.split("\n\n")
    for p_idx, para in enumerate(paragraphs):
        for m in fig_pattern.finditer(para):
            fig_id = m.group(1)
            if fig_id in img_files and fig_id not in fig_mentions:
                fig_mentions[fig_id] = p_idx

    # 反向遍历插入图片（从后往前，避免索引偏移）
    def _sort_key(fid: str) -> tuple:
        parts = fid.split("-")
        return tuple(int(p) if p.isdigit() else p for p in parts)

    inserted: set[str] = set()
    for fig_id in sorted(img_files.keys(), key=_sort_key, reverse=True):
        if fig_id in existing:
            continue
        # note-relative 标准 markdown（Obsidian 可靠格式）
        md_ref = f"![Figure {fig_id}](images/{img_files[fig_id]})"
        caption = f"*Figure {fig_id}*"
        fig_block = f"\n\n{md_ref}\n{caption}"

        if fig_id in fig_mentions:
            p_idx = fig_mentions[fig_id]
            paragraphs[p_idx] = paragraphs[p_idx].rstrip() + fig_block
        else:
            inserted.add(fig_id)

    result = "\n\n".join(paragraphs)

    # 未被提及的图片 → 追加"论文图表"附录
    unmentioned = [fid for fid in img_files
                   if fid not in existing and fid not in fig_mentions]
    if unmentioned:
        appendix = "\n\n---\n\n## 论文图表\n\n"
        for fig_id in sorted(unmentioned, key=_sort_key):
            md_ref = f"![Figure {fig_id}](images/{img_files[fig_id]})"
            caption = f"*Figure {fig_id}*"
            appendix += f"{md_ref}\n{caption}\n\n"
        result += appendix

    return result


def load_meta(analysis_dir: Path) -> Optional[dict]:
    """读取已存在的 meta.json。"""
    meta_path = Path(analysis_dir) / "meta.json"
    if meta_path.exists():
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def md_with_inline_images(md_text: str, base_dir: Path) -> str:
    """将 markdown 中 `images/` 相对路径图片引用转为 base64 data URI。

    用于 Streamlit 等 Web 环境，因为 st.markdown() 无法直接访问本地文件。
    在 Obsidian / VS Code 等本地编辑器中查看时不需要此转换。

    Args:
        md_text: Markdown 文本
        base_dir: 图片路径的基准目录（即 .md 文件所在目录）

    Returns:
        转换后的 Markdown（本地图片 → base64 inline）
    """
    def _replace(match: re.Match) -> str:
        alt = match.group(1)
        img_rel = match.group(2)
        full_path = (base_dir / img_rel).resolve()
        if not full_path.exists():
            return match.group(0)
        suffix = full_path.suffix.lower().lstrip(".")
        mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp", "gif": "gif"}
        mime = mime_map.get(suffix, "jpeg")
        try:
            with open(full_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"![{alt}](data:image/{mime};base64,{b64})"
        except OSError:
            return match.group(0)

    return re.sub(
        r"!\[([^\]]*)\]\((images/[^)]+)\)",
        _replace,
        md_text,
        flags=re.IGNORECASE,
    )
