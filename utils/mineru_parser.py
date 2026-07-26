#!/usr/bin/env python3
"""
MinerU 解析封装模块 — 程序化 API 调用层

将 mineru-api-client/mineru_client.py 的核心能力封装为内部可调用的 API，
支持进度回调、日志静默、自动路径推断。
"""

import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional

# 将 mineru-api-client 加入模块搜索路径（如果尚未加入）
MINERU_CLIENT_DIR = Path(__file__).resolve().parent.parent / "mineru-api-client"
if str(MINERU_CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(MINERU_CLIENT_DIR))

# 复用 mineru_client 中的底层函数（避免复制网络逻辑）
import mineru_client as _mc

logger = logging.getLogger(__name__)


class MinerUParser:
    """MinerU PDF 解析器（程序化 API 封装）"""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "vlm",
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            token: MinerU API Token。为 None 时按 _mc._resolve_token 规则解析。
            base_url: API 基础 URL，默认 https://mineru.net/api/v4
            model: 解析模型 (vlm / pipeline / MinerU-HTML)
            progress_callback: 进度消息回调，供 Web 界面使用。
        """
        self.token = token or _mc._resolve_token("")
        if not self.token:
            raise ValueError(
                "缺少 MinerU API Token。请通过参数 token、"
                "环境变量 MINERU_TOKEN 或 mineru-api-client/config.json 配置。"
            )
        self.base_url = base_url or _mc.DEFAULT_BASE_URL
        self.model = model
        self._cb = progress_callback

    def _notify(self, msg: str) -> None:
        """统一输出：优先回调，其次日志。"""
        if self._cb:
            self._cb(msg)
        else:
            logger.info(msg)

    def _infer_output_path(self, pdf_path: Path) -> Path:
        """
        自动推断输出路径：
        - 若 PDF 位于 download/ 目录 → 输出到同级的 parsed/
        - 否则 → 与 PDF 同目录的 parsed/ 子目录
        """
        pdf_path = pdf_path.resolve()
        if pdf_path.parent.name.lower() == "download":
            parsed_dir = pdf_path.parent.parent / "parsed"
        else:
            parsed_dir = pdf_path.parent / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        return parsed_dir / f"{pdf_path.stem}.md"

    def parse_local_pdf(
        self,
        pdf_path: str | Path,
        output_md: Optional[str | Path] = None,
    ) -> dict:
        """
        解析本地 PDF 文件。

        Args:
            pdf_path: 本地 PDF 路径。
            output_md: 输出 Markdown 文件路径。为 None 时自动推断。

        Returns:
            解析结果字典，包含字段:
            - md_path: Markdown 文件绝对路径
            - images_dir: 图片目录绝对路径（与 md 同名的专属目录下的 images/）
            - paper_dir: 专属论文目录（md_path.stem/）
            - full_zip_url: ZIP 下载地址
            - model: 使用的模型
            - batch_id: Batch ID
        """
        pdf_path = Path(pdf_path).resolve()
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        filename = pdf_path.name
        self._notify(f"准备解析本地 PDF: {pdf_path}")

        # 1. 申请预签名上传链接
        file_infos = [{"name": filename, "data_id": filename}]
        batch_id, presigned_urls = _mc.get_upload_urls(
            file_infos, self.model, self.token, self.base_url
        )
        presigned_url = presigned_urls[0]
        self._notify(f"Batch ID: {batch_id}, 模型: {self.model}")

        # 2. PUT 上传文件
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        self._notify(f"正在直传到 MinerU OSS ({size_mb:.1f} MB) ...")
        _mc.upload_file_to_presigned(str(pdf_path), presigned_url)
        self._notify("直传完成，MinerU 已开始解析。")

        # 3. 轮询 batch 结果
        self._notify("等待解析完成...")
        result = _mc.poll_batch(batch_id, filename, self.token, self.base_url)
        self._notify("MinerU 解析完成。")

        # 4. 确定输出路径并下载提取
        if output_md:
            out_path = Path(output_md).resolve()
        else:
            out_path = self._infer_output_path(pdf_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        full_zip_url = result.get("full_zip_url", "")
        if not full_zip_url:
            raise RuntimeError(f"MinerU 返回结果缺少 full_zip_url: {result}")

        self._notify(f"正在下载解析结果并提取 Markdown...")
        _mc.download_and_extract_md(full_zip_url, str(out_path))
        self._notify(f"Markdown 已保存: {out_path}")

        # 5. 构造返回信息
        paper_dir = out_path.parent / out_path.stem
        images_dir = paper_dir / "images"

        return {
            "md_path": str(out_path),
            "paper_dir": str(paper_dir),
            "images_dir": str(images_dir),
            "full_zip_url": full_zip_url,
            "model": self.model,
            "batch_id": batch_id,
        }

    def parse_url(
        self,
        pdf_url: str,
        output_md: str | Path,
    ) -> dict:
        """
        解析公网 PDF URL。

        Args:
            pdf_url: 公网可访问的 PDF URL。
            output_md: 输出 Markdown 文件路径（必须显式指定）。

        Returns:
            同 parse_local_pdf。
        """
        out_path = Path(output_md).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self._notify(f"解析公网 URL: {pdf_url}")
        task_id = _mc.submit_task_by_url(pdf_url, self.model, self.token, self.base_url)
        self._notify(f"Task ID: {task_id}, 模型: {self.model}")

        self._notify("等待解析完成...")
        result = _mc.poll_task(task_id, self.token, self.base_url)
        self._notify("MinerU 解析完成。")

        full_zip_url = result.get("full_zip_url", "")
        if not full_zip_url:
            raise RuntimeError(f"MinerU 返回结果缺少 full_zip_url: {result}")

        self._notify("正在下载解析结果并提取 Markdown...")
        _mc.download_and_extract_md(full_zip_url, str(out_path))
        self._notify(f"Markdown 已保存: {out_path}")

        paper_dir = out_path.parent / out_path.stem
        images_dir = paper_dir / "images"

        return {
            "md_path": str(out_path),
            "paper_dir": str(paper_dir),
            "images_dir": str(images_dir),
            "full_zip_url": full_zip_url,
            "model": self.model,
            "task_id": task_id,
        }
