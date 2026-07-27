#!/usr/bin/env python3
"""
论文深度分析独立 CLI

完全独立于 main.py 的爬取流程。用户主动选择单篇论文进行分析：
    python analyze.py pdf "papers/download/xxx.pdf"
    python analyze.py arxiv 2401.12345
    python analyze.py doi 10.1000/xyz
    python analyze.py from-md "papers/parsed/xxx.md"

环境隔离：使用项目 .venv 中的 python 运行。
"""

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Callable, Optional

from rich.console import Console

# 项目根目录加入路径
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import load_config, AppConfig
from utils.logger import setup_logger
from utils.mineru_parser import MinerUParser
from utils.llm_analyzer import LLMAnalyzer, LLMClient
from utils.cache_manager import check_cache, save_cache, restore_from_cache
from utils.pdf_downloader import download_arxiv, download_doi, download_url
from storage.report_writer import write_analysis_report

logger = logging.getLogger(__name__)
console = Console()


def _slugify(text: str) -> str:
    """生成安全目录名。"""
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("._")[:80]


def _make_slug(metadata: dict) -> str:
    """生成论文目录 slug：第一作者姓氏_年份_关键词。

    如: Rashid_2026_multi_band_fmcw
    """
    parts = []
    # 第一作者姓氏（兼容 "Smith, J." / "J. Smith" / "Smith J" 三种格式）
    author = metadata.get("first_author", "")
    if author:
        if "," in author:
            # "Smith, J." → 取逗号前半段为姓氏
            surname = author.split(",")[0].strip()
        else:
            # "J. Smith" → 取最后一个 token 为姓氏
            surname = author.split()[-1]
        parts.append(surname.strip(",. "))
    # 年份
    year = metadata.get("year", "")
    if year:
        parts.append(str(year))
    # 标题关键词（取英文标题前2-3个实义词）
    title = metadata.get("title", "")
    if title:
        clean = re.sub(r"[^\w\s]", " ", title.lower())
        words = [w for w in clean.split() if len(w) > 2 and w not in
                 ("the", "for", "and", "with", "based", "using", "via", "from",
                  "into", "its", "new", "two", "has", "was", "are", "not")]
        parts.extend(words[:3])
    slug = "_".join(parts) if parts else "unknown_paper"
    return _slugify(slug)


def _resolve_api_key(args_key: Optional[str], config: AppConfig) -> str:
    """API Key 优先级：命令行 > 环境变量 > 配置文件。"""
    if args_key:
        return args_key
    env_key = os.environ.get("LLM_API_KEY", "")
    if env_key:
        return env_key
    if config.llm_api_key:
        return config.llm_api_key
    raise ValueError(
        "缺少 LLM API Key。请通过以下任一方式配置：\n"
        "  1. 命令行: --api-key <key>\n"
        "  2. 环境变量: set LLM_API_KEY=<key>\n"
        "  3. 配置文件: research_interests.yaml 中 llm_api_key 字段"
    )


def _resolve_analysis_dir(args_output: Optional[str], config: AppConfig) -> Path:
    """确定分析输出根目录。

    优先级：
    1. --output 命令行参数（绝对或相对路径）
    2. config.analysis_dir（配置文件字段，如 'papers/analysis'）
    3. config.vault_path / config.papers_dir
    """
    if args_output:
        return Path(args_output).resolve()
    # 配置文件中的 analysis_dir 字段（吸纳设计意图，便于与爬取产物隔离）
    if config.analysis_dir:
        p = Path(config.analysis_dir)
        if p.is_absolute():
            return p.resolve()
        # 相对路径：挂在 vault_path 下，否则相对当前工作目录
        if config.vault_path:
            return (Path(config.vault_path) / p).resolve()
        return p.resolve()
    if config.vault_path:
        return Path(config.vault_path).resolve() / config.papers_dir
    return Path(config.papers_dir).resolve()


def run_analysis_pipeline(
    mode: str,
    source: str,
    config: AppConfig,
    api_key: str,
    api_base: str,
    model: str,
    language: str,
    analysis_dir: Path,
    force: bool = False,
    skip_analysis: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
    extra_metadata: Optional[dict] = None,
) -> Path:
    """
    执行完整的分析流水线。

    Args:
        mode: pdf / arxiv / doi / from-md
        source: 文件路径 / arxiv_id / doi / md 路径
        config: 应用配置
        api_key: LLM API Key
        api_base: LLM API Base
        model: LLM 模型
        language: zh / en
        analysis_dir: 分析输出根目录
        force: 是否强制重新分析（忽略缓存）
        skip_analysis: 只做 MinerU 解析，不调用 LLM
        progress_callback: 进度回调

    Returns:
        最终分析目录 Path。
    """
    def _notify(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            console.print(msg)

    # ========== 阶段 1：确定输入文件 / Markdown ==========
    pdf_path: Optional[Path] = None
    md_path: Optional[Path] = None
    mineru_result: Optional[dict] = None
    paper_metadata: dict = {}
    # 优先使用外部传入的元数据（如 web 端从爬取结果中提取的标题/作者/年份）
    if extra_metadata:
        paper_metadata.update(extra_metadata)

    if mode == "pdf":
        # 自动判断 source 是本地文件路径还是公网 URL
        if source.startswith("http://") or source.startswith("https://"):
            download_dir = analysis_dir / "_cache" / "downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = download_url(source, download_dir, progress_callback=_notify)
            paper_metadata.setdefault("title", pdf_path.stem)
            # 用元数据重命名 PDF（避免 URL 中的无意义 ID 作为文件名）
            if extra_metadata and extra_metadata.get("title"):
                try:
                    new_name = _make_slug(extra_metadata) + ".pdf"
                    new_path = pdf_path.with_name(new_name)
                    if new_path != pdf_path and not new_path.exists():
                        pdf_path.rename(new_path)
                        pdf_path = new_path
                except OSError:
                    pass
            _notify(f"模式: URL 下载 → {pdf_path}")
        else:
            pdf_path = Path(source).resolve()
            if not pdf_path.is_file():
                raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")
            paper_metadata.setdefault("title", pdf_path.stem)
            _notify(f"模式: 本地 PDF → {pdf_path}")

    elif mode == "arxiv":
        arxiv_id = source.lower().replace("arxiv:", "").strip()
        paper_metadata["arxiv_id"] = arxiv_id
        paper_metadata.setdefault("title", f"arXiv:{arxiv_id}")
        # 下载 PDF
        download_dir = analysis_dir / "_cache" / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = download_arxiv(arxiv_id, download_dir, progress_callback=_notify)
        _notify(f"arXiv PDF 已下载: {pdf_path}")

    elif mode == "doi":
        doi = source.strip()
        paper_metadata["doi"] = doi
        paper_metadata.setdefault("title", f"DOI:{doi}")
        download_dir = analysis_dir / "_cache" / "downloads"
        download_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = download_doi(doi, download_dir, progress_callback=_notify)
        if not pdf_path:
            raise RuntimeError(f"无法通过 DOI 下载 PDF: {doi}")
        _notify(f"DOI PDF 已下载: {pdf_path}")

    elif mode == "from-md":
        md_path = Path(source).resolve()
        if not md_path.is_file():
            raise FileNotFoundError(f"Markdown 文件不存在: {md_path}")
        paper_metadata.setdefault("title", md_path.stem)
        _notify(f"模式: 已有 Markdown → {md_path}")

    else:
        raise ValueError(f"未知模式: {mode}")

    # ========== 阶段 2：确定输出目录 slug ==========
    # 缓存标签（区分不同模型/参数下的同一输入）
    _mineru_model = "vlm"  # MinerU 解析模型
    _cache_tag = f"mineru:{_mineru_model}|llm:{model}"

    # 优先用 arXiv ID，其次用 DOI，最后用论文元数据生成
    if paper_metadata.get("arxiv_id"):
        slug = f"arxiv_{paper_metadata['arxiv_id']}"
    elif paper_metadata.get("doi"):
        slug = _slugify(f"doi_{paper_metadata['doi']}")
    elif paper_metadata.get("title") and paper_metadata["title"] not in (pdf_path.stem if pdf_path else "", md_path.stem if md_path else ""):
        # 有真实标题时用 _make_slug
        slug = _make_slug(paper_metadata)
    elif pdf_path:
        slug = _slugify(pdf_path.stem)
    elif md_path:
        # from-md 模式下，若源文件是 full.md（已有分析目录），则用父目录名
        if md_path.stem == "full":
            slug = _slugify(md_path.parent.name)
        else:
            slug = _slugify(md_path.stem)
    else:
        slug = "unknown_paper"

    target_dir = analysis_dir / slug
    _notify(f"分析输出目录: {target_dir}")

    # ========== 阶段 3：缓存检查 ==========
    if not force and not skip_analysis:
        cache_hit = None
        if pdf_path:
            cache_hit = check_cache(source_path=pdf_path, analysis_dir=analysis_dir, tag=_cache_tag)
        elif md_path:
            md_text = md_path.read_text(encoding="utf-8")
            cache_hit = check_cache(md_text=md_text, analysis_dir=analysis_dir, tag=_cache_tag)

        if cache_hit:
            _notify("检测到缓存结果，直接恢复...")
            restore_from_cache(cache_hit, target_dir)
            _notify(f"分析完成（来自缓存）: {target_dir / 'analysis.md'}")
            return target_dir

    # ========== 阶段 4：MinerU 解析（如果尚未有 md） ==========
    if mode in ("pdf", "arxiv", "doi"):
        _notify("开始 MinerU PDF 解析...")
        parser = MinerUParser(
            token=None,  # 自动从 config.json / 环境变量解析
            model="vlm",
            progress_callback=_notify,
        )
        # 缓存解析中间产物到 _cache/parsed/，最终搬入论文目录
        cache_parsed = analysis_dir / "_cache" / "parsed" / slug
        cache_parsed.mkdir(parents=True, exist_ok=True)
        tmp_md_path = cache_parsed / f"{slug}.md"

        mineru_result = parser.parse_local_pdf(
            pdf_path=str(pdf_path),
            output_md=str(tmp_md_path),
        )
        md_path = Path(mineru_result["md_path"])
        _notify(f"MinerU 解析完成: {md_path}")

    # 读取 Markdown 内容
    if not md_path or not md_path.exists():
        raise FileNotFoundError("无可分析的 Markdown 内容")
    md_text = md_path.read_text(encoding="utf-8")

    # ========== 阶段 5：跳过 LLM 分析（仅解析模式） ==========
    if skip_analysis:
        _notify("--skip-analysis 已指定，跳过 LLM 分析。")
        # 查找图片目录（同阶段 7 的逻辑）
        img_dir = None
        if mineru_result:
            img_dir = Path(mineru_result["images_dir"])
        elif md_path:
            candidate = md_path.parent / md_path.stem / "images"
            if candidate.exists():
                img_dir = candidate
            elif (md_path.parent / "images").exists():
                img_dir = md_path.parent / "images"

        write_analysis_report(
            analysis_result={"report_md": "# Analysis skipped\n\nUse `analyze.py` without `--skip-analysis` to generate full report."},
            output_dir=target_dir,
            paper_metadata=paper_metadata,
            mineru_md_path=md_path,
            mineru_images_dir=img_dir,
            language=language,
        )
        _notify(f"解析结果已保存（无 LLM 分析）: {target_dir}")
        return target_dir

    # ========== 阶段 6：LLM 深度分析 ==========
    _notify("初始化 LLM 分析引擎...")
    llm_client = LLMClient(
        api_key=api_key,
        api_base=api_base,
        model=model,
        timeout=config.llm_timeout,
    )
    analyzer = LLMAnalyzer(
        llm_client=llm_client,
        language=language,
        progress_callback=_notify,
    )

    _notify("开始 LLM 深度分析（可能需要几分钟）...")
    analysis_result = analyzer.analyze(md_text=md_text, metadata=paper_metadata)

    # ========== 阶段 7：写入报告 ==========
    mineru_images_dir = None
    if mineru_result:
        mineru_images_dir = Path(mineru_result["images_dir"])
    elif md_path:
        # 如果是 from-md 模式，尝试找同目录下的 images/
        candidate = md_path.parent / md_path.stem / "images"
        if candidate.exists():
            mineru_images_dir = candidate
        else:
            candidate2 = md_path.parent / "images"
            if candidate2.exists():
                mineru_images_dir = candidate2

    write_analysis_report(
        analysis_result=analysis_result,
        output_dir=target_dir,
        paper_metadata=paper_metadata,
        mineru_md_path=md_path,
        mineru_images_dir=mineru_images_dir,
        language=language,
    )

    # 保存缓存
    if pdf_path:
        save_cache(result_dir=target_dir, source_path=pdf_path, analysis_dir=analysis_dir, tag=_cache_tag)
    else:
        save_cache(result_dir=target_dir, md_text=md_text, analysis_dir=analysis_dir, tag=_cache_tag)

    _notify(f"分析完成！报告位置: {target_dir / 'analysis.md'}")
    _notify(f"执行摘要:\n{analysis_result.get('exec_summary', '')[:300]}...")
    scores = analysis_result.get("scores", {})
    if scores:
        _notify(
            f"评分: 总体 {scores.get('overall', '-')} | "
            f"创新 {scores.get('innovation', '-')} | "
            f"实验 {scores.get('experiment', '-')} | "
            f"实用 {scores.get('practical', '-')} | "
            f"写作 {scores.get('writing', '-')} | "
            f"影响 {scores.get('influence', '-')}"
        )
    return target_dir


def parse_args() -> argparse.Namespace:
    # 通用参数（作为 parent parser 供子命令继承，支持参数放子命令后）
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--api-key", help="LLM API Key（覆盖环境变量和配置）")
    parent.add_argument("--api-base", default=None, help="LLM API Base URL")
    parent.add_argument("--model", default=None, help="LLM 模型名称（如 deepseek-chat, gpt-4o）")
    parent.add_argument("--language", default=None, choices=["zh", "en"], help="输出语言")
    parent.add_argument("--output", "-o", default=None, help="分析输出根目录（默认 papers/analysis）")
    parent.add_argument("--force", action="store_true", help="强制重新分析（忽略缓存）")
    parent.add_argument("--skip-analysis", action="store_true", help="仅做 MinerU 解析，跳过 LLM 分析（省费用）")
    parent.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parent.add_argument("--config", default="research_interests.yaml", help="配置文件路径")

    parser = argparse.ArgumentParser(
        description="论文深度分析独立 CLI（完全独立于爬取流程）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[parent],
        epilog="""
示例:
  # 分析本地 PDF（自动下载、解析、分析、生成报告）
  python analyze.py pdf "papers/download/report.pdf"

  # 分析 arXiv 论文
  python analyze.py arxiv 2401.12345

  # 分析已有 Markdown（跳过 MinerU 解析）
  python analyze.py from-md "papers/parsed/report/report.md"

  # 指定 LLM API Key 和模型
  python analyze.py pdf report.pdf --api-key sk-xxx --model deepseek-chat

  # 仅做 MinerU 解析，不调用 LLM（省费用）
  python analyze.py pdf report.pdf --skip-analysis

API Key 优先级:
  1. 命令行 --api-key
  2. 环境变量 LLM_API_KEY
  3. 配置文件 llm_api_key 字段
""",
    )
    sub = parser.add_subparsers(dest="mode", required=True, help="分析模式")

    # pdf 模式
    pdf_parser = sub.add_parser("pdf", help="分析本地 PDF 文件", parents=[parent])
    pdf_parser.add_argument("path", help="PDF 文件路径")

    # arxiv 模式
    arxiv_parser = sub.add_parser("arxiv", help="通过 arXiv ID 下载并分析", parents=[parent])
    arxiv_parser.add_argument("id", help="arXiv ID（如 2401.12345）")

    # doi 模式
    doi_parser = sub.add_parser("doi", help="通过 DOI 下载并分析（尽力而为）", parents=[parent])
    doi_parser.add_argument("doi", help="DOI 字符串")

    # from-md 模式
    md_parser = sub.add_parser("from-md", help="基于已有 Markdown 直接分析（跳过 MinerU 解析）", parents=[parent])
    md_parser.add_argument("path", help="Markdown 文件路径")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logger(verbose=args.verbose)

    # 加载配置
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        console.print(f"[red]配置文件不存在: {args.config}。运行 `python main.py --init` 生成默认配置。[/red]")
        sys.exit(1)

    # 解析参数（skip-analysis 时不需要 API Key）
    api_key = ""
    if not args.skip_analysis:
        try:
            api_key = _resolve_api_key(args.api_key, config)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            sys.exit(1)

    api_base = args.api_base or config.llm_api_base
    model = args.model or config.llm_model
    language = args.language or config.language
    analysis_dir = _resolve_analysis_dir(args.output, config)

    # 执行流水线
    try:
        # 统一获取 source 参数名
        if args.mode == "from-md":
            src = args.path
        elif args.mode == "arxiv":
            src = args.id
        elif args.mode == "doi":
            src = args.doi
        else:
            src = args.path

        run_analysis_pipeline(
            mode=args.mode,
            source=src,
            config=config,
            api_key=api_key,
            api_base=api_base,
            model=model,
            language=language,
            analysis_dir=analysis_dir,
            force=args.force,
            skip_analysis=args.skip_analysis,
        )
    except Exception as e:
        logger.exception("分析流程失败")
        console.print(f"[red]分析失败: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
