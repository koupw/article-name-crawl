"""analyze.py 纯函数单元测试"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyze import _slugify, _make_slug, _resolve_analysis_dir


class TestSlugify:
    def test_plain(self):
        assert _slugify("hello_world") == "hello_world"

    def test_spaces(self):
        assert _slugify("hello world test") == "hello_world_test"

    def test_special_chars(self):
        assert _slugify('bad:char*?"<>') == "bad_char"

    def test_leading_trailing(self):
        assert _slugify("._trim_.") == "trim"


class TestMakeSlug:
    def test_smith_comma(self):
        slug = _make_slug({"first_author": "Smith, J.", "year": 2026, "title": "Multi-Band FMCW Laser Ranging"})
        assert slug.startswith("Smith_2026")

    def test_dot_smith(self):
        slug = _make_slug({"first_author": "J. Smith", "year": 2026, "title": "Multi-Band FMCW Laser Ranging"})
        assert slug.startswith("Smith_2026")

    def test_given_surname(self):
        slug = _make_slug({"first_author": "John Smith", "year": 2026, "title": "Multi-Band FMCW Laser Ranging"})
        assert slug.startswith("Smith_2026")

    def test_no_author(self):
        slug = _make_slug({"year": 2023, "title": "Quantum Optics Experiment"})
        assert slug.startswith("2023_quantum_optics") or slug.startswith("2023_quantum_optics_experiment")

    def test_no_metadata(self):
        slug = _make_slug({})
        assert slug == "unknown_paper"


class TestResolveAnalysisDir:
    def test_cmdline_override(self):
        from config.loader import AppConfig
        cfg = AppConfig(analysis_dir="papers/analysis")
        result = _resolve_analysis_dir("/tmp/foo", cfg)
        assert result == Path("/tmp/foo").resolve()

    def test_config_analysis_dir_relative(self):
        from config.loader import AppConfig
        cfg = AppConfig(analysis_dir="papers/analysis", vault_path="")
        result = _resolve_analysis_dir(None, cfg)
        # 相对路径且无 vault_path → cwd 下的 papers/analysis
        assert result.name == "analysis"
        assert result.parent.name == "papers"

    def test_config_analysis_dir_with_vault(self):
        from config.loader import AppConfig
        cfg = AppConfig(analysis_dir="papers/analysis", vault_path="/home/user/vault")
        result = _resolve_analysis_dir(None, cfg)
        assert result == (Path("/home/user/vault") / "papers" / "analysis").resolve()

    def test_fallback_to_vault_papers_dir(self):
        from config.loader import AppConfig
        # analysis_dir 为空字符串时不应使用
        cfg = AppConfig(analysis_dir="", vault_path="/vault", papers_dir="papers")
        # 空 analysis_dir → 跳过 → vault_path/papers_dir
        result = _resolve_analysis_dir(None, cfg)
        assert result == (Path("/vault") / "papers").resolve()
