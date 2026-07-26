#!/usr/bin/env python3
"""
MinerU 官方 API 便捷客户端（v4 原生直传版）
支持：公网 PDF URL 直接解析 / 本地 PDF 文件通过 MinerU 预签名 URL 直传解析
"""

import argparse
import io
import os
import re
import sys
import time
import json
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import requests

# MinerU 专用 session：强制不走系统代理（避免与翻译等需要代理的服务冲突）
_sess = requests.Session()
_sess.trust_env = False

# 向后兼容的别名
requests = _sess

# ==================== 配置 ====================

DEFAULT_BASE_URL = "https://mineru.net/api/v4"
DEFAULT_MODEL = "vlm"
POLL_INTERVAL = 3          # 轮询间隔（秒）
MAX_POLL_COUNT = 120       # 最多轮询次数（约 6 分钟）

SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_FILE = SCRIPT_DIR / "config.json"


def _load_config() -> dict:
    """读取同级目录的 config.json（如果存在）。"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"[WARN] {CONFIG_FILE} 格式错误，将忽略。", file=sys.stderr)
    return {}


def _resolve_token(cmdline_token: str) -> str:
    """
    Token 优先级：
    1. 命令行 --token
    2. 同级目录 config.json 中的 "token" 字段
    3. MINERU_TOKEN 环境变量
    """
    if cmdline_token:
        return cmdline_token
    cfg = _load_config()
    token = cfg.get("token", "")
    if token:
        return token
    return os.getenv("MINERU_TOKEN", "")


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _is_url(s: str) -> bool:
    parsed = urlparse(s)
    return parsed.scheme in ("http", "https")


# ==================== 核心函数 ====================

def get_upload_urls(files: list[dict], model: str, token: str, base_url: str) -> tuple[str, list[str]]:
    """通过 /api/v4/file-urls/batch 获取预签名上传 URL 列表。

    Returns:
        (batch_id, [presigned_url, ...])
    """
    url = f"{base_url}/file-urls/batch"
    payload = {
        "files": files,
        "model_version": model,
    }
    resp = requests.post(url, headers=_headers(token), json=payload, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"申请上传链接失败: {result}")

    data = result.get("data", {})
    batch_id = data.get("batch_id", "")
    file_urls = data.get("file_urls", [])
    if not batch_id or not file_urls:
        raise RuntimeError(f"API 返回异常，无 batch_id/file_urls: {result}")

    return batch_id, file_urls


def upload_file_to_presigned(filepath: str, presigned_url: str) -> None:
    """将本地文件 PUT 到 MinerU 预签名 URL（无需 Content-Type）。"""
    abs_path = os.path.abspath(filepath)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"文件不存在: {abs_path}")

    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
    print(f"[UPLOAD] 正在直传到 MinerU OSS ({size_mb:.1f} MB) ...")

    with open(abs_path, "rb") as f:
        resp = requests.put(presigned_url, data=f, timeout=120)

    if resp.status_code not in (200, 204):
        raise RuntimeError(f"直传失败: HTTP {resp.status_code} - {resp.text[:200]}")

    print("[UPLOAD] 直传完成，MinerU 已开始解析。")


def submit_task_by_url(pdf_url: str, model: str, token: str, base_url: str) -> str:
    """提交公网 URL 解析任务，返回 task_id。"""
    url = f"{base_url}/extract/task"
    payload = {"url": pdf_url, "model_version": model}

    resp = requests.post(url, headers=_headers(token), json=payload, timeout=30)
    resp.raise_for_status()

    result = resp.json()
    if result.get("code") != 0:
        raise RuntimeError(f"提交任务失败: {result}")

    data = result.get("data", {})
    if isinstance(data, dict):
        return data.get("task_id", "")
    return data


def poll_batch(batch_id: str, data_id: str, token: str, base_url: str) -> dict:
    """轮询 batch 任务直到完成，返回单文件结果数据。"""
    status_url = f"{base_url}/extract-results/batch/{batch_id}"

    for i in range(MAX_POLL_COUNT):
        resp = requests.get(status_url, headers=_headers(token), timeout=30)
        resp.raise_for_status()

        result = resp.json()
        data = result.get("data", {})
        extract_result = data.get("extract_result", [])

        # 找到匹配 data_id 的条目
        item = None
        for r in extract_result:
            if r.get("data_id") == data_id:
                item = r
                break

        state = item.get("state", "unknown") if item else "unknown"

        # 进度指示
        dots = "." * ((i % 3) + 1)
        print(f"\r[POLL] 状态: {state}{dots:<3}", end="", flush=True)

        if state == "done":
            print()
            return item

        if state == "failed":
            print()
            raise RuntimeError(f"解析任务失败: {item}")

        time.sleep(POLL_INTERVAL)

    print()
    raise TimeoutError(f"轮询超时，任务仍未完成。Batch ID: {batch_id}")


def poll_task(task_id: str, token: str, base_url: str) -> dict:
    """轮询单任务直到完成，返回结果数据。"""
    status_url = f"{base_url}/extract/task/{task_id}"

    for i in range(MAX_POLL_COUNT):
        resp = requests.get(status_url, headers=_headers(token), timeout=30)
        resp.raise_for_status()

        result = resp.json()
        data = result.get("data", {})
        state = data.get("state", "unknown")

        dots = "." * ((i % 3) + 1)
        print(f"\r[POLL] 状态: {state}{dots:<3}", end="", flush=True)

        if state == "done":
            print()
            return data

        if state == "failed":
            print()
            raise RuntimeError(f"解析任务失败: {data}")

        time.sleep(POLL_INTERVAL)

    print()
    raise TimeoutError(f"轮询超时，任务仍未完成。Task ID: {task_id}")


def download_and_extract_md(zip_url: str, output_path: str) -> None:
    """下载结果 ZIP 并提取 full.md 及专属 images/ 到指定路径。

    每张论文拥有独立的图片目录，避免多篇 PDF 解析时图片互相覆盖。
    目录结构：
        output.md
        output/                  ← 与 .md 文件同名的专属目录
            └── images/
                ├── figure-1.jpg
                └── figure-2.jpg

    图片按 Markdown 中引用的出现顺序重命名为 figure-1.jpg、figure-2.jpg ...
    并同步更新 Markdown 中的引用路径。
    """
    print(f"[DOWNLOAD] 正在下载结果 ZIP ...")

    # 下载 ZIP（带重试，应对间歇性网络错误）
    max_retries = 5
    for attempt in range(max_retries):
        try:
            resp = requests.get(zip_url, timeout=300)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = (attempt + 1) * 10
            print(f"[DOWNLOAD] 下载失败 ({type(e).__name__})，{wait}s 后重试 ({attempt + 1}/{max_retries})...")
            time.sleep(wait)

    out_path = Path(output_path)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 专属目录：与 .md 文件同名（不含扩展名）
    paper_dir = out_dir / out_path.stem
    img_dir = paper_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    # 清理该专属目录中的旧残留图片（避免重复解析时残留上一批图片）
    for fpath in img_dir.iterdir():
        if not fpath.is_file():
            continue
        name = fpath.name
        # 删除旧的 figure-N.ext 或哈希名图片
        if (
            re.match(r"^figure-\d+\.(jpg|jpeg|png|webp|gif)$", name, re.I)
            or re.match(r"^[0-9a-f]{32,64}\.(jpg|jpeg|png|webp|gif)$", name, re.I)
        ):
            fpath.unlink()

    zip_bytes = io.BytesIO(resp.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        # 查找 full.md
        md_name = None
        for name in zf.namelist():
            if name.lower().endswith("full.md"):
                md_name = name
                break

        if not md_name:
            print(f"[WARN] ZIP 中未找到 full.md，包含文件: {zf.namelist()}")
            return

        # 读取 full.md 内容
        md_content = zf.read(md_name).decode("utf-8")

        # 1. 按 Markdown 引用出现顺序提取旧图片文件名（匹配 ![](images/xxx.jpg)）
        refs = re.findall(r"!\[.*?\]\(images/([^)]+)\)", md_content)
        seen = set()
        ordered_old_bases: list[str] = []
        for r in refs:
            base = Path(r).name
            if base not in seen:
                seen.add(base)
                ordered_old_bases.append(base)

        # 2. 建立重命名映射（按 Markdown 引用顺序编号）
        rename_map: dict[str, str] = {}
        for i, old_base in enumerate(ordered_old_bases, start=1):
            ext = Path(old_base).suffix
            new_name = f"figure-{i}{ext}"
            rename_map[old_base] = new_name

        # 3. 从 ZIP 提取图片并按新名写入专属目录
        extracted_images = 0
        for old_base, new_name in rename_map.items():
            zip_path = f"images/{old_base}"
            if zip_path not in zf.namelist():
                print(f"[WARN] ZIP 中未找到图片: {zip_path}")
                continue
            img_data = zf.read(zip_path)
            img_path = img_dir / new_name
            with open(img_path, "wb") as f:
                f.write(img_data)
            extracted_images += 1

        # 4. 同步替换 Markdown 中的图片引用路径
        #    从 ![](images/xxx.jpg) 改为 ![[stem]/images/xxx.jpg)
        img_prefix = f"{out_path.stem}/images"
        for old_base, new_name in rename_map.items():
            # 替换 images/old_name → stem/images/new_name
            md_content = md_content.replace(
                f"images/{old_base}", f"{img_prefix}/{new_name}"
            )

        # 写入更新后的 Markdown
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"[SAVE] Markdown 已提取并写入: {out_path}")

        if extracted_images:
            print(f"[SAVE] 已提取 {extracted_images} 张图片到: {img_dir}")


def save_outputs(result: dict, output_path: str | None, save_json: bool):
    """保存结果到文件或打印到 stdout。"""
    full_zip_url = result.get("full_zip_url", "")
    markdown = result.get("markdown", "")

    if not full_zip_url:
        print("[WARN] 结果中无 full_zip_url，无法下载解析结果。")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if output_path:
        # 下载 ZIP 并提取 full.md
        download_and_extract_md(full_zip_url, output_path)
    else:
        print(f"\n[INFO] 解析结果 ZIP 包: {full_zip_url}")
        print("         请手动下载 ZIP 获取 full.md 及 JSON 文件。")

    if save_json:
        json_path = (output_path or "output") + ".json"
        Path(json_path).parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[SAVE] 结果摘要 JSON 已写入: {json_path}")


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="MinerU 官方 API 便捷客户端（v4 原生直传版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 1. 解析公网 PDF（URL 直接传入）
  python mineru_client.py "https://example.com/doc.pdf"

  # 2. 解析本地 PDF（默认输出到 parsed/ 目录，与 download/ 同级）
  #    输入: papers/download/report.pdf
  #    默认输出: papers/parsed/report.md
  #    图片目录: papers/parsed/report/images/
  python mineru_client.py "papers/download/report.pdf"

  # 3. 显式指定输出路径
  python mineru_client.py report.pdf -o "output/report.md"

  # 4. 使用 pipeline 模型（速度更快，成本低）
  python mineru_client.py report.pdf --model pipeline

  # 5. 同时保存结果摘要 JSON
  python mineru_client.py report.pdf --json

配置方式:
  --token          命令行传入（优先级最高）
  config.json      脚本同级目录创建 JSON 文件: {"token": "..."}
  MINERU_TOKEN     环境变量（优先级最低）
""",
    )
    parser.add_argument("input", help="PDF 公网 URL 或本地文件路径")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=["vlm", "pipeline", "MinerU-HTML"],
        help="解析模型: vlm(高精度,默认) / pipeline(速度快) / MinerU-HTML",
    )
    parser.add_argument(
        "-o", "--output",
        help="输出 Markdown 文件路径（默认打印到终端）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="同时保存完整 API 返回的 JSON 结果",
    )
    parser.add_argument(
        "--token",
        default="",
        help="MinerU API Token（优先级高于 config.json 和环境变量）",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API 基础 URL（默认: {DEFAULT_BASE_URL}）",
    )

    args = parser.parse_args()

    # Token 解析
    token = _resolve_token(args.token)
    if not token:
        print(
            "[ERROR] 缺少 API Token。请选择以下任一方式配置：\n"
            "  1. 命令行: --token <your_token>\n"
            "  2. 配置文件: 在脚本同级目录创建 config.json，写入 {\"token\": \"...\"}\n"
            "  3. 环境变量: set MINERU_TOKEN=<your_token>\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # 判断输入类型
    if _is_url(args.input):
        pdf_url = args.input
        print(f"[INFO] 解析公网 URL: {pdf_url}")
        task_id = submit_task_by_url(pdf_url, args.model, token, args.base_url)
        print(f"[INFO] 使用模型: {args.model}")
        print(f"[INFO] Task ID: {task_id}")
        result = poll_task(task_id, token, args.base_url)
    else:
        # 本地文件：通过 MinerU 预签名 URL 直传
        abs_path = os.path.abspath(args.input)
        if not os.path.isfile(abs_path):
            print(f"[ERROR] 文件不存在: {abs_path}", file=sys.stderr)
            sys.exit(1)

        filename = os.path.basename(abs_path)
        print(f"[INFO] 本地文件: {abs_path}")

        # 1. 申请预签名上传链接
        file_infos = [{"name": filename, "data_id": filename}]
        batch_id, presigned_urls = get_upload_urls(file_infos, args.model, token, args.base_url)
        presigned_url = presigned_urls[0]

        print(f"[INFO] Batch ID: {batch_id}")
        print(f"[INFO] 使用模型: {args.model}")

        # 2. PUT 上传文件
        upload_file_to_presigned(abs_path, presigned_url)

        # 3. 轮询 batch 结果
        result = poll_batch(batch_id, filename, token, args.base_url)

    print(f"[INFO] 解析完成，结果字段: {list(result.keys())}")

    # 自动推断默认输出路径（本地 PDF 且未指定 -o 时）
    if not args.output and not _is_url(args.input):
        input_path = Path(args.input).resolve()
        # 若 PDF 在 download/ 目录，默认输出到同级的 parsed/
        if input_path.parent.name.lower() == "download":
            parsed_dir = input_path.parent.parent / "parsed"
        else:
            parsed_dir = input_path.parent / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        args.output = str(parsed_dir / f"{input_path.stem}.md")
        print(f"[INFO] 未指定 -o，默认输出到: {args.output}")

    # 输出
    save_outputs(result, args.output, args.json)
    print("[DONE] 全部完成。")


if __name__ == "__main__":
    main()
