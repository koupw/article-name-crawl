"""llm_analyzer.py 纯函数单元测试"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.llm_analyzer import (
    _estimate_tokens,
    _split_text,
    LLMAnalyzer,
    DEFAULT_WEIGHTS,
)


class TestEstimateTokens:
    def test_english(self):
        # ~30 words → ~39 tokens
        t = _estimate_tokens("The quick brown fox jumps over the lazy dog " * 3)
        assert 35 <= t <= 45

    def test_chinese(self):
        # 36 chars → ~36 tokens
        t = _estimate_tokens("这是一段用于测试的中文文本" * 3)
        assert 25 <= t <= 40

    def test_mixed(self):
        t = _estimate_tokens("中英 mixed 混合 text")
        assert t > 0


class TestSplitText:
    def test_short_text(self):
        chunks = _split_text("hello world", chunk_size=5000, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == "hello world"

    def test_multi_paragraph(self):
        paras = ["para " + str(i) for i in range(20)]
        text = "\n\n".join(paras)
        chunks = _split_text(text, chunk_size=100, overlap=20)
        assert len(chunks) >= 1


class TestExtractScores:
    def test_all_five_dimensions(self):
        class MockLLM:
            api_key = ""
            api_base = ""
            model = ""
            timeout = 1
        a = LLMAnalyzer(llm_client=MockLLM(), language="zh")
        report = """
| 创新性 | 8.5/10 | 新颖 |
| 实验充分性 | 7.8/10 | 数据集丰富 |
| 实用性 | 6.9/10 | 场景广 |
| 写作质量 | 9.0/10 | 结构清晰 |
| 影响力 | 8.0/10 | 高被引 |
"""
        scores = a._extract_scores(report)
        assert "innovation" in scores
        assert "experiment" in scores
        assert "practical" in scores
        assert "writing" in scores
        assert "influence" in scores
        assert "overall" in scores
        expected = round(
            8.5 * 0.25 + 7.8 * 0.25 + 6.9 * 0.20 + 9.0 * 0.15 + 8.0 * 0.15, 1
        )
        assert abs(scores["overall"] - expected) < 0.05

    def test_partial_scores_no_overall(self):
        class MockLLM:
            api_key = ""
            api_base = ""
            model = ""
            timeout = 1
        a = LLMAnalyzer(llm_client=MockLLM(), language="zh")
        report = """
| 创新性 | 8.0/10 | test |
| 实验充分性 | 7.0/10 | test |
"""
        scores = a._extract_scores(report)
        # 只有 2 个维度，仍应计算 overall（用现有维度加权）
        assert "innovation" in scores
        assert "experiment" in scores
        assert "overall" in scores
        # overall 应在 7.0~8.0 之间（权重 0.25+0.25 → 加权平均）
        assert 7.0 <= scores["overall"] <= 8.0

    def test_chinese_colon_separator(self):
        class MockLLM:
            api_key = ""
            api_base = ""
            model = ""
            timeout = 1
        a = LLMAnalyzer(llm_client=MockLLM(), language="zh")
        report = """
创新性：**8.5/10**
"""
        scores = a._extract_scores(report)
        assert scores.get("innovation") == 8.5

    def test_no_influence_no_overall(self):
        """缺 影响力 → 用剩余 4 维度加权计算 overall"""
        class MockLLM:
            api_key = ""
            api_base = ""
            model = ""
            timeout = 1
        a = LLMAnalyzer(llm_client=MockLLM(), language="zh")
        report = """
| 创新性 | 8.5/10 | x |
| 实验充分性 | 7.8/10 | x |
| 实用性 | 6.9/10 | x |
| 写作质量 | 9.0/10 | x |
"""
        scores = a._extract_scores(report)
        assert "influence" not in scores
        assert "overall" in scores  # 4 维仍可计算
