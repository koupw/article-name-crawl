"""
Streamlit 多页面：论文深度分析

使用方式（由 streamlit_app.py 导航进入，或独立运行）：
    streamlit run web/pages/analysis.py

功能：
- 上传 PDF 或输入 arXiv ID / DOI / Markdown 路径
- 调用 analyze.py 中的 run_analysis_pipeline 执行完整流程
- 实时展示进度、执行摘要、评分、下载报告
"""

import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import load_config, AppConfig
from utils.logger import setup_logger
from analyze import run_analysis_pipeline, _resolve_api_key, _resolve_analysis_dir
from storage.report_writer import md_with_inline_images

setup_logger(replace_handlers=False)

st.title("🔬 论文深度分析")
st.caption("选择性解读单篇论文：MinerU 解析 → LLM 深度分析 → 结构化报告")

# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
CONFIG_PATH = PROJECT_ROOT / "research_interests.yaml"


@st.cache_data
def _load_cfg() -> AppConfig:
    return load_config(str(CONFIG_PATH))


try:
    config = _load_cfg()
except Exception as e:
    st.error(f"加载配置失败: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# 侧边栏 — 输入与参数
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📥 输入")

    mode = st.radio(
        "分析来源",
        options=["上传 PDF", "arXiv ID", "已有 Markdown"],
        index=0,
    )

    source_file: str = ""
    if mode == "上传 PDF":
        uploaded = st.file_uploader("选择 PDF 文件", type=["pdf"])
        if uploaded:
            # 保存到临时文件（run_analysis_pipeline 需要路径）
            tmp_dir = Path(tempfile.gettempdir()) / "paper_analyze_uploads"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_path = tmp_dir / uploaded.name
            tmp_path.write_bytes(uploaded.getvalue())
            source_file = str(tmp_path)
            st.success(f"已上传: {uploaded.name}")
    elif mode == "arXiv ID":
        source_file = st.text_input("arXiv ID", placeholder="例如: 2401.12345").strip()
    else:
        source_file = st.text_input(
            "Markdown 文件路径",
            placeholder="例如: papers/parsed/report/report.md",
        ).strip()

    st.divider()
    st.header("⚙️ LLM 参数")

    api_key = st.text_input(
        "API Key (可选)",
        type="password",
        placeholder="留空则使用配置或环境变量 LLM_API_KEY",
        help="优先级: 此处输入 > 环境变量 > 配置文件",
    )
    api_base = st.text_input(
        "API Base",
        value=config.llm_api_base,
    )
    model = st.text_input(
        "模型名称",
        value=config.llm_model,
    )
    language = st.radio(
        "输出语言",
        options=["zh", "en"],
        index=0 if config.language == "zh" else 1,
    )

    st.divider()
    st.header("📁 输出")
    output_dir = st.text_input(
        "分析输出目录",
        value=str(_resolve_analysis_dir(None, config)),
    )
    force = st.checkbox("强制重新分析（忽略缓存）", value=False)
    skip_llm = st.checkbox("仅做 PDF 解析，跳过 LLM 分析（省费用）", value=False)

    st.divider()
    run_clicked = st.button(
        "🚀 开始分析",
        type="primary",
        use_container_width=True,
        disabled=not source_file,
    )

# ---------------------------------------------------------------------------
# 主区域 — 运行与结果展示
# ---------------------------------------------------------------------------
if not source_file:
    st.info("👈 请在左侧选择分析来源并上传/输入")
    st.stop()

if run_clicked:
    # 解析模式
    if mode == "上传 PDF":
        run_mode = "pdf"
    elif mode == "arXiv ID":
        run_mode = "arxiv"
    else:
        run_mode = "from-md"

    # 解析 API Key
    try:
        effective_key = _resolve_api_key(api_key or None, config)
    except ValueError as e:
        st.error(str(e))
        st.stop()

    with st.status("正在执行分析流程...", expanded=True) as status:
        def progress_callback(msg: str) -> None:
            status.write(f"• {msg}")

        try:
            target_dir = run_analysis_pipeline(
                mode=run_mode,
                source=source_file,
                config=config,
                api_key=effective_key,
                api_base=api_base,
                model=model,
                language=language,
                analysis_dir=Path(output_dir),
                force=force,
                skip_analysis=skip_llm,
                progress_callback=progress_callback,
            )
            status.update(label="分析完成！", state="complete")
        except Exception as e:
            status.update(label=f"分析失败: {e}", state="error")
            st.exception(e)
            st.stop()

    # 读取结果
    analysis_md_path = target_dir / "analysis.md"
    full_md_path = target_dir / "full.md"
    meta_path = target_dir / "meta.json"
    images_dir = target_dir / "images"

    # 展示执行摘要和评分
    if meta_path.exists():
        import json
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        exec_summary = meta.get("exec_summary", "")
        scores = meta.get("scores", {})

        if exec_summary:
            st.subheader("📋 执行摘要")
            st.markdown(exec_summary)

        if scores:
            st.subheader("📊 评分")
            cols = st.columns(len(scores))
            score_labels = {
                "overall": "总体",
                "innovation": "创新",
                "experiment": "实验",
                "practical": "实用",
                "writing": "写作",
                "influence": "影响",
            }
            for col, (k, v) in zip(cols, scores.items()):
                label = score_labels.get(k, k)
                col.metric(label, f"{v}/10")

    # 文件下载
    st.subheader("📥 下载报告")
    dcols = st.columns(3)
    if analysis_md_path.exists():
        with open(analysis_md_path, "r", encoding="utf-8") as f:
            dcols[0].download_button(
                "下载 analysis.md",
                data=f.read(),
                file_name="analysis.md",
                mime="text/markdown",
                use_container_width=True,
            )
    if full_md_path.exists():
        with open(full_md_path, "r", encoding="utf-8") as f:
            dcols[1].download_button(
                "下载 full.md",
                data=f.read(),
                file_name="full.md",
                mime="text/markdown",
                use_container_width=True,
            )
    # 图片打包下载
    if images_dir.exists() and any(images_dir.iterdir()):
        import zipfile
        import io
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for img in images_dir.iterdir():
                if img.is_file():
                    zf.write(img, img.name)
        dcols[2].download_button(
            "下载图片 (zip)",
            data=zip_buffer.getvalue(),
            file_name="images.zip",
            mime="application/zip",
            use_container_width=True,
        )

    # 完整报告预览（折叠，图片 base64 内联以支持 Streamlit 显示）
    if analysis_md_path.exists():
        with st.expander("📝 查看完整报告 (analysis.md)", expanded=False):
            st.markdown(md_with_inline_images(
                analysis_md_path.read_text(encoding="utf-8"),
                analysis_md_path.parent,
            ), unsafe_allow_html=True)

    # 原始 Markdown 预览（折叠）
    if full_md_path.exists():
        with st.expander("📄 查看原始解析 (full.md)", expanded=False):
            st.markdown(md_with_inline_images(
                full_md_path.read_text(encoding="utf-8"),
                full_md_path.parent,
            ), unsafe_allow_html=True)

    st.success(f"分析结果目录: {target_dir}")
