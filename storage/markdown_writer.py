"""Markdown 文件写入器（Obsidian 兼容）"""

from pathlib import Path
from datetime import datetime
from collections import defaultdict
import logging

from models.paper import Paper

logger = logging.getLogger(__name__)


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
