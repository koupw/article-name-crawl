"""爬虫基类"""

from abc import ABC, abstractmethod
from typing import Generator, Optional
import logging
import requests

from utils.retry import retryable_request
from models.paper import Paper

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """爬虫基类，定义统一接口"""

    def __init__(self, excluded_keywords: list[str] = None):
        self.excluded_keywords = excluded_keywords or []
        self.logger = logging.getLogger(self.__class__.__name__)
        self._session: Optional[requests.Session] = None

    @property
    def session(self) -> requests.Session:
        """获取可复用的 HTTP session（延迟初始化）"""
        if self._session is None:
            self._session = requests.Session()
        return self._session

    @session.setter
    def session(self, value: requests.Session) -> None:
        """允许子类直接赋值覆盖 session"""
        self._session = value

    def request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs,
    ) -> requests.Response:
        """带指数退避重试的 HTTP 请求

        Args:
            method: HTTP 方法
            url: 请求 URL
            max_retries: 最大重试次数
            base_delay: 初始延迟（秒）
            **kwargs: 传递给 session.request 的参数

        Returns:
            requests.Response 对象
        """
        return retryable_request(
            method=method,
            url=url,
            session=self.session,
            max_retries=max_retries,
            base_delay=base_delay,
            **kwargs,
        )

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
