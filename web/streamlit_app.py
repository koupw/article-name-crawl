"""论文爬取 Web 界面 (Streamlit)

使用方法:
    streamlit run web/streamlit_app.py

然后在浏览器中打开显示的地址（默认 http://localhost:8501）
"""

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
# 配置加载
# ---------------------------------------------------------------------------
@st.cache_data
def load_app_config(config_path: str = "research_interests.yaml") -> AppConfig:
    """加载并缓存配置（配置变更后需在 Streamlit 菜单点击 Rerun）"""
    return load_config(config_path)


try:
    config = load_app_config()
except Exception as e:
    st.error(f"加载配置失败: {e}")
    st.info("请确保项目根目录存在 `research_interests.yaml`，或运行 `python main.py --init` 生成默认配置。")
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
# 运行逻辑
# ---------------------------------------------------------------------------
if run_clicked:
    # 临时覆盖配置（仅影响本次运行）
    config.filters.min_citations = min_citations
    config.filters.year_from = year_from
    config.translate_backend = translate_engine

    run_options = RunOptions(
        max_results=max_results,
        dry_run=dry_run,
        no_history=no_history,
        no_translate=no_translate,
    )

    output_path = config.output_path

    # 实时日志区域
    log_container = st.empty()
    logs: list[str] = []

    def progress_callback(msg: str) -> None:
        logs.append(msg)
        display = "\n".join(f"• {m}" for m in logs[-30:])
        log_container.markdown(f"```text\n{display}\n```")

    # 新建爬虫（每个请求独立实例，避免线程安全问题）
    crawlers = get_crawlers(sources=selected_sources, config=config)

    with st.status("正在爬取论文...", expanded=True) as status:
        file_path, papers = process_domain(
            domain_config=domain_config,
            config=config,
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
        else:
            status.update(
                label="未找到符合条件的论文",
                state="error",
            )

    # 展示结果
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
        if file_path and file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                md_content = f.read()
            st.download_button(
                "📥 下载 Markdown",
                data=md_content,
                file_name=file_path.name,
                mime="text/markdown",
                key="download_md",
            )
        elif dry_run:
            st.info("干跑模式，未保存文件。取消「干跑模式」后重新爬取即可下载 Markdown。")
    else:
        st.warning(
            "未找到符合条件的论文。建议尝试：\n"
            "1. 放宽筛选条件（降低引用数或年份）\n"
            "2. 增加数据源\n"
            "3. 增加关键词覆盖面"
        )
