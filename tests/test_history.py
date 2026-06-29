"""历史记录管理测试"""

import json
import pytest
from pathlib import Path
from datetime import datetime

from conftest import make_paper
from models.paper import Paper
from utils.history import (
    get_paper_key,
    load_history,
    save_history,
    deduplicate_with_history,
    update_history_translations,
    clear_history,
)


@pytest.fixture
def temp_output(tmp_path):
    """临时输出目录"""
    return tmp_path / "papers"


# ========== get_paper_key ==========

def test_key_with_doi():
    """有 DOI 时 key 为 doi:..."""
    paper = make_paper(doi="10.1234/fmcw.2024")
    assert get_paper_key(paper) == "doi:10.1234/fmcw.2024"


def test_key_with_arxiv_id():
    """有 arXiv ID 时 key 为 arxiv:..."""
    paper = make_paper(arxiv_id="2401.12345")
    assert get_paper_key(paper) == "arxiv:2401.12345"


def test_key_with_title():
    """既无 DOI 也无 arXiv ID 时 key 为 title:..."""
    paper = make_paper(title="FMCW Laser Ranging")
    key = get_paper_key(paper)
    assert key.startswith("title:")
    assert "fmcw" in key


# ========== load / save history ==========

def test_load_empty_history(temp_output):
    """加载不存在的文件返回空字典"""
    assert load_history(temp_output) == {}


def test_save_and_load_history(temp_output):
    """保存后再加载，内容一致"""
    history = {
        "doi:10.1234/test": {
            "title": "Test",
            "source": "openalex",
            "domain": "test",
        }
    }
    save_history(temp_output, history)
    loaded = load_history(temp_output)
    assert loaded["doi:10.1234/test"]["title"] == "Test"


def test_load_corrupted_history(temp_output):
    """损坏的历史文件应返回空字典而非崩溃"""
    hist_path = temp_output / "crawled_papers.json"
    temp_output.mkdir(parents=True, exist_ok=True)
    hist_path.write_text("invalid json", encoding="utf-8")
    assert load_history(temp_output) == {}


# ========== deduplicate_with_history ==========

def test_dedup_new_paper(temp_output):
    """新论文应通过去重"""
    paper = make_paper(doi="10.1234/new")
    new_papers, history = deduplicate_with_history([paper], temp_output)
    assert len(new_papers) == 1
    assert len(history) == 1


def test_dedup_existing_paper(temp_output):
    """已有论文应被过滤"""
    save_history(temp_output, {
        "doi:10.1234/fmcw.2024": {
            "title": "FMCW Laser Ranging",
            "source": "openalex",
            "domain": "FMCW",
        }
    })
    paper = make_paper(doi="10.1234/fmcw.2024")
    new_papers, history = deduplicate_with_history([paper], temp_output)
    assert len(new_papers) == 0


def test_dedup_restore_translation(temp_output):
    """历史记录中的翻译应恢复到 paper"""
    save_history(temp_output, {
        "doi:10.1234/fmcw.2024": {
            "title": "FMCW Laser Ranging",
            "source": "openalex",
            "domain": "FMCW",
            "title_zh": "调频连续波激光测距",
        }
    })
    paper = make_paper(doi="10.1234/fmcw.2024")
    assert paper.title_zh is None
    new_papers, history = deduplicate_with_history([paper], temp_output)
    assert len(new_papers) == 0
    assert paper.title_zh == "调频连续波激光测距"


def test_dedup_multiple_papers(temp_output):
    """多篇论文混合"""
    p1 = make_paper(title="New Paper", doi="10.1234/new")
    p2 = make_paper(title="Old Paper", doi="10.1234/old")

    save_history(temp_output, {
        "doi:10.1234/old": {
            "title": "Old Paper",
            "source": "openalex",
            "domain": "test",
        }
    })

    new_papers, history = deduplicate_with_history([p1, p2], temp_output)
    assert len(new_papers) == 1
    assert new_papers[0].title == "New Paper"
    assert len(history) == 2


# ========== update_history_translations ==========

def test_update_translations():
    """翻译结果应更新到历史记录"""
    paper = make_paper(
        doi="10.1234/fmcw",
        title_zh="调频连续波激光测距",
    )
    history = {
        "doi:10.1234/fmcw": {
            "title": "FMCW Laser Ranging",
            "source": "openalex",
            "domain": "FMCW",
        }
    }
    update_history_translations(history, [paper])
    assert history["doi:10.1234/fmcw"]["title_zh"] == "调频连续波激光测距"


def test_update_translations_skip_none():
    """翻译为空的论文不应更新历史"""
    paper = make_paper(doi="10.1234/nozh")
    history = {"doi:10.1234/nozh": {"title": "Untranslated"}}
    update_history_translations(history, [paper])
    assert "title_zh" not in history["doi:10.1234/nozh"]


# ========== clear_history ==========

def test_clear_history(temp_output):
    """清除历史应删除文件"""
    save_history(temp_output, {"test": {"title": "Test"}})
    assert (temp_output / "crawled_papers.json").exists()
    clear_history(temp_output)
    assert not (temp_output / "crawled_papers.json").exists()


def test_clear_nonexistent_history(temp_output):
    """清除不存在的历史不应报错"""
    clear_history(temp_output)
