"""配置文件加载器（Pydantic v2）"""

import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field, field_validator

# 自动加载项目根目录的 .env 文件（如果存在）
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)


class ResearchDomain(BaseModel):
    """研究领域配置"""

    name: str
    keywords: list[str] = Field(default_factory=list)
    arxiv_categories: list[str] = Field(default_factory=list)
    priority: int = 5

    @field_validator("priority")
    @classmethod
    def _check_priority(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError(f"priority 应为 1-10，当前为 {v}")
        return v


class FilterConfig(BaseModel):
    """论文筛选配置"""

    min_citations: int = 0
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    require_doi: bool = False
    open_access_only: bool = False

    @field_validator("min_citations")
    @classmethod
    def _check_min_citations(cls, v: int) -> int:
        if v < 0:
            raise ValueError("min_citations 不能为负数")
        return v

    @field_validator("year_to")
    @classmethod
    def _check_year_range(cls, v: Optional[int], info) -> Optional[int]:
        year_from = info.data.get("year_from")
        if year_from is not None and v is not None and year_from > v:
            raise ValueError(f"year_from ({year_from}) > year_to ({v})")
        return v


class AppConfig(BaseModel):
    """应用配置"""

    language: str = "zh"
    vault_path: str = ""
    papers_dir: str = "papers"
    research_domains: dict[str, ResearchDomain] = Field(default_factory=dict)
    excluded_keywords: list[str] = Field(default_factory=list)
    semantic_scholar_api_key: str = ""
    ieee_api_key: str = ""
    openalex_email: str = ""
    core_api_key: str = ""
    translate_backend: str = "google"
    baidu_translate_app_id: str = ""
    baidu_translate_app_key: str = ""
    filters: FilterConfig = Field(default_factory=FilterConfig)

    # LLM 深度分析配置
    llm_api_key: str = ""
    llm_api_base: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    llm_timeout: int = 120
    analysis_dir: str = "papers/analysis"

    @property
    def output_path(self) -> Path:
        """输出目录的完整路径"""
        return Path(self.vault_path) / self.papers_dir

    @field_validator("translate_backend")
    @classmethod
    def _check_backend(cls, v: str) -> str:
        if v not in ("google", "baidu"):
            raise ValueError(f"未知翻译引擎: {v}（可选: google, baidu）")
        return v


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
        papers_dir=data.get("papers_dir", "papers"),
        research_domains=domains,
        excluded_keywords=data.get("excluded_keywords", []),
        semantic_scholar_api_key=data.get("semantic_scholar_api_key", "")
        or os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        ieee_api_key=data.get("ieee_api_key", "")
        or os.environ.get("IEEE_API_KEY", ""),
        openalex_email=data.get("openalex_email", "")
        or os.environ.get("OPENALEX_EMAIL", ""),
        core_api_key=data.get("core_api_key", "")
        or os.environ.get("CORE_API_KEY", ""),
        translate_backend=data.get("translate_backend", "google"),
        baidu_translate_app_id=data.get("baidu_translate_app_id", "")
        or os.environ.get("BAIDU_TRANSLATE_APP_ID", ""),
        baidu_translate_app_key=data.get("baidu_translate_app_key", "")
        or os.environ.get("BAIDU_TRANSLATE_APP_KEY", ""),
        filters=filters,
        # LLM 分析配置
        llm_api_key=data.get("llm_api_key", "")
        or os.environ.get("LLM_API_KEY", ""),
        llm_api_base=data.get("llm_api_base", "https://api.deepseek.com/v1"),
        llm_model=data.get("llm_model", "deepseek-chat"),
        llm_timeout=data.get("llm_timeout", 120),
        analysis_dir=data.get("analysis_dir", "papers/analysis"),
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

    if config.translate_backend == "baidu" and not (
        config.baidu_translate_app_id and config.baidu_translate_app_key
    ):
        issues.append(
            "translate_backend 为 baidu，但未配置 baidu_translate_app_id / "
            "baidu_translate_app_key（也可通过环境变量 BAIDU_TRANSLATE_APP_ID / "
            "BAIDU_TRANSLATE_APP_KEY 提供）"
        )

    # LLM 分析配置验证（仅在用户打算使用分析功能时提示）
    if not config.llm_api_key:
        issues.append(
            "未配置 llm_api_key（也可用环境变量 LLM_API_KEY）。"
            "论文深度分析功能将不可用。"
        )

    return issues


DEFAULT_CONFIG = """# 研究兴趣与论文爬取配置
language: zh
vault_path: .
papers_dir: papers
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

# API 配置（可选，也可用同名大写环境变量替代）
# 默认数据源（无需 Key）：arxiv + openalex + crossref
# 如需更多数据源，在命令行用 --sources 指定
semantic_scholar_api_key: ''
ieee_api_key: ''
openalex_email: ''
core_api_key: ''                 # CORE API Key（免费注册 https://core.ac.uk/services/apis/，或用环境变量 CORE_API_KEY）

# 翻译引擎配置
translate_backend: google        # 翻译引擎: google | baidu
baidu_translate_app_id: ''       # 百度翻译 APP ID（使用 baidu 时必填，或用环境变量 BAIDU_TRANSLATE_APP_ID）
baidu_translate_app_key: ''      # 百度翻译 Secret Key（或用环境变量 BAIDU_TRANSLATE_APP_KEY）

# LLM 深度分析配置（可选，论文解读功能需要）
# API Key 优先级：命令行 --api-key > 环境变量 LLM_API_KEY > 配置文件 llm_api_key
#
# 支持任何 OpenAI 兼容格式端点，例如：
#   - DeepSeek:  https://api.deepseek.com/v1           (模型: deepseek-chat)
#   - OpenAI:    https://api.openai.com/v1              (模型: gpt-4o)
#   - OpenCode:  https://opencode.ai/zen/go/v1/         (模型: 按该网关实际部署填写)
#   - 本地/Ollama: http://localhost:11434/v1             (模型: llama3 等)
llm_api_key: ''                      # 对应网关的 API Key
llm_api_base: 'https://api.deepseek.com/v1'   # API Base URL（OpenAI 兼容格式）
llm_model: 'deepseek-chat'           # 模型名称
llm_timeout: 120                     # LLM 请求超时秒数
analysis_dir: 'papers/analysis'      # 深度分析报告存放目录

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
