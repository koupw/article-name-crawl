"""论文数据模型"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Paper:
    """统一的论文数据结构"""

    title: str
    authors: list[str]
    abstract: str
    url: str
    source: str  # arxiv, semantic_scholar, google_scholar, openalex, ieee_xplore
    domain: str  # 所属研究领域
    matched_keywords: list[str] = field(default_factory=list)
    pdf_url: Optional[str] = None
    published_date: Optional[datetime] = None
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    categories: list[str] = field(default_factory=list)
    citations: int = 0  # 引用数
    is_open_access: bool = False  # 是否开放获取
    title_zh: Optional[str] = None  # 中文标题

    @property
    def year(self) -> Optional[int]:
        """获取发表年份"""
        return self.published_date.year if self.published_date else None

    @property
    def authors_str(self) -> str:
        """作者列表格式化为字符串"""
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 3:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def date_str(self) -> str:
        """日期格式化为字符串"""
        if not self.published_date:
            return "Unknown"
        return self.published_date.strftime("%Y-%m")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "title_zh": self.title_zh,
            "authors": self.authors,
            "abstract": self.abstract,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "source": self.source,
            "domain": self.domain,
            "matched_keywords": self.matched_keywords,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "arxiv_id": self.arxiv_id,
            "doi": self.doi,
            "categories": self.categories,
            "citations": self.citations,
            "is_open_access": self.is_open_access,
        }
