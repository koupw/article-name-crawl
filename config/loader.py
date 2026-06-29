"""配置文件加载器"""

from pathlib import Path
from typing import Optional
import yaml
from dataclasses import dataclass, field


@dataclass
class ResearchDomain:
    """研究领域配置"""

    name: str
    keywords: list[str]
    arxiv_categories: list[str]
    priority: int = 5


@dataclass
class FilterConfig:
    """论文筛选配置"""

    min_citations: int = 0  # 最低引用数
    year_from: Optional[int] = None  # 起始年份
    year_to: Optional[int] = None  # 结束年份
    require_doi: bool = False  # 是否必须有 DOI
    open_access_only: bool = False  # 是否只要开放获取


@dataclass
class AppConfig:
    """应用配置"""

    language: str = "zh"
    vault_path: str = ""
    papers_dir: str = "20_Research/Papers"
    research_domains: dict[str, ResearchDomain] = field(default_factory=dict)
    excluded_keywords: list[str] = field(default_factory=list)
    semantic_scholar_api_key: str = ""
    ieee_api_key: str = ""
    openalex_email: str = ""
    filters: FilterConfig = field(default_factory=FilterConfig)

    @property
    def output_path(self) -> Path:
        """输出目录的完整路径"""
        return Path(self.vault_path) / self.papers_dir


def load_config(config_path: str = "research_interests.yaml") -> AppConfig:
    """加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        AppConfig 对象

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("配置文件格式错误: 应为字典结构")

    # 解析研究领域
    domains = {}
    for domain_name, domain_data in data.get("research_domains", {}).items():
        if not isinstance(domain_data, dict):
            continue
        domains[domain_name] = ResearchDomain(
            name=domain_name,
            keywords=domain_data.get("keywords", []),
            arxiv_categories=domain_data.get("arxiv_categories", []),
            priority=domain_data.get("priority", 5),
        )

    # 解析筛选配置
    filter_data = data.get("filters", {})
    filters = FilterConfig(
        min_citations=filter_data.get("min_citations", 0),
        year_from=filter_data.get("year_from"),
        year_to=filter_data.get("year_to"),
        require_doi=filter_data.get("require_doi", False),
        open_access_only=filter_data.get("open_access_only", False),
    )

    return AppConfig(
        language=data.get("language", "zh"),
        vault_path=data.get("vault_path", ""),
        papers_dir=data.get("papers_dir", "20_Research/Papers"),
        research_domains=domains,
        excluded_keywords=data.get("excluded_keywords", []),
        semantic_scholar_api_key=data.get("semantic_scholar_api_key", ""),
        ieee_api_key=data.get("ieee_api_key", ""),
        openalex_email=data.get("openalex_email", ""),
        filters=filters,
    )


def validate_config(config: AppConfig) -> list[str]:
    """验证配置，返回警告/错误列表

    Args:
        config: 应用配置

    Returns:
        验证问题列表（空列表表示无问题）
    """
    issues = []

    if not config.vault_path:
        issues.append("vault_path 未设置，输出将使用命令行 --output 指定")

    if not config.research_domains:
        issues.append("research_domains 为空，至少需要一个研究领域")

    for name, domain in config.research_domains.items():
        if not domain.keywords:
            issues.append(f"领域 '{name}': keywords 为空")
        elif len(domain.keywords) < 3:
            issues.append(f"领域 '{name}': 关键词少于 3 个，搜索结果可能较少")
        if domain.priority < 1 or domain.priority > 10:
            issues.append(f"领域 '{name}': priority 应为 1-10，当前为 {domain.priority}")

    f = config.filters
    if f.min_citations < 0:
        issues.append("filters.min_citations 不能为负数")
    if f.year_from is not None and f.year_to is not None and f.year_from > f.year_to:
        issues.append(f"filters.year_from ({f.year_from}) > year_to ({f.year_to})")

    return issues


DEFAULT_CONFIG = """# 研究兴趣与论文爬取配置
language: zh
vault_path: ./papers
papers_dir: ''
research_domains:
  Example Domain:
    keywords:
      - keyword one
      - keyword two
      - keyword three
    arxiv_categories:
      - physics.optics
    priority: 5

excluded_keywords:
  - workshop

# API 配置（可选）
semantic_scholar_api_key: ''
ieee_api_key: ''
openalex_email: ''

# 质量筛选配置
filters:
  min_citations: 0          # 最低引用数（0 表示不限制）
  year_from: null           # 起始年份（null 表示不限制）
  year_to: null             # 结束年份（null 表示不限制）
  require_doi: false        # 是否必须有 DOI
  open_access_only: false   # 是否只要开放获取的论文
"""


def init_config(config_path: str) -> None:
    """生成默认配置文件

    Args:
        config_path: 输出路径
    """
    path = Path(config_path)
    if path.exists():
        print(f"配置文件已存在: {config_path}")
        return

    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
    print(f"默认配置文件已生成: {config_path}")
    print("请编辑该文件，添加你的研究领域和关键词后重新运行")


def get_domain(config: AppConfig, domain_name: Optional[str] = None) -> ResearchDomain:
    """获取指定研究领域配置

    Args:
        config: 应用配置
        domain_name: 领域名称，为 None 时返回第一个领域

    Returns:
        ResearchDomain 对象

    Raises:
        ValueError: 指定的领域不存在
    """
    if not config.research_domains:
        raise ValueError("配置文件中未定义研究领域")

    if domain_name is None:
        # 返回优先级最高的领域
        return max(config.research_domains.values(), key=lambda d: d.priority)

    if domain_name not in config.research_domains:
        available = ", ".join(config.research_domains.keys())
        raise ValueError(f"研究领域 '{domain_name}' 不存在，可用领域: {available}")

    return config.research_domains[domain_name]


def get_domains(config: AppConfig, domain_arg: Optional[str] = None) -> list[ResearchDomain]:
    """获取一个或多个研究领域配置

    Args:
        config: 应用配置
        domain_arg: 领域名称参数，支持:
            - None: 返回按 priority 排序的所有领域
            - "all": 同上，全部领域
            - "Name1": 单个指定领域
            - "Name1,Name2": 逗号分隔的多个领域

    Returns:
        研究领域列表（按 priority 降序）

    Raises:
        ValueError: 指定的领域不存在
    """
    if not config.research_domains:
        raise ValueError("配置文件中未定义研究领域")

    if domain_arg is None or domain_arg.lower() == "all":
        return sorted(
            config.research_domains.values(),
            key=lambda d: d.priority,
            reverse=True,
        )

    names = [n.strip() for n in domain_arg.split(",")]
    domains = []
    for name in names:
        if name not in config.research_domains:
            available = ", ".join(config.research_domains.keys())
            raise ValueError(f"研究领域 '{name}' 不存在，可用领域: {available}")
        domains.append(config.research_domains[name])
    return domains
