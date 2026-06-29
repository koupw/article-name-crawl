"""配置加载与验证测试"""

import pytest
from config.loader import load_config, validate_config, get_domains, AppConfig, \
    ResearchDomain, FilterConfig


def test_validate_empty_domains():
    """空领域配置应产生警告"""
    config = AppConfig(vault_path="/tmp")
    warnings = validate_config(config)
    assert any("research_domains 为空" in w for w in warnings)


def test_validate_no_vault_path():
    """无 vault_path 应产生警告"""
    config = AppConfig(research_domains={"test": ResearchDomain("test", ["kw"], [])})
    warnings = validate_config(config)
    assert any("vault_path" in w for w in warnings)


def test_validate_empty_keywords():
    """空关键词应产生警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain("test", [], [])},
    )
    warnings = validate_config(config)
    assert any("keywords 为空" in w for w in warnings)


def test_validate_negative_citations():
    """负数 min_citations 应产生警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain("test", ["laser"], [])},
        filters=FilterConfig(min_citations=-1),
    )
    warnings = validate_config(config)
    assert any("负数" in w for w in warnings)


def test_validate_year_mismatch():
    """year_from > year_to 应产生警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={"test": ResearchDomain("test", ["laser"], [])},
        filters=FilterConfig(year_from=2025, year_to=2020),
    )
    warnings = validate_config(config)
    assert any("year_from" in w and "year_to" in w for w in warnings)


def test_validate_valid_config():
    """合法配置不应有警告"""
    config = AppConfig(
        vault_path="/tmp",
        research_domains={
            "test": ResearchDomain("test", ["laser", "fmcw", "ranging"], ["physics.optics"]),
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
            "A": ResearchDomain("A", ["kw1"], [], priority=3),
            "B": ResearchDomain("B", ["kw2"], [], priority=5),
        }
    )
    domains = get_domains(config)
    assert len(domains) == 2


def test_get_domains_priority_order():
    """get_domains 按 priority 降序"""
    config = AppConfig(
        research_domains={
            "Low": ResearchDomain("Low", ["kw"], [], priority=1),
            "High": ResearchDomain("High", ["kw"], [], priority=10),
        }
    )
    domains = get_domains(config)
    assert domains[0].name == "High"
    assert domains[1].name == "Low"


def test_get_domains_all_keyword():
    """get_domains(all) 返回所有"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain("A", ["kw"], [], priority=3),
        }
    )
    assert len(get_domains(config, "all")) == 1


def test_get_domains_specific():
    """指定领域名返回单个"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain("A", ["kw"], []),
            "B": ResearchDomain("B", ["kw"], []),
        }
    )
    domains = get_domains(config, "A")
    assert len(domains) == 1
    assert domains[0].name == "A"


def test_get_domains_multiple():
    """逗号分隔返回多个"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain("A", ["kw"], []),
            "B": ResearchDomain("B", ["kw"], []),
            "C": ResearchDomain("C", ["kw"], []),
        }
    )
    domains = get_domains(config, "A, C")
    assert len(domains) == 2
    assert names_equal(domains, ["A", "C"])


def test_get_domains_invalid():
    """不存在的领域应报错"""
    config = AppConfig(
        research_domains={
            "A": ResearchDomain("A", ["kw"], []),
        }
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
