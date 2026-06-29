"""FMCW 论文名称爬取工具 - CLI 入口"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from config.loader import load_config, validate_config, get_domains, init_config
from models.paper import Paper
from crawlers.arxiv_crawler import ArxivCrawler
from crawlers.semantic_scholar import SemanticScholarCrawler
from crawlers.google_scholar import GoogleScholarCrawler
from crawlers.openalex_crawler import OpenAlexCrawler
from crawlers.ieee_xplore_crawler import IEEEXploreCrawler
from utils.dedup import deduplicate
from utils.filter import filter_papers
from utils.history import deduplicate_with_history, save_history, clear_history, update_history_translations
from utils.paper_translator import translate_paper_titles
from utils.logger import setup_logger
from storage.markdown_writer import write_markdown, write_index

logger = logging.getLogger(__name__)
console = Console()

# 可用数据源
AVAILABLE_SOURCES = ["arxiv", "semantic_scholar", "google_scholar", "openalex", "ieee_xplore"]


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="学术论文爬取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                                    # 爬取所有领域
  python main.py --domain "FMCW Laser Ranging"      # 爬取指定领域
  python main.py --sources arxiv,semantic_scholar    # 指定数据源
  python main.py --max-results 100                   # 每个数据源最多 100 篇
  python main.py --verbose                           # 详细日志
        """,
    )

    parser.add_argument(
        "--config",
        default="research_interests.yaml",
        help="配置文件路径 (默认: research_interests.yaml)",
    )
    parser.add_argument(
        "--domain",
        help="指定研究领域 (默认: 配置文件中优先级最高的领域)",
    )
    parser.add_argument(
        "--sources",
        help=f"数据源，逗号分隔 (可选: {','.join(AVAILABLE_SOURCES)})",
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=50,
        help="每个数据源最大结果数 (默认: 50)",
    )
    parser.add_argument(
        "--output",
        help="输出目录 (默认: 配置文件中的 vault_path/papers_dir)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式，不写入文件",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="不使用历史记录（禁用跨次去重）",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="清除历史记录",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="生成默认配置文件 research_interests.yaml",
    )
    parser.add_argument(
        "--min-citations",
        type=int,
        help="最低引用数（覆盖配置文件）",
    )
    parser.add_argument(
        "--year-from",
        type=int,
        help="起始年份（覆盖配置文件）",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="不翻译论文标题",
    )

    return parser.parse_args()


def get_crawlers(
    sources: list[str],
    config,
) -> list:
    """初始化爬虫实例

    Args:
        sources: 数据源列表
        config: 应用配置

    Returns:
        爬虫实例列表
    """
    crawlers = []

    for source in sources:
        if source == "arxiv":
            crawlers.append(ArxivCrawler(excluded_keywords=config.excluded_keywords))
        elif source == "semantic_scholar":
            crawlers.append(
                SemanticScholarCrawler(
                    api_key=config.semantic_scholar_api_key if config.semantic_scholar_api_key else None,
                    excluded_keywords=config.excluded_keywords,
                )
            )
        elif source == "google_scholar":
            crawlers.append(GoogleScholarCrawler(excluded_keywords=config.excluded_keywords))
        elif source == "openalex":
            crawlers.append(
                OpenAlexCrawler(
                    email=config.openalex_email if config.openalex_email else None,
                    excluded_keywords=config.excluded_keywords,
                )
            )
        elif source == "ieee_xplore":
            if not config.ieee_api_key:
                logger.warning("IEEE Xplore 需要 API Key，跳过该数据源")
                continue
            crawlers.append(
                IEEEXploreCrawler(
                    api_key=config.ieee_api_key,
                    excluded_keywords=config.excluded_keywords,
                )
            )
        else:
            logger.warning(f"未知数据源: {source}")

    return crawlers


def _crawl_single(
    crawler,
    keywords: list[str],
    categories: list[str],
    max_results: int,
    domain: str,
) -> list[Paper]:
    """单个爬虫的爬取任务（在线程池中执行）"""
    return list(
        crawler.search(
            keywords=keywords,
            categories=categories,
            max_results=max_results,
            domain=domain,
        )
    )


def crawl_papers(
    crawlers: list,
    keywords: list[str],
    categories: list[str],
    domain: str,
    max_results: int,
) -> list[Paper]:
    """并发爬取论文

    使用 ThreadPoolExecutor 并发爬取所有数据源。
    单个爬虫失败不影响其他数据源。

    Args:
        crawlers: 爬虫列表
        keywords: 关键词列表
        categories: 分类列表
        domain: 研究领域
        max_results: 每个数据源最大结果数

    Returns:
        论文列表
    """
    all_papers = []

    with ThreadPoolExecutor(max_workers=len(crawlers)) as executor:
        future_map = {
            executor.submit(
                _crawl_single,
                c,
                keywords,
                categories,
                max_results,
                domain,
            ): c
            for c in crawlers
        }

        for future in as_completed(future_map):
            crawler = future_map[future]
            source_name = crawler.get_name()
            try:
                papers = future.result()
                all_papers.extend(papers)
                console.print(f"[green]  {source_name}: 获取 {len(papers)} 篇论文[/green]")
            except Exception as e:
                logger.error("%s 爬取失败: %s", source_name, e)
                console.print(f"[red]  {source_name}: 爬取失败 - {e}[/red]")

    return all_papers


def process_domain(
    domain_config,
    config,
    args,
    crawlers: list,
    output_path: Path,
) -> Optional[Path]:
    """处理单个研究领域的完整流水线

    爬取 → 去重 → 筛选 → 跨次去重 → 翻译 → 写入

    Args:
        domain_config: 研究领域配置
        config: 应用配置
        args: 命令行参数
        crawlers: 爬虫实例列表（已在外部创建）
        output_path: 输出目录

    Returns:
        输出文件路径，无新论文时返回 None
    """
    console.print(f"\n[bold cyan]处理领域: {domain_config.name}[/bold cyan]")
    console.print(f"关键词数量: {len(domain_config.keywords)}")
    console.print(f"arXiv 分类: {', '.join(domain_config.arxiv_categories)}")

    # 爬取论文
    with console.status("[bold green]正在爬取论文..."):
        all_papers = crawl_papers(
            crawlers=crawlers,
            keywords=domain_config.keywords,
            categories=domain_config.arxiv_categories,
            domain=domain_config.name,
            max_results=args.max_results,
        )
    console.print(f"[bold]共爬取 {len(all_papers)} 篇论文[/bold]")

    if not all_papers:
        console.print("[yellow]未爬取到任何论文，跳过后续处理[/yellow]")
        return None

    # 单次运行内去重
    console.print("[bold]正在去重...[/bold]")
    unique_papers = deduplicate(all_papers)
    console.print(f"[bold]单次去重后: {len(unique_papers)} 篇论文[/bold]")

    # 质量筛选
    console.print("[bold]正在质量筛选...[/bold]")
    unique_papers = filter_papers(unique_papers, config.filters)
    console.print(f"[bold]筛选后: {len(unique_papers)} 篇论文[/bold]")

    if not unique_papers:
        console.print("[yellow]筛选后无可用论文[/yellow]")
        return None

    if args.dry_run:
        console.print("\n[yellow]干跑模式，不写入文件[/yellow]")
        for i, paper in enumerate(unique_papers[:10], 1):
            console.print(f"  {i}. {paper.title}")
        if len(unique_papers) > 10:
            console.print(f"  ... 还有 {len(unique_papers) - 10} 篇")
        return None

    # 跨次去重（在翻译之前，避免翻译已爬取的论文）
    history = {}  # 确保 history 变量存在
    if not args.no_history:
        console.print("[bold]正在跨次去重...[/bold]")
        unique_papers, history = deduplicate_with_history(unique_papers, output_path)
        console.print(f"[bold]跨次去重后: {len(unique_papers)} 篇新论文[/bold]")
        if not unique_papers:
            console.print("[yellow]所有论文已在历史记录中，无需写入[/yellow]")
            return None

    # 翻译论文标题
    if not args.no_translate and unique_papers:
        console.print("[bold]正在翻译论文标题...[/bold]")
        unique_papers = translate_paper_titles(unique_papers)
        console.print("[bold]翻译完成[/bold]")
        if not args.no_history:
            update_history_translations(history, unique_papers)

    # 写入文件
    console.print("[bold]正在写入文件...[/bold]")
    try:
        file_path = write_markdown(
            papers=unique_papers,
            output_path=output_path,
            domain=domain_config.name,
            language=config.language,
        )
        console.print(f"[bold green]完成！文件已保存到: {file_path}[/bold green]")

        if not args.no_history:
            save_history(output_path, history)
            console.print(f"[dim]历史记录已更新: {len(history)} 篇论文[/dim]")

        return file_path
    except Exception as e:
        logger.error("写入文件失败: %s", e)
        console.print(f"[red]写入文件失败: {e}[/red]")
        return None


def main():
    """主函数"""
    args = parse_args()

    # 配置日志
    setup_logger(verbose=args.verbose)

    # 初始化配置（不执行爬取）
    if args.init:
        init_config(args.config)
        return

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        console.print(f"[red]错误: {e}[/red]")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]配置错误: {e}[/red]")
        sys.exit(1)

    # 验证配置
    config_warnings = validate_config(config)
    for warning in config_warnings:
        console.print(f"[yellow]配置警告: {warning}[/yellow]")

    # 获取研究领域列表
    try:
        domains = get_domains(config, args.domain)
    except ValueError as e:
        console.print(f"[red]错误: {e}[/red]")
        sys.exit(1)

    console.print(f"[bold]共 {len(domains)} 个研究领域: "
                  f"{', '.join(d.name for d in domains)}[/bold]")

    # 输出目录（需要提前确定，因为清除历史记录需要）
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = config.output_path

    # 清除历史记录
    if args.clear_history:
        clear_history(output_path)
        console.print("[yellow]历史记录已清除[/yellow]")

    # 应用命令行参数覆盖配置
    if args.min_citations is not None:
        config.filters.min_citations = args.min_citations
    if args.year_from is not None:
        config.filters.year_from = args.year_from

    # 解析数据源
    if args.sources:
        sources = [s.strip() for s in args.sources.split(",")]
        # 验证数据源
        for source in sources:
            if source not in AVAILABLE_SOURCES:
                console.print(f"[red]未知数据源: {source}[/red]")
                console.print(f"可用数据源: {', '.join(AVAILABLE_SOURCES)}")
                sys.exit(1)
    else:
        sources = AVAILABLE_SOURCES

    console.print(f"数据源: {', '.join(sources)}")
    console.print(f"最大结果数: {args.max_results} / 数据源")

    # 初始化爬虫（在所有领域间共享）
    crawlers = get_crawlers(sources=sources, config=config)

    # 处理每个领域
    processed = 0
    for domain_config in domains:
        result = process_domain(
            domain_config=domain_config,
            config=config,
            args=args,
            crawlers=crawlers,
            output_path=output_path,
        )
        if result:
            processed += 1

    # 总结
    if len(domains) > 1:
        console.print(f"\n[bold green]全部完成！{processed}/{len(domains)} 个领域已处理[/bold green]")
    elif processed == 0:
        console.print("[yellow]未生成任何文件[/yellow]")

    # 更新索引文件（如果有输出）
    if not args.dry_run and processed > 0:
        index_path = write_index(output_path)
        if index_path:
            console.print(f"[dim]索引文件: {index_path}[/dim]")


if __name__ == "__main__":
    main()
