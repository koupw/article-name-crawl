"""Markdown 文件写入器（Obsidian 兼容）"""

from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Optional
import logging
import re
import yaml

from models.paper import Paper

logger = logging.getLogger(__name__)

# 索引文件名
INDEX_FILE = "_index.md"


def write_markdown(
    papers: list[Paper],
    output_path: Path,
    domain: str,
    language: str = "zh",
) -> Path:
    """将论文列表写入 Markdown 文件

    Args:
        papers: 论文列表
        output_path: 输出目录路径
        domain: 研究领域名称
        language: 语言 (zh/en)

    Returns:
        输出文件路径
    """
    # 确保输出目录存在
    output_path.mkdir(parents=True, exist_ok=True)

    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{domain.replace(' ', '_')}_{timestamp}.md"
    file_path = output_path / filename

    # 按数据源分组
    by_source = defaultdict(list)
    for paper in papers:
        by_source[paper.source].append(paper)

    # 统计信息
    source_counts = {source: len(ps) for source, ps in by_source.items()}

    # 生成内容
    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f"title: {domain} Papers")
    lines.append(f"date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"domain: {domain}")
    lines.append(f"total: {len(papers)}")
    lines.append("sources:")
    for source, count in source_counts.items():
        lines.append(f"  {source}: {count}")
    lines.append("---")
    lines.append("")

    # 标题
    if language == "zh":
        lines.append(f"# {domain} 论文列表")
        lines.append("")
        lines.append(f"共找到 **{len(papers)}** 篇相关论文")
    else:
        lines.append(f"# {domain} Paper List")
        lines.append("")
        lines.append(f"Found **{len(papers)}** related papers")
    lines.append("")

    # 源名称映射
    source_names = {
        "arxiv": "arXiv",
        "semantic_scholar": "Semantic Scholar",
        "google_scholar": "Google Scholar",
        "openalex": "OpenAlex",
        "ieee_xplore": "IEEE Xplore",
    }

    # 按数据源输出
    for source, source_papers in by_source.items():
        source_name = source_names.get(source, source)
        lines.append(f"## {source_name} ({len(source_papers)} 篇)")
        lines.append("")

        # 按年份分组
        by_year = defaultdict(list)
        for paper in source_papers:
            year = paper.year or "Unknown"
            by_year[year].append(paper)

        for year in sorted(by_year.keys(), reverse=True):
            year_papers = by_year[year]
            lines.append(f"### {year}")
            lines.append("")
            lines.append("| # | 标题 | 中文标题 | 作者 | 日期 | 链接 |")
            lines.append("|---|------|----------|------|------|------|")

            for i, paper in enumerate(year_papers, 1):
                # 标题（带链接）
                title_display = paper.title[:60] + "..." if len(paper.title) > 60 else paper.title
                if paper.url:
                    title_cell = f"[{title_display}]({paper.url})"
                else:
                    title_cell = title_display

                # 中文标题
                if paper.title_zh:
                    title_zh_display = paper.title_zh[:40] + "..." if len(paper.title_zh) > 40 else paper.title_zh
                    title_zh_cell = title_zh_display
                else:
                    title_zh_cell = "-"

                # 作者
                authors_cell = paper.authors_str

                # 日期
                date_cell = paper.date_str

                # 链接
                links = []
                if paper.pdf_url:
                    links.append(f"[PDF]({paper.pdf_url})")
                if paper.doi:
                    links.append(f"[DOI](https://doi.org/{paper.doi})")
                links_cell = " / ".join(links) if links else "-"

                lines.append(f"| {i} | {title_cell} | {title_zh_cell} | {authors_cell} | {date_cell} | {links_cell} |")

            lines.append("")

    # 写入文件
    content = "\n".join(lines)
    file_path.write_text(content, encoding="utf-8")

    logger.info(f"已写入文件: {file_path}")
    return file_path


def write_index(output_path: Path) -> Optional[Path]:
    """生成输出目录索引文件 _index.md

    扫描输出目录下所有论文列表 Markdown 文件，
    解析 frontmatter 汇总为索引页。

    Args:
        output_path: 输出目录路径

    Returns:
        索引文件路径，无文件时返回 None
    """
    output_path.mkdir(parents=True, exist_ok=True)

    # 收集所有论文列表文件（排除索引本身）
    md_files = sorted(output_path.glob("*_*.md"))
    index_path = output_path / INDEX_FILE
    md_files = [f for f in md_files if f.name != INDEX_FILE]

    if not md_files:
        return None

    # 解析每个文件的 frontmatter
    entries = []
    for file_path in md_files:
        info = _parse_frontmatter(file_path)
        info["file"] = file_path.name
        info["path"] = file_path
        entries.append(info)

    # 按日期排序（最新在前）
    entries.sort(key=lambda e: e.get("date", ""), reverse=True)

    # 生成索引内容
    lines = []
    lines.append("---")
    lines.append("title: 论文列表索引")
    lines.append(f"date: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"files: {len(entries)}")
    lines.append("---")
    lines.append("")
    lines.append("# 📚 论文列表索引")
    lines.append("")
    lines.append(f"共 **{len(entries)}** 个列表文件")
    lines.append("")

    for entry in entries:
        domain = entry.get("domain", "Unknown")
        total = entry.get("total", "?")
        date = entry.get("date", "?")
        file_name = entry["file"]

        lines.append(f"### [{domain}]({file_name})")
        lines.append("")
        lines.append(f"- **论文数**: {total}")
        lines.append(f"- **日期**: {date}")
        # 显示来源
        sources = entry.get("sources", {})
        if sources:
            source_summary = ", ".join(f"{src}: {cnt}" for src, cnt in sources.items())
            lines.append(f"- **数据源**: {source_summary}")
        lines.append("")

    content = "\n".join(lines)
    index_path.write_text(content, encoding="utf-8")

    logger.info(f"已更新索引文件: {index_path}")
    return index_path


def _parse_frontmatter(file_path: Path) -> dict:
    """解析 Markdown 文件的 frontmatter

    Args:
        file_path: Markdown 文件路径

    Returns:
        frontmatter 字典，包含 title, date, domain, total, sources 等字段
    """
    info = {
        "title": "",
        "date": "",
        "domain": "",
        "total": 0,
        "sources": {},
    }

    try:
        content = file_path.read_text(encoding="utf-8")

        # 匹配 frontmatter 块
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            info["title"] = file_path.stem
            return info

        frontmatter = match.group(1)

        # 使用 PyYAML 解析 frontmatter（取代手写逐行解析）
        data = yaml.safe_load(frontmatter)
        if isinstance(data, dict):
            info["title"] = data.get("title", file_path.stem) or file_path.stem
            info["date"] = data.get("date", "") or ""
            info["domain"] = data.get("domain", "") or ""
            info["total"] = data.get("total", 0) or 0
            info["sources"] = data.get("sources", {}) or {}

    except Exception as e:
        logger.warning("解析 frontmatter 失败 %s: %s", file_path.name, e)
        info["title"] = file_path.stem

    return info
