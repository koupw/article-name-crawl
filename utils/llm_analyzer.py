#!/usr/bin/env python3
"""
LLM 深度分析引擎

功能：
1. 调用 OpenAI 兼容 API（DeepSeek / OpenAI 等）进行论文深度分析
2. 优化版 14 章 Prompt 模板（执行摘要 + 14 章深度层）
3. Map-Reduce 长文本处理（>6000 tokens 拆分为 3000/200 overlap）
4. 5 维度评分（创新/实验/实用/写作/影响），支持动态权重
5. 中英文输出，图片引用统一转换为标准 markdown 格式
"""

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Callable, Optional

import requests

logger = logging.getLogger(__name__)

# ==================== 常量 ====================

# Map-Reduce 阈值
CHUNK_SIZE_TOKENS = 3000
CHUNK_OVERLAP_TOKENS = 200
MAX_TOKENS_THRESHOLD = 6000

# 评分维度默认权重
DEFAULT_WEIGHTS = {
    "innovation": 0.25,
    "experiment": 0.25,
    "practical": 0.20,
    "writing": 0.15,
    "influence": 0.15,
}

# 双语章节标题映射
SECTION_HEADERS = {
    "zh": {
        "exec_summary": "执行摘要",
        "core_info": "核心信息",
        "abstract": "摘要翻译",
        "background": "研究背景与动机",
        "problem": "研究问题",
        "method": "方法概述",
        "experiments": "实验结果",
        "deep_analysis": "深度分析",
        "advantages": "方法优势详解",
        "limitations": "局限性分析",
        "applicability": "适用性与场景分析",
        "comparison": "与相关论文对比",
        "roadmap": "技术路线定位",
        "future": "未来工作建议",
        "assessment": "我的综合评价",
    },
    "en": {
        "exec_summary": "Executive Summary",
        "core_info": "Core Information",
        "abstract": "Abstract & Translation",
        "background": "Research Background & Motivation",
        "problem": "Research Problem",
        "method": "Method Overview",
        "experiments": "Experimental Results",
        "deep_analysis": "In-Depth Analysis",
        "advantages": "Method Advantages",
        "limitations": "Limitations Analysis",
        "applicability": "Applicability & Scenarios",
        "comparison": "Comparison with Related Work",
        "roadmap": "Technical Roadmap",
        "future": "Future Work Suggestions",
        "assessment": "Assessment",
    },
}


def _estimate_tokens(text: str) -> int:
    """粗略估计 token 数（中文 1 字 ≈ 1 token，英文 1 词 ≈ 1.3 token）"""
    # 简单启发式：中文字符 + 英文单词数 * 1.3
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    english_words = len(re.findall(r"[a-zA-Z]+", text))
    return int(chinese_chars + english_words * 1.3)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """按近似 token 数拆分文本，保留段落边界。"""
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)
        if current_tokens + para_tokens > chunk_size and current:
            chunks.append("\n\n".join(current))
            # 保留 overlap 段落
            overlap_tokens = 0
            overlap_paras: list[str] = []
            for p in reversed(current):
                pt = _estimate_tokens(p)
                if overlap_tokens + pt > overlap:
                    break
                overlap_paras.insert(0, p)
                overlap_tokens += pt
            current = overlap_paras
            current_tokens = overlap_tokens
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))
    return chunks


# ==================== Prompt 模板 ====================

_SYSTEM_PROMPT_ZH = """你是一位资深学术研究专家，擅长对学术论文进行系统性、批判性深度分析。
你的任务是根据提供的论文全文（Markdown 格式，含图片引用），生成一份结构化的深度分析报告。

输出要求：
1. 使用 Markdown 格式，所有数学公式使用标准 LaTeX（行内 $...$，块级 $$...$$）。
2. 图片引用必须使用标准 Markdown 格式：`![Figure N](images/figure-N.jpg)`，不要写完整路径，不要 URL 编码。
3. 评分必须客观、有理有据，分数精确到 0.1。
4. 若文本信息不足，标注 "[原文未明确说明]"，不要编造。
5. 保持学术严谨性，区分 "论文声称" 与 "你的分析"。
"""

_SYSTEM_PROMPT_EN = """You are a senior academic research expert specializing in systematic, critical deep analysis of scholarly papers.
Your task is to generate a structured in-depth analysis report based on the provided full paper (Markdown format with image references).

Output requirements:
1. Use Markdown format. All math formulas in standard LaTeX (inline $...$, block $$...$$).
2. Image references must use standard Markdown format: `![Figure N](images/figure-N.jpg)`, no full paths, no URL encoding.
3. Scores must be objective and justified, precise to 0.1.
4. If information is insufficient, mark "[not explicitly stated in the original text]", do not fabricate.
5. Maintain academic rigor; distinguish between "the paper claims" and "your analysis".
"""

_EXEC_SUMMARY_PROMPT_ZH = """请先阅读以下论文全文，然后生成一份【执行摘要】（Executive Summary），限制在 400 字以内。

执行摘要必须包含：
- 研究目标（1 句话）
- 核心方法（1-2 句话）
- 关键实验结果（1-2 句话，附具体数字）
- 主要贡献 / 实际意义（1 句话）
- 一句话结论（本文是否值得精读）

论文全文：
{paper_text}
"""

_EXEC_SUMMARY_PROMPT_EN = """Please read the following full paper and generate an Executive Summary within 400 words.

The Executive Summary must include:
- Research objective (1 sentence)
- Core method (1-2 sentences)
- Key experimental results (1-2 sentences with specific numbers)
- Main contribution / practical significance (1 sentence)
- One-sentence verdict (whether this paper is worth deep reading)

Full paper text:
{paper_text}
"""

_FULL_ANALYSIS_PROMPT_ZH = """请基于以下论文全文，生成完整的深度分析报告。

报告结构（必须严格包含以下 14 个章节，使用对应的双语标题）：

# 执行摘要
[400 字以内的精炼总结，含研究目标、核心方法、关键结果、主要贡献、精读建议]

# 核心信息
- 论文标题：
- 作者 & 机构：
- 发表时间 / 会议 / 期刊：
- 论文链接：
- 代码 / 数据是否开源：

# 摘要翻译
### 英文摘要原文
[粘贴原文]

### 中文翻译
[流畅、准确的中文翻译]

### 核心要点提炼
- 研究背景：
- 研究动机：
- 核心方法：
- 主要结果：
- 研究意义：

# 研究背景与动机
## 领域现状
[该领域当前发展状况]

## 现有方法局限性
[深入分析现有方法存在的问题]

## 研究动机
[为什么需要这项研究]

# 研究问题
## 核心研究问题
[清晰、准确地描述论文要解决的核心问题]

## 子问题分解
[如有，分解为子问题]

# 方法概述
## 核心思想
[用通俗易懂的语言解释方法核心思想]

## 方法框架
### 整体架构
[描述方法整体架构，包括主要组件和关系]

**架构图选择原则**：
1. 优先使用论文中的现成图：`![Figure N](images/figure-N.jpg)`
2. 仅在无图时自行描述

### 各模块详细说明
[逐个模块描述功能、输入、输出、处理流程、关键技术、数学公式]

## 关键创新
1. [创新点1] - [为什么重要]
2. [创新点2] - [为什么重要]
3. [创新点3] - [为什么重要]

# 实验结果
## 实验目标
[本实验要验证什么]

## 数据集
| 数据集 | 样本数 | 特征维度 | 类别数 | 数据类型 |
|--------|--------|----------|--------|----------|

## 实验设置
- 基线方法：
- 评估指标：
- 实验环境：
- 超参数设置：

## 主要结果
### 主实验结果
[表格：方法 vs 数据集-指标，含标准差，粗体标最优]

### 结果分析
[对主实验结果的详细分析]

## 消融实验
[如有，列出设计思路和结果]

## 实验结果图
[插入论文中的实验结果图：`![Figure N](images/figure-N.jpg)`]

# 深度分析
## 研究价值评估
### 理论贡献
- [贡献1]
- [贡献2]

### 实际应用价值
- [场景1]
- [场景2]

### 领域影响
- 短期、中期、长期影响

## 方法优势详解
### 优势1
- 描述、技术基础、实验验证、对比分析

### 优势2
[类似格式]

## 局限性分析
### 局限1
- 描述、表现、原因、影响、可能的解决方案

### 局限2
[类似格式]

## 适用性与场景分析
### 适用场景
### 不适用场景

# 与相关论文对比
### 对比论文选择依据
### 相关论文1
#### 基本信息、方法对比表、性能对比表、关系分析

### 对比总结

# 技术路线定位
## 所属技术路线
## 技术路线发展历程
## 本文在技术路线中的位置

# 未来工作建议
## 作者建议的未来工作
## 基于分析的未来方向
## 改进建议

# 我的综合评价
## 价值评分
### 总体评分
**X.X/10** - [评分理由简述]

### 分项评分（必须严格使用以下表格格式，不得省略！）
| 评分维度 | 分数 | 评分理由 |
|----------|------|----------|
| 创新性 | X.X/10 | [具体理由，不少于 15 字] |
| 实验充分性 | X.X/10 | [具体理由，不少于 15 字] |
| 实用性 | X.X/10 | [具体理由，不少于 15 字] |
| 写作质量 | X.X/10 | [具体理由，不少于 15 字] |
| 影响力 | X.X/10 | [具体理由，不少于 15 字] |

## 重点关注
### 值得关注的技术点
### 需要深入理解的部分

## 快速决策建议
- 精读价值：高 / 中 / 低
- 推荐人群：
- 预计阅读耗时：

论文全文：
{paper_text}

[注意：图片引用请统一使用 `![Figure N](images/figure-N.jpg)` 格式]
"""

_FULL_ANALYSIS_PROMPT_EN = """Please generate a complete in-depth analysis report based on the following full paper text.

The report must strictly contain the following 14 chapters with bilingual headers:

# Executive Summary
[Concise summary within 400 words: objective, core method, key results, contribution, reading recommendation]

# Core Information
- Title:
- Authors & Affiliations:
- Publication Date / Venue:
- Links:
- Open-source code/data:

# Abstract & Translation
### Original Abstract
[paste original]

### Translation
[fluent, accurate translation]

### Key Takeaways
- Background:
- Motivation:
- Core Method:
- Main Results:
- Significance:

# Research Background & Motivation
## Domain Status
## Limitations of Existing Methods
## Research Motivation

# Research Problem
## Core Problem
## Sub-problem Decomposition

# Method Overview
## Core Idea
## Method Framework
### Overall Architecture
[Use paper figures first: `![Figure N](images/figure-N.jpg)`]
### Module Details
## Key Innovations

# Experimental Results
## Objectives
## Datasets
## Settings
## Main Results
### Result Tables
### Analysis
## Ablation Studies
## Result Figures

# In-Depth Analysis
## Research Value
## Method Advantages
## Limitations
## Applicability

# Comparison with Related Work
# Technical Roadmap
# Future Work
# Assessment

### Dimension Scores (must use this exact table format, do not omit!)
| Dimension | Score | Justification |
|-----------|-------|---------------|
| Innovation | X.X/10 | [specific reason, at least 15 words] |
| Experiment Thoroughness | X.X/10 | [specific reason, at least 15 words] |
| Practicality | X.X/10 | [specific reason, at least 15 words] |
| Writing Quality | X.X/10 | [specific reason, at least 15 words] |
| Influence | X.X/10 | [specific reason, at least 15 words] |

Paper text:
{paper_text}

[Note: Use `![Figure N](images/figure-N.jpg)` for all image references.]
"""

_SYNTHESIZE_PROMPT_ZH = """你之前已经阅读了这篇论文的多个片段分析。现在请将以下各片段的分析综合为一份完整的、连贯的深度分析报告。

要求：
1. 消除片段间的重复内容。
2. 确保逻辑一致性（例如前后评分需一致）。
3. 补充跨章节的关联分析（如实验结果如何支撑方法优势）。
4. 输出完整的 14 章结构（见下方模板）。
5. 图片引用使用 `![Figure N](images/figure-N.jpg)`。

片段分析汇总：
{chunk_analyses}

请直接输出完整的分析报告。
"""

_SYNTHESIZE_PROMPT_EN = """You have previously analyzed multiple chunks of the same paper. Now synthesize the following chunk analyses into one coherent, complete in-depth report.

Requirements:
1. Eliminate redundancy across chunks.
2. Ensure logical consistency (e.g., scores should align).
3. Add cross-chapter connections (e.g., how experiments support method advantages).
4. Output the full 14-chapter structure.
5. Use `![Figure N](images/figure-N.jpg)` for images.

Chunk analyses:
{chunk_analyses}

Please output the complete analysis report directly.
"""


# ==================== LLM 调用封装 ====================

class LLMClient:
    """通用 OpenAI 兼容格式 LLM 客户端"""

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout: int = 120,
    ):
        if not api_key:
            raise ValueError("LLM API Key 不能为空。请通过配置或环境变量 LLM_API_KEY 设置。")
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.6,
        max_tokens: int = 8192,
    ) -> str:
        """调用 LLM chat completion，返回生成的文本。"""
        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        logger.debug("LLM request -> %s, model=%s", url, self.model)

        # 429 限流重试（指数退避：2s → 4s → 8s → 16s → 32s）
        max_429_retries = 5
        for attempt in range(max_429_retries):
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code == 429 and attempt < max_429_retries - 1:
                delay = 2 ** (attempt + 1)  # 2, 4, 8, 16 seconds
                logger.warning(
                    "LLM rate limited (429), retry %d/%d in %ds...",
                    attempt + 1, max_429_retries - 1, delay,
                )
                time.sleep(delay)
                continue
            break  # not 429 or last attempt

        if not resp.ok:
            status = resp.status_code
            detail = resp.text[:500] if resp.text else "(no body)"
            if status == 429:
                raise requests.HTTPError(
                    f"LLM API 限流（429），已重试 {max_429_retries} 次仍失败。"
                    f"免费 API 有频率限制，请稍后重试或更换 API Key。\n{detail}",
                    response=resp,
                )
            raise requests.HTTPError(
                f"{status} {resp.reason} for {url}: {detail}",
                response=resp,
            )
        data = resp.json()

        message = data["choices"][0]["message"]
        content = message.get("content") or ""
        # 推理模型（如 deepseek-v4-flash-free）output 可能在 reasoning_content，
        # content 为空时 fallback 到 reasoning_content
        if not content:
            reasoning = message.get("reasoning_content") or ""
            if reasoning:
                content = reasoning
                logger.debug("LLM fallback to reasoning_content (%d chars)", len(reasoning))
        usage = data.get("usage", {})
        logger.debug(
            "LLM response <- prompt_tokens=%s completion_tokens=%s",
            usage.get("prompt_tokens"),
            usage.get("completion_tokens"),
        )
        return content


# ==================== 分析引擎 ====================

class LLMAnalyzer:
    """LLM 深度分析引擎"""

    def __init__(
        self,
        llm_client: LLMClient,
        language: str = "zh",
        weights: Optional[dict] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Args:
            llm_client: 已初始化的 LLM 客户端
            language: 输出语言 (zh/en)
            weights: 评分权重字典，默认 DEFAULT_WEIGHTS
            progress_callback: 进度回调
        """
        self.llm = llm_client
        self.language = language
        self.weights = weights or dict(DEFAULT_WEIGHTS)
        self._cb = progress_callback

    def _notify(self, msg: str) -> None:
        if self._cb:
            self._cb(msg)
        else:
            logger.info(msg)

    def _fix_image_refs(self, text: str) -> str:
        """统一图片引用为 note-relative 标准 markdown（Obsidian 可靠格式）。"""
        # 1. 标准 md 图片 → 保持标准格式，修复 images/ 相对路径
        text = re.sub(
            r"!\[([^\]]*)\]\((?:[^)]*?/)?(images/figure-[^)]+)\)",
            r"![\1](\2)",
            text,
            flags=re.IGNORECASE,
        )
        # 2. LLM 输出的裸 wikilink → 标准 md
        text = re.sub(
            r"!\[\[figure-([\d-]+[a-z]?)\.(jpg|jpeg|png|webp|gif)\|?\d*\]\]",
            r"![Figure \1](images/figure-\1.\2)",
            text,
            flags=re.IGNORECASE,
        )
        # 3. wikilink 含 images/ 路径 → 标准 md（清理旧格式）
        text = re.sub(
            r"!\[\[(?:.*?/)?images/(figure-[\d-]+[a-z]?)\.(jpg|jpeg|png|webp|gif)\|?\d*\]\]",
            r"![Figure \1](images/figure-\1.\2)",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _analyze_chunk(self, chunk_text: str, is_first: bool) -> str:
        """分析单个文本片段。"""
        sys_prompt = (
            _SYSTEM_PROMPT_ZH if self.language == "zh" else _SYSTEM_PROMPT_EN
        )
        # 非首个片段使用简化 prompt（不需要完整的 14 章，而是提取信息）
        if is_first:
            user_prompt = (
                _FULL_ANALYSIS_PROMPT_ZH if self.language == "zh" else _FULL_ANALYSIS_PROMPT_EN
            ).format(paper_text=chunk_text)
        else:
            # 后续片段：聚焦补充信息
            tmpl = (
                "以下是论文的后续片段。请补充提取以下信息（如果该片段不包含某类信息，标注\"[该片段未提及]\"）：\n"
                "- 方法细节与公式\n"
                "- 实验设置与具体数字\n"
                "- 消融实验结果\n"
                "- 局限性讨论\n"
                "- 未来工作建议\n\n"
                "片段内容：\n{paper_text}"
                if self.language == "zh"
                else (
                    "This is a subsequent chunk of the paper. Please extract the following supplementary information "
                    "(mark \"[not mentioned]\" if absent):\n"
                    "- Method details and formulas\n"
                    "- Experimental settings and specific numbers\n"
                    "- Ablation study results\n"
                    "- Limitations discussion\n"
                    "- Future work suggestions\n\n"
                    "Chunk content:\n{paper_text}"
                )
            )
            user_prompt = tmpl.format(paper_text=chunk_text)

        return self.llm.chat(sys_prompt, user_prompt, temperature=0.6, max_tokens=16384)

    def analyze(self, md_text: str, metadata: Optional[dict] = None) -> dict:
        """
        对整篇论文 Markdown 进行深度分析。

        Args:
            md_text: 论文全文 Markdown 内容（含图片引用）。
            metadata: 可选元数据（title, authors, year, venue, url 等），
                      用于前置信息补充。

        Returns:
            {
                "report_md": "完整的分析报告 Markdown 字符串",
                "exec_summary": "执行摘要字符串",
                "scores": {"overall": float, "innovation": float, ...},
                "tokens_used": int,  # 仅记录，非精确值
            }
        """
        self._notify("开始 LLM 深度分析...")

        # 1. 图片引用预修复（让 LLM 也看到正确格式，减少它乱写路径）
        md_text = self._fix_image_refs(md_text)

        # 2. 预置元数据到文本头部（如果提供）
        if metadata:
            header = self._build_metadata_header(metadata)
            full_text = header + "\n\n" + md_text
        else:
            full_text = md_text

        # 3. 判断是否需要 Map-Reduce
        total_tokens = _estimate_tokens(full_text)
        self._notify(f"论文文本预估 token 数: {total_tokens}")

        if total_tokens <= MAX_TOKENS_THRESHOLD:
            # 单轮分析
            self._notify("文本在阈值内，执行单轮全量分析...")
            report = self._analyze_single(full_text)
        else:
            # Map-Reduce
            self._notify("文本较长，启用 Map-Reduce 分段分析...")
            chunks = _split_text(full_text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)
            self._notify(f"拆分为 {len(chunks)} 个片段")
            chunk_results = []
            for i, chunk in enumerate(chunks, 1):
                self._notify(f"分析片段 {i}/{len(chunks)} ...")
                chunk_report = self._analyze_chunk(chunk, is_first=(i == 1))
                chunk_results.append(f"--- 片段 {i} 分析 ---\n{chunk_report}")
                time.sleep(0.5)  # 轻微节流，避免速率限制

            self._notify("综合各片段分析结果...")
            synthesize_prompt = (
                _SYNTHESIZE_PROMPT_ZH if self.language == "zh" else _SYNTHESIZE_PROMPT_EN
            ).format(chunk_analyses="\n\n".join(chunk_results))

            sys_prompt = (
                _SYSTEM_PROMPT_ZH if self.language == "zh" else _SYSTEM_PROMPT_EN
            )
            report = self.llm.chat(
                sys_prompt, synthesize_prompt, temperature=0.5, max_tokens=16384
            )

        # 4. 后处理：再次修复图片引用、确保评分可解析
        report = self._fix_image_refs(report)
        scores = self._extract_scores(report)
        exec_summary = self._extract_exec_summary(report)

        self._notify("LLM 分析完成。")
        return {
            "report_md": report,
            "exec_summary": exec_summary,
            "scores": scores,
            "tokens_used": total_tokens,
        }

    def _analyze_single(self, full_text: str) -> str:
        """单次全量分析（短文本）。"""
        sys_prompt = (
            _SYSTEM_PROMPT_ZH if self.language == "zh" else _SYSTEM_PROMPT_EN
        )
        user_prompt = (
            _FULL_ANALYSIS_PROMPT_ZH if self.language == "zh" else _FULL_ANALYSIS_PROMPT_EN
        ).format(paper_text=full_text)
        return self.llm.chat(sys_prompt, user_prompt, temperature=0.6, max_tokens=16384)

    def _build_metadata_header(self, metadata: dict) -> str:
        """将已知元数据拼装为文本头部，减少 LLM 的幻觉。"""
        lines = ["# 已知论文信息（供参考，分析时请以正文为准）"]
        if self.language == "zh":
            mapping = {
                "title": "标题",
                "authors": "作者",
                "year": "年份",
                "venue": "会议/期刊",
                "url": "链接",
                "doi": "DOI",
                "arxiv_id": "arXiv ID",
            }
        else:
            mapping = {
                "title": "Title",
                "authors": "Authors",
                "year": "Year",
                "venue": "Venue",
                "url": "URL",
                "doi": "DOI",
                "arxiv_id": "arXiv ID",
            }
        for k, label in mapping.items():
            v = metadata.get(k)
            if v:
                lines.append(f"- **{label}**: {v}")
        return "\n".join(lines)

    def _extract_scores(self, report: str) -> dict:
        """从报告中提取评分。支持多种格式：表格、列表、粗体等。"""
        # 匹配模式：维度名 + 分隔符 + 数字/10
        pattern_map = [
            (r"创新(?:性|程度)?", "innovation"),
            (r"实验(?:充分性|评估|设计|验证|结果)?|方法严谨性|结果与论证", "experiment"),
            (r"写作(?:质量|表达|水平)?|(?:论文|文章)?结构", "writing"),
            (r"实用(?:性|价值)?|应[用前]景", "practical"),
            (r"(?:领域|行业)?影响力?|文献与背景", "influence"),
            (r"(?:Overall|总体)(?:\s*Score|\s*评分)?", "overall"),
        ]
        scores: dict[str, float] = {}
        for cn_re, key in pattern_map:
            # 匹配 "维度名：7.5/10" 或 "维度名：7.5。" 两种格式
            # 外层 (?:cn_re) 确保后缀应用于所有 alternation 分支
            pat = rf"(?:{cn_re})\s*[：:*|=\s]*\**\s*(\d+(?:\.\d+)?)(?:\s*/\s*10)?(?=[\s。，,;\n*]|$)"
            m = re.search(pat, report, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                if 1.0 <= val <= 10.0:
                    scores[key] = val

        # 若子维度齐全但缺少 overall，按权重计算
        sub_keys = ["innovation", "experiment", "practical", "writing", "influence"]
        if "overall" not in scores:
            available = [k for k in sub_keys if k in scores]
            if available:
                total_weight = sum(self.weights.get(k, 0.2) for k in available)
                if total_weight > 0:
                    overall = sum(scores[k] * self.weights.get(k, 0.2) / total_weight for k in available)
                    scores["overall"] = round(overall, 1)
        return scores

    def _extract_exec_summary(self, report: str) -> str:
        """提取执行摘要部分。"""
        # 匹配 "# 执行摘要" 或 "## 1. 执行摘要" 等各种编号格式
        header = "执行摘要" if self.language == "zh" else "Executive Summary"
        pat = rf"#+\s*(?:\d+[\.\s]*)?{header}\s*\n(.*?)(?=\n#+\s)"
        m = re.search(pat, report, re.DOTALL)
        if m:
            return m.group(1).strip()
        return ""
