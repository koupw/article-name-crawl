"""论文模型测试"""

from conftest import make_paper


def test_year_from_date():
    """有日期时返回正确年份"""
    paper = make_paper(year=2024)
    assert paper.year == 2024


def test_year_no_date():
    """无日期时返回 None"""
    paper = make_paper(year=None)
    assert paper.year is None


def test_authors_str_three_or_less():
    """3 个及以下作者显示全名"""
    paper = make_paper(authors=["Alice", "Bob"])
    assert paper.authors_str == "Alice, Bob"


def test_authors_str_more_than_three():
    """超过 3 个作者显示 et al."""
    paper = make_paper(authors=["Alice", "Bob", "Charlie", "David"])
    assert paper.authors_str == "Alice et al."


def test_authors_str_empty():
    """无作者时返回 Unknown"""
    paper = make_paper(authors=[])
    assert paper.authors_str == "Unknown"


def test_date_str_with_date():
    """有日期时返回 YYYY-MM"""
    paper = make_paper(year=2024)
    assert paper.date_str == "2024-01"


def test_date_str_no_date():
    """无日期时返回 Unknown"""
    paper = make_paper(year=None)
    assert paper.date_str == "Unknown"
