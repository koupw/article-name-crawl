"""爬虫基类"""

from abc import ABC, abstractmethod
from typing import Generator
import logging

from models.paper import Paper

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """爬虫基类，定义统一接口"""

    def __init__(self, excluded_keywords: list[str] = None):
        self.excluded_keywords = excluded_keywords or []
        self.logger = logging.getLogger(self.__class__.__name__)

    def should_exclude(self, title: str) -> bool:
        """检查论文标题是否应被排除

        Args:
            title: 论文标题

        Returns:
            True 表示应排除
        """
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in self.excluded_keywords)

    def match_keywords(self, text: str, keywords: list[str]) -> list[str]:
        """匹配文本中的关键词

        Args:
            text: 待匹配文本
            keywords: 关键词列表

        Returns:
            命中的关键词列表
        """
        text_lower = text.lower()
        return [kw for kw in keywords if kw.lower() in text_lower]

    @abstractmethod
    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """搜索论文

        Args:
            keywords: 关键词列表
            categories: 分类列表（如 arXiv 分类）
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """返回数据源名称"""
        pass
