"""配置加载与验证测试"""

import pytest
from config.loader import load_config, validate_config, get_domains, AppConfig, \
    ResearchDomain, FilterConfig


# ========== pydantic 自动校验测试 ==========

def test_pydantic_priority_range():
    """priority 超出 1-10 应在构造时报错"""
    with pytest.raises(ValueError):
        ResearchDomain(name="test", keywords=["kw"], arxiv_categories=[], priority=0)


def test_pydantic_negative_citations():
    """负数 min_citations 应在构造时报错"""
    with pytest.raises(ValueError):
        FilterConfig(min_citations=-1)


def test_pydantic_year_range():
    """year_from > year_to 应在构造时报错"""
    with pytest.raises(ValueError):
        FilterConfig(year_from=2025, year_to=2020)


def test_pydantic_invalid_translate_backend():
    """未知翻译引擎应在构造时报错"""
    with pytest.raises(ValueError):
        AppConfig(translate_backend="bing")


# ========== validate_config 警告测试 ==========

def test_validate_empty_domains():
    """空领域配置应产生警告"""
    config = AppConfig(vault_path="/tmp")
    warnings = validate_config(config)
    assert any("research_domains 为空" in w for w in warnings)


def test_validate_no_vault_path():
    """无 vault_path 应产生警告"""
    config = AppConfig(
        research_domains={"test": ResearchDomain(name="test", keywords=["kw"], arxiv_categories=[])},
    )
    warnings = validate_config(config)
    assert any("vault_path" in w for w in warnings)


def test_validate_empty_keywords():
    """空关键词应产生警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain(name="test", keywords=[], arxiv_categories=[])},
    )
    warnings = validate_config(config)
    assert any("keywords 为空" in w for w in warnings)


def test_validate_negative_citations():
    """pydantic 已拦截负数，validate_config 不会收到此情况，
    但保留测试确保 filters 可正常构造"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain(name="test", keywords=["laser"], arxiv_categories=[])},
        filters=FilterConfig(min_citations=0),
    )
    warnings = validate_config(config)
    assert not any("负数" in w for w in warnings)


def test_validate_year_mismatch():
    """pydantic 已拦截年份错误，validate_config 不会收到此情况"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain(name="test", keywords=["laser"], arxiv_categories=[])},
        filters=FilterConfig(year_from=2020, year_to=2024),
    )
    warnings = validate_config(config)
    assert not any("year_from" in w and "year_to" in w for w in warnings)


def test_validate_valid_config():
    """合法配置不应有警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={
            "test": ResearchDomain(
                name="test",
                keywords=["laser", "fmcw", "ranging"],
                arxiv_categories=["physics.optics"],
            ),
        },
        filters=FilterConfig(min_citations=3, year_from=2020, year_to=2024),
    )
    warnings = validate_config(config)
    assert len(warnings) == 0


# ========== get_domains ==========

def test_get_domains_all():
    """get_domains(None) 返回所有领域"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain(name="A", keywords=["kw1"], arxiv_categories=[], priority=3),
            "B": ResearchDomain(name="B", keywords=["kw2"], arxiv_categories=[], priority=5),
        },
    )
    domains = get_domains(config)
    assert len(domains) == 2


def test_get_domains_priority_order():
    """get_domains 按 priority 降序"""
    config = AppConfig(
        research_domains={
            "Low": ResearchDomain(name="Low", keywords=["kw"], arxiv_categories=[], priority=1),
            "High": ResearchDomain(name="High", keywords=["kw"], arxiv_categories=[], priority=10),
        },
    )
    domains = get_domains(config)
    assert domains[0].name == "High"
    assert domains[1].name == "Low"


def test_get_domains_all_keyword():
    """get_domains(all) 返回所有"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain(name="A", keywords=["kw"], arxiv_categories=[], priority=3),
        },
    )
    assert len(get_domains(config, "all")) == 1


def test_get_domains_specific():
    """指定领域名返回单个"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain(name="A", keywords=["kw"], arxiv_categories=[]),
            "B": ResearchDomain(name="B", keywords=["kw"], arxiv_categories=[]),
        },
    )
    domains = get_domains(config, "A")
    assert len(domains) == 1
    assert domains[0].name == "A"


def test_get_domains_multiple():
    """逗号分隔返回多个"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain(name="A", keywords=["kw"], arxiv_categories=[]),
            "B": ResearchDomain(name="B", keywords=["kw"], arxiv_categories=[]),
            "C": ResearchDomain(name="C", keywords=["kw"], arxiv_categories=[]),
        },
    )
    domains = get_domains(config, "A, C")
    assert len(domains) == 2
    assert names_equal(domains, ["A", "C"])


def test_get_domains_invalid():
    """不存在的领域应报错"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain(name="A", keywords=["kw"], arxiv_categories=[]),
        },
    )
    with pytest.raises(ValueError):
        get_domains(config, "NonExistent")


def test_get_domains_no_domains():
    """无领域时应报错"""
    config = AppConfig()
    with pytest.raises(ValueError):
        get_domains(config)


# ========== 辅助 ==========

def names_equal(domains, expected_names):
    """检查领域名称列表是否一致"""
    return [d.name for d in domains] == expected_names
