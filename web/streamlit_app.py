"""论文爬取 Web 界面 (Streamlit)

使用方法:
    streamlit run web/streamlit_app.py

然后在浏览器中打开显示的地址（默认 http://localhost:8501）
"""

import copy
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# 将项目根目录加入导入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import load_config, validate_config, AppConfig
from main import get_crawlers, process_domain, RunOptions, AVAILABLE_SOURCES
from utils.logger import setup_logger

# 论文深度分析相关（需要在主页面内直接嵌入分析功能）
from analyze import run_analysis_pipeline, _resolve_api_key, _resolve_analysis_dir
from config.loader import load_config as _load_cfg_raw  # noqa: E402
from storage.report_writer import md_with_inline_images

# ---------------------------------------------------------------------------
# 页面初始化
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="论文爬取工具",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Web 模式日志（不覆盖 Streamlit 自带的 handlers）
setup_logger(replace_handlers=False)


# ---------------------------------------------------------------------------
# 配置加载（使用项目根目录的绝对路径，避免工作目录问题）
# ---------------------------------------------------------------------------
CONFIG_PATH = PROJECT_ROOT / "research_interests.yaml"

def _safe_basename(s: str, maxlen: int = 80) -> str:
    """去除文件系统非法字符，避免 download_button 失败。"""
    s = re.sub(r'[\\/:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", "_", s)
    return s.strip("._")[:maxlen]

@st.cache_data
def load_app_config(config_path: str = str(CONFIG_PATH)) -> AppConfig:
    """加载并缓存配置（配置变更后需在 Streamlit 菜单点击 Rerun）"""
    return load_config(config_path)


try:
    config = load_app_config()
except Exception as e:
    st.error(f"加载配置失败: {e}")
    st.info(f"请确保配置文件存在: {CONFIG_PATH}")
    st.info("或运行 `python main.py --init` 生成默认配置。")
    st.stop()

# 显示配置警告
warnings = validate_config(config)
for w in warnings:
    st.warning(w)

# ---------------------------------------------------------------------------
# 左侧边栏 — 配置面板
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ 配置")

    # 领域选择
    domain_names = list(config.research_domains.keys())
    if not domain_names:
        st.error("配置文件中未定义研究领域，请先编辑 research_interests.yaml")
        st.stop()

    selected_domain = st.selectbox("研究领域", domain_names)
    domain_config = config.research_domains[selected_domain]

    st.divider()

    # 数据源
    selected_sources = st.multiselect(
        "数据源",
        options=AVAILABLE_SOURCES,
        default=["arxiv", "openalex", "crossref"],
        help=(
            "推荐: arXiv + OpenAlex + Crossref（全部免费官方 API）。"
            " IEEE / CORE 需要 API Key；Google Scholar 不稳定"
        ),
    )

    # 最大结果数
    max_results = st.slider(
        "每数据源最大结果数",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
    )

    st.divider()
    st.subheader("筛选条件")

    min_citations = st.slider(
        "最低引用数",
        min_value=0,
        max_value=100,
        value=config.filters.min_citations or 0,
        step=5,
        help="0 表示不限制。需要 OpenAlex / Semantic Scholar 数据源才有效",
    )

    year_from = st.number_input(
        "起始年份",
        min_value=1980,
        max_value=2030,
        value=config.filters.year_from or 2018,
        step=1,
        help="只保留该年份之后的论文",
    )

    st.divider()
    st.subheader("翻译")

    translate_engine = st.radio(
        "翻译引擎",
        options=["google", "baidu"],
        index=0 if config.translate_backend == "google" else 1,
        help="百度翻译免费版限制 1 QPS，速度较慢",
    )
    no_translate = st.checkbox("不翻译标题", value=False)

    st.divider()

    dry_run = st.checkbox(
        "干跑模式（预览不保存）",
        value=False,
        help="结果只展示，不写入 Markdown 文件和历史记录",
    )
    no_history = st.checkbox(
        "禁用历史记录",
        value=False,
        help="不读取也不写入 crawled_papers.json",
    )

    st.divider()

    run_clicked = st.button(
        "🚀 开始爬取",
        type="primary",
        use_container_width=True,
    )

# ---------------------------------------------------------------------------
# 主区域 — 状态概览与结果
# ---------------------------------------------------------------------------
st.title("📚 论文爬取工具")
st.caption("从多个学术数据源自动爬取、去重、筛选并翻译论文标题")

# 配置摘要卡片
if domain_config.keywords:
    cols = st.columns(4)
    cols[0].metric("研究领域", selected_domain)
    cols[1].metric("关键词数", len(domain_config.keywords))
    cols[2].metric("数据源", len(selected_sources))
    cols[3].metric("预估上限", max_results * len(selected_sources))

# 未选数据源时提示
if not selected_sources:
    st.info("👈 请在左侧边栏至少选择一个数据源")
    st.stop()

# ---------------------------------------------------------------------------
# 运行爬取（仅在用户点击按钮时执行）
# ---------------------------------------------------------------------------
if run_clicked:
    # 独立副本写入运行时覆盖（不污染 @st.cache_data 缓存的 config）
    run_cfg = copy.deepcopy(config)
    run_cfg.filters.min_citations = min_citations
    run_cfg.filters.year_from = year_from
    run_cfg.translate_backend = translate_engine
    # 重新取 domain_config 以避免引用缓存对象
    domain_config = run_cfg.research_domains[selected_domain]

    run_options = RunOptions(
        max_results=max_results,
        dry_run=dry_run,
        no_history=no_history,
        no_translate=no_translate,
    )

    output_path = run_cfg.output_path

    # 新建爬虫（每个请求独立实例，避免线程安全问题）
    crawlers = get_crawlers(sources=selected_sources, config=run_cfg)

    with st.status("正在爬取论文...", expanded=True) as status:
        def progress_callback(msg: str) -> None:
            status.write(f"• {msg}")

        file_path, papers = process_domain(
            domain_config=domain_config,
            config=run_cfg,
            run_options=run_options,
            crawlers=crawlers,
            output_path=output_path,
            progress_callback=progress_callback,
        )
        if papers:
            status.update(
                label=f"完成！找到 {len(papers)} 篇论文",
                state="complete",
            )
            # 持久化到 session_state，页面刷新不丢失
            st.session_state["crawled_papers"] = papers
            st.session_state["crawled_file_path"] = file_path
            st.session_state["crawled_dry_run"] = dry_run
            # 重置分析结果（新爬取结果可能与旧分析不匹配）
            st.session_state.pop("analysis_target_dir", None)
        else:
            status.update(
                label="未找到符合条件的论文",
                state="error",
            )
            st.session_state.pop("crawled_papers", None)
            st.warning(
                "未找到符合条件的论文。建议尝试：\n"
                "1. 放宽筛选条件（降低引用数或年份）\n"
                "2. 增加数据源\n"
                "3. 增加关键词覆盖面"
            )
        # 注意：此处不调用 st.rerun()，让结果在同一渲染周期内展示


# ---------------------------------------------------------------------------
# 展示结果（始终从 session_state 读取，页面刷新不丢失）
# ---------------------------------------------------------------------------
papers = st.session_state.get("crawled_papers", [])
file_path = st.session_state.get("crawled_file_path", None)

if not papers and not run_clicked:
    st.info("👈 配置好参数后，点击「🚀 开始爬取」获取论文列表。爬取完成后可在这里选择论文进行深度分析。")
    st.stop()

if papers:
    st.success(f"找到 {len(papers)} 篇论文")

    # 构建 DataFrame
    rows = []
    for p in papers:
        rows.append(
            {
                "标题": p.title,
                "中文标题": p.title_zh or "-",
                "作者": p.authors_str,
                "年份": p.year or "-",
                "引用数": p.citations,
                "数据源": p.source,
                "链接": p.url,
                "PDF": p.pdf_url or "",
            }
        )
    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        column_config={
            "链接": st.column_config.LinkColumn("论文链接"),
            "PDF": st.column_config.LinkColumn("PDF 链接"),
        },
        hide_index=True,
        use_container_width=True,
    )

    # 统计
    st.caption(
        f"去重后 {len(papers)} 篇 | 数据源分布: "
        + ", ".join(
            f"{src}: {cnt}"
            for src, cnt in df["数据源"].value_counts().to_dict().items()
        )
    )

    # 下载按钮
    if file_path and Path(file_path).exists():
        with open(file_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        st.download_button(
            "📥 下载 Markdown",
            data=md_content,
            file_name=Path(file_path).name,
            mime="text/markdown",
            key="download_md",
        )
    elif st.session_state.get("crawled_dry_run"):
        st.info("干跑模式，未保存文件。取消「干跑模式」后重新爬取即可下载 Markdown。")

    # -----------------------------------------------------------------------
    # 论文深度分析入口（从爬取结果中选择论文直接分析）
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("🔬 深度分析论文")

    # 筛选出有可用来源的论文（有 arXiv ID 或 PDF URL）
    analyzable = []
    for p in papers:
        if p.arxiv_id:
            analyzable.append((f"[arXiv] {p.title}", p.arxiv_id, "arxiv", p))
        elif p.pdf_url:
            analyzable.append((f"[PDF] {p.title}", p.pdf_url, "pdf", p))
        elif p.doi:
            analyzable.append((f"[DOI] {p.title}", p.doi, "doi", p))

    if not analyzable:
        st.info("当前论文列表中无可分析的论文（需要有 arXiv ID / PDF 链接 / DOI）。"
                 "如需分析，可切换到「🔬 论文深度分析」页面手动上传 PDF 或输入 arXiv ID。")
    else:
        # 选择论文
        options = [label for label, _, _, _ in analyzable]
        selected_idx = st.selectbox(
            "选择要深度分析的论文",
            range(len(options)),
            format_func=lambda i: options[i][:120],
            key="analysis_select",
        )
        selected_label, selected_source, selected_mode, selected_paper = analyzable[selected_idx]

        # 显示选中论文的详情
        with st.expander("📄 论文详情", expanded=False):
            p = selected_paper
            st.write(f"**标题**: {p.title}")
            if p.title_zh and p.title_zh != "-":
                st.write(f"**中文标题**: {p.title_zh}")
            st.write(f"**作者**: {p.authors_str}")
            st.write(f"**年份**: {p.year or '-'}")
            st.write(f"**来源**: {p.source}")
            if p.arxiv_id:
                st.write(f"**arXiv ID**: {p.arxiv_id}")
            if p.doi:
                st.write(f"**DOI**: {p.doi}")
            if p.pdf_url:
                st.write(f"**PDF**: {p.pdf_url}")
            if p.abstract:
                st.write(f"**摘要**: {p.abstract[:500]}...")

        # 分析按钮
        col1, col2 = st.columns([1, 3])
        with col1:
            run_analysis = st.button(
                "🚀 开始深度分析",
                type="primary",
                key="run_analysis_btn",
                use_container_width=True,
            )

        if run_analysis:
            # 解析 API Key
            try:
                effective_key = _resolve_api_key(None, config)
            except ValueError as e:
                st.error(str(e))
                st.stop()

            with st.status("正在执行深度分析...", expanded=True) as ana_status:
                def analysis_progress(msg: str) -> None:
                    ana_status.write(f"• {msg}")

                try:
                    target_dir = run_analysis_pipeline(
                        mode=selected_mode,
                        source=selected_source,
                        config=config,
                        api_key=effective_key,
                        api_base=config.llm_api_base,
                        model=config.llm_model,
                        language=config.language,
                        analysis_dir=_resolve_analysis_dir(None, config),
                        force=False,
                        skip_analysis=False,
                        progress_callback=analysis_progress,
                        extra_metadata={
                            "title": selected_paper.title,
                            "first_author": selected_paper.authors[0] if selected_paper.authors else "",
                            "year": str(selected_paper.year) if selected_paper.year else "",
                        },
                    )
                    # 持久化分析结果
                    st.session_state["analysis_target_dir"] = str(target_dir)
                    ana_status.update(label="深度分析完成！", state="complete")
                except Exception as e:
                    ana_status.update(label=f"分析失败: {e}", state="error")
                    st.exception(e)
                    st.stop()

        # 展示分析结果（从 session_state 读取，持久化）
        ana_dir = st.session_state.get("analysis_target_dir", None)
        if ana_dir:
            ana_md_path = Path(ana_dir) / "analysis.md"
            meta_path = Path(ana_dir) / "meta.json"
            full_md_path = Path(ana_dir) / "full.md"

            if meta_path.exists():
                import json
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                scores = meta.get("scores", {})

                st.subheader("📊 评分")
                if scores:
                    ccols = st.columns(min(len(scores), 6))
                    score_map = {
                        "overall": "总体",
                        "innovation": "创新",
                        "experiment": "实验",
                        "practical": "实用",
                        "writing": "写作",
                        "influence": "影响",
                    }
                    for col, (k, v) in zip(ccols, list(scores.items())[:6]):
                        label = score_map.get(k, k)
                        col.metric(label, f"{v}/10")

            # 执行摘要
            if meta_path.exists():
                summary = json.loads(meta_path.read_text(encoding="utf-8")).get("exec_summary", "")
                if summary:
                    st.subheader("📋 执行摘要")
                    st.markdown(summary)

            # 下载按钮
            st.subheader("📥 下载报告")
            dcols = st.columns(3)
            if ana_md_path.exists():
                with open(ana_md_path, "r", encoding="utf-8") as f:
                    dcols[0].download_button(
                        "analysis.md",
                        data=f.read(),
                        file_name=f"{_safe_basename(selected_paper.title[:50])}_analysis.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="dl_ana",
                    )
            if full_md_path.exists():
                with open(full_md_path, "r", encoding="utf-8") as f:
                    dcols[1].download_button(
                        "full.md (原始解析)",
                        data=f.read(),
                        file_name=f"{_safe_basename(selected_paper.title[:50])}_full.md",
                        mime="text/markdown",
                        use_container_width=True,
                        key="dl_full",
                    )

            # 完整报告预览（图片 base64 内联以支持 Streamlit 显示）
            if ana_md_path.exists():
                with st.expander("📝 完整报告预览", expanded=False):
                    st.markdown(md_with_inline_images(
                        ana_md_path.read_text(encoding="utf-8"),
                        ana_md_path.parent,
                    ), unsafe_allow_html=True)
