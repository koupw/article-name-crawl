#!/usr/bin/env python3
"""
PDF 下载工具

支持从以下源下载 PDF：
- arXiv ID -> https://arxiv.org/pdf/{id}.pdf
- DOI -> 通过 https://doi.org/{doi} 解析跳转获取 PDF（尽力而为）
- 直接 URL -> 下载公网 PDF

下载的文件放入指定目录，文件名自动规范化。
"""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def _safe_filename(name: str) -> str:
    """将字符串转为安全文件名。"""
    name = re.sub(r'[\\/:*?"<>|]+', "_", name)
    name = re.sub(r"\s+", "_", name)
    return name.strip("._")


def download_arxiv(arxiv_id: str, output_dir: Path, progress_callback: Optional[callable] = None) -> Path:
    """从 arXiv 下载 PDF。

    Args:
        arxiv_id: 纯 ID（如 2401.12345）或含前缀（arXiv:2401.12345）。
        output_dir: 下载保存目录。
        progress_callback: 进度回调。

    Returns:
        下载后的 PDF 路径。
    """
    # 清洗 ID
    clean_id = arxiv_id.lower().replace("arxiv:", "").strip()
    url = f"https://arxiv.org/pdf/{clean_id}.pdf"
    filename = f"arxiv_{clean_id}.pdf"
    return _download_url(url, output_dir / filename, progress_callback)


def download_doi(doi: str, output_dir: Path, progress_callback: Optional[callable] = None) -> Optional[Path]:
    """通过 DOI 尽力下载 PDF（解析跳转链路，不保证 100% 成功）。

    Returns:
        成功时返回 PDF 路径；失败返回 None。
    """
    clean_doi = doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "")
    # 先尝试 unpaywall 或 doi.org 跳转
    headers = {"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"}
    try:
        # 跟随 doi.org 跳转，寻找 PDF 链接
        resp = requests.get(
            f"https://doi.org/{clean_doi}",
            headers=headers,
            allow_redirects=True,
            timeout=30,
        )
        # 如果最终 URL 以 .pdf 结尾，直接下载
        final_url = resp.url
        if final_url.lower().endswith(".pdf"):
            filename = f"doi_{_safe_filename(clean_doi)}.pdf"
            return _download_url(final_url, output_dir / filename, progress_callback)
        # 否则尝试从页面提取 PDF 链接（简单启发式）
        pdf_url = _extract_pdf_link_from_html(resp.text, final_url)
        if pdf_url:
            filename = f"doi_{_safe_filename(clean_doi)}.pdf"
            return _download_url(pdf_url, output_dir / filename, progress_callback)
    except Exception as e:
        logger.warning("DOI 解析失败 %s: %s", doi, e)
    return None


def download_url(pdf_url: str, output_dir: Path, progress_callback: Optional[callable] = None) -> Path:
    """从直接 URL 下载 PDF。"""
    parsed = urlparse(pdf_url)
    filename = Path(parsed.path).name or "downloaded.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return _download_url(pdf_url, output_dir / filename, progress_callback)


def _download_url(url: str, output_path: Path, progress_callback: Optional[callable] = None) -> Path:
    """通用下载函数。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": USER_AGENT}
    logger.info("开始下载: %s", url)
    if progress_callback:
        progress_callback(f"正在下载 PDF: {url}")

    resp = requests.get(url, headers=headers, stream=True, timeout=120)
    resp.raise_for_status()

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    logger.info("下载完成: %s (%s bytes)", output_path, output_path.stat().st_size)
    if progress_callback:
        progress_callback(f"PDF 已下载: {output_path.name}")
    return output_path


def _extract_pdf_link_from_html(html: str, base_url: str) -> Optional[str]:
    """从 HTML 中简单提取 PDF 链接。"""
    # 常见模式
    patterns = [
        r'href="([^"]+\.pdf)"',
        r'content="([^"]+\.pdf)"',
        r"window\.location\.href\s*=\s*'([^']+\.pdf)'",
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            link = m.group(1)
            if link.startswith("http"):
                return link
            # 相对路径处理（简化）
            from urllib.parse import urljoin
            return urljoin(base_url, link)
    return None
