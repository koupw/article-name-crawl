"""去重逻辑测试"""

import pytest
from conftest import make_paper
from utils.dedup import deduplicate, normalize_title, calculate_similarity


# ========== DOI 去重 ==========

def test_dedup_same_doi():
    """相同 DOI 应去重"""
    p1 = make_paper(title="Paper A", doi="10.1234/a")
    p2 = make_paper(title="Paper B", doi="10.1234/a")
    assert len(deduplicate([p1, p2])) == 1


def test_dedup_different_doi():
    """不同 DOI 保留"""
    p1 = make_paper(title="Laser Ranging", doi="10.1234/a")
    p2 = make_paper(title="Quantum Computing", doi="10.1234/b")
    assert len(deduplicate([p1, p2])) == 2


def test_dedup_doi_case_insensitive():
    """DOI 大小写不敏感"""
    p1 = make_paper(title="Paper A", doi="10.1234/AbC")
    p2 = make_paper(title="Paper B", doi="10.1234/abc")
    assert len(deduplicate([p1, p2])) == 1


def test_dedup_no_doi_kept():
    """无 DOI 的不同论文保留"""
    p1 = make_paper(title="Laser Ranging")
    p2 = make_paper(title="Quantum Computing")
    assert len(deduplicate([p1, p2])) == 2


# ========== arXiv ID 去重 ==========

def test_dedup_same_arxiv_id():
    """相同 arXiv ID 应去重"""
    p1 = make_paper(title="Paper A", arxiv_id="2401.12345")
    p2 = make_paper(title="Paper B", arxiv_id="2401.12345")
    assert len(deduplicate([p1, p2])) == 1


def test_dedup_different_arxiv_id():
    """不同 arXiv ID 保留"""
    p1 = make_paper(title="Laser Ranging", arxiv_id="2401.12345")
    p2 = make_paper(title="Quantum Computing", arxiv_id="2402.67890")
    assert len(deduplicate([p1, p2])) == 2


# ========== 标题相似度去重 ==========

def test_dedup_identical_title():
    """完全相同的标题应去重"""
    p1 = make_paper(title="FMCW Laser Ranging System")
    p2 = make_paper(title="FMCW Laser Ranging System")
    assert len(deduplicate([p1, p2])) == 1


def test_dedup_similar_title():
    """微小差异的标题应去重（>85% 阈值）"""
    p1 = make_paper(title="FMCW Laser Ranging System")
    p2 = make_paper(title="FMCW Laser Ranging Systems")
    assert len(deduplicate([p1, p2])) == 1


def test_dedup_no_false_positive():
    """不同论文不被误删"""
    p1 = make_paper(title="Laser Ranging Using FMCW")
    p2 = make_paper(title="Laser Welding Temperature Control")
    assert len(deduplicate([p1, p2])) == 2


def test_dedup_punctuation_normalized():
    """标点符号被归一化后应匹配"""
    p1 = make_paper(title="FMCW Laser Ranging: A Survey")
    p2 = make_paper(title="FMCW Laser Ranging, A Survey")
    assert len(deduplicate([p1, p2])) == 1


# ========== 混合场景 ==========

def test_dedup_three_same_doi():
    """三篇论文两两重复"""
    p1 = make_paper(title="Paper A", doi="10.1234/a")
    p2 = make_paper(title="Paper B", doi="10.1234/a")
    p3 = make_paper(title="Paper C", doi="10.1234/a")
    assert len(deduplicate([p1, p2, p3])) == 1


def test_dedup_priority_doi_over_title():
    """DOI 优先于标题去重"""
    p1 = make_paper(title="Original Title", doi="10.1234/a")
    p2 = make_paper(title="Very Different Title", doi="10.1234/a")
    assert len(deduplicate([p1, p2])) == 1


# ========== 工具函数 ==========

def test_normalize_title():
    """标题标准化"""
    assert normalize_title("  FMCW Laser: A Survey!  ") == "fmcw laser a survey"
    assert normalize_title("Hello-World") == "helloworld"


def test_calculate_similarity_identical():
    """完全相同字符串相似度为 1.0"""
    sim = calculate_similarity("fmcw laser ranging", "fmcw laser ranging")
    assert sim == 1.0


def test_calculate_similarity_different():
    """完全不同字符串相似度接近 0"""
    sim = calculate_similarity("aaa bbb ccc", "xxx yyy zzz")
    assert sim < 0.3
