"""筛选逻辑测试"""

import pytest
from conftest import make_paper
from utils.filter import filter_papers
from config.loader import FilterConfig


# ========== 引用数筛选 ==========

def test_filter_min_citations_pass():
    """引用数达标应通过"""
    papers = [make_paper(citations=5)]
    filters = FilterConfig(min_citations=3)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_min_citations_fail():
    """引用数不达标应过滤"""
    papers = [make_paper(citations=1)]
    filters = FilterConfig(min_citations=3)
    assert len(filter_papers(papers, filters)) == 0


def test_filter_min_citations_edge():
    """引用数等于阈值应通过"""
    papers = [make_paper(citations=3)]
    filters = FilterConfig(min_citations=3)
    assert len(filter_papers(papers, filters)) == 1


# ========== 年份筛选 ==========

def test_filter_year_from_pass():
    """年份在起始年份之后应通过"""
    papers = [make_paper(year=2023)]
    filters = FilterConfig(year_from=2020)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_year_from_fail():
    """年份在起始年份之前应过滤"""
    papers = [make_paper(year=2019)]
    filters = FilterConfig(year_from=2020)
    assert len(filter_papers(papers, filters)) == 0


def test_filter_year_to_pass():
    """年份在结束年份之前应通过"""
    papers = [make_paper(year=2022)]
    filters = FilterConfig(year_to=2023)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_year_to_fail():
    """年份在结束年份之后应过滤"""
    papers = [make_paper(year=2024)]
    filters = FilterConfig(year_to=2023)
    assert len(filter_papers(papers, filters)) == 0


def test_filter_year_range():
    """年份在范围内应通过"""
    papers = [make_paper(year=2022)]
    filters = FilterConfig(year_from=2020, year_to=2023)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_year_no_date():
    """无年份的论文在年份筛选时通过（假设年份未知则不禁用）"""
    papers = [make_paper(year=None)]
    filters = FilterConfig(year_from=2020)
    assert len(filter_papers(papers, filters)) == 1


# ========== DOI 筛选 ==========

def test_filter_doi_pass():
    """有 DOI 应通过"""
    papers = [make_paper(doi="10.1234/a")]
    filters = FilterConfig(require_doi=True)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_doi_fail():
    """无 DOI 应过滤"""
    papers = [make_paper(doi=None)]
    filters = FilterConfig(require_doi=True)
    assert len(filter_papers(papers, filters)) == 0


# ========== 开放获取筛选 ==========

def test_filter_open_access_pass():
    """开放获取应通过"""
    papers = [make_paper(is_open_access=True)]
    filters = FilterConfig(open_access_only=True)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_open_access_fail():
    """非开放获取应过滤"""
    papers = [make_paper(is_open_access=False)]
    filters = FilterConfig(open_access_only=True)
    assert len(filter_papers(papers, filters)) == 0


# ========== 组合筛选 ==========

def test_filter_combined_all_pass():
    """所有条件均满足"""
    papers = [make_paper(citations=10, year=2022, doi="10.1234/a")]
    filters = FilterConfig(min_citations=5, year_from=2020, require_doi=True)
    assert len(filter_papers(papers, filters)) == 1


def test_filter_combined_one_fail():
    """任一条件不满足则过滤"""
    papers = [make_paper(citations=10, year=2022, doi="10.1234/a")]
    filters = FilterConfig(min_citations=5, year_from=2023, require_doi=True)
    assert len(filter_papers(papers, filters)) == 0


# ========== 空/边界条件 ==========

def test_filter_no_filters():
    """无筛选条件应全部通过"""
    papers = [make_paper(citations=0)]
    filters = FilterConfig()
    assert len(filter_papers(papers, filters)) == 1


def test_filter_empty_list():
    """空列表应返回空列表"""
    assert filter_papers([], FilterConfig()) == []


def test_filter_multiple_papers():
    """多篇论文混合筛选"""
    papers = [
        make_paper(citations=10, year=2022),
        make_paper(citations=2, year=2022),
        make_paper(citations=10, year=2019),
        make_paper(citations=5, year=2020),
    ]
    filters = FilterConfig(min_citations=5, year_from=2020)
    assert len(filter_papers(papers, filters)) == 2
