"""爬虫基类"""

from abc import ABC, abstractmethod
from typing import Generator, Optional
import logging
import requests

from utils.retry import retryable_request
from utils.dedup import normalize_title
from models.paper import Paper

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """爬虫基类，定义统一接口

    子类实现 fetch_batch() 即可获得多轮关键词分批搜索能力（模板方法）；
    搜索流程差异较大的子类（如 Google Scholar）可直接覆盖 search()。
    """

    # 多轮搜索：每批关键词数量、每批最小结果数
    KEYWORD_BATCH_SIZE = 6
    MIN_PER_BATCH = 8

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

    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """多轮关键词分批搜索（模板方法）

        将全部关键词分批，逐批调用 fetch_batch()，批间按
        DOI / arXiv ID / 标准化标题自动去重。

        Args:
            keywords: 关键词列表
            categories: 分类列表（如 arXiv 分类）
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        if not keywords:
            self.logger.warning("%s: 关键词为空，跳过搜索", self.get_name())
            return

        batches = [
            keywords[i:i + self.KEYWORD_BATCH_SIZE]
            for i in range(0, len(keywords), self.KEYWORD_BATCH_SIZE)
        ]
        per_batch = max(max_results // len(batches), self.MIN_PER_BATCH)

        self.logger.info(
            "%s 多轮搜索: %d 批, 每批最多 %d 篇",
            self.get_name(), len(batches), per_batch,
        )

        seen: set[str] = set()
        total = 0

        for batch_idx, batch in enumerate(batches):
            if total >= max_results:
                break

            query = self.build_query(batch, categories)
            remaining = max_results - total
            batch_limit = min(per_batch, remaining)

            self.logger.debug(
                "第 %d/%d 批: %s", batch_idx + 1, len(batches), query[:80],
            )

            papers = self.fetch_batch(
                query=query,
                keywords=batch,
                categories=categories,
                domain=domain,
                limit=batch_limit,
            )

            for paper in papers:
                if total >= max_results:
                    break
                key = self._paper_key(paper)
                if key in seen:
                    continue
                seen.add(key)
                total += 1
                self.logger.debug("[%d/%d] %s", total, max_results, paper.title[:70])
                yield paper

        self.logger.info(
            "%s 共返回 %d 篇论文（%d 批搜索）",
            self.get_name(), total, len(batches),
        )

    def build_query(self, batch: list[str], categories: list[str]) -> str:
        """构建一批关键词的查询字符串（子类可覆盖）

        Args:
            batch: 一批关键词
            categories: 分类列表

        Returns:
            查询字符串
        """
        return " ".join(batch)

    def fetch_batch(
        self,
        query: str,
        keywords: list[str],
        categories: list[str],
        domain: str,
        limit: int,
    ) -> list[Paper]:
        """执行单批搜索（子类必须实现此方法，或覆盖 search()）

        Args:
            query: 查询字符串
            keywords: 本批关键词列表（用于解析匹配）
            categories: 分类列表
            domain: 研究领域
            limit: 本批最大结果数

        Returns:
            论文列表
        """
        raise NotImplementedError("子类必须实现 fetch_batch() 或覆盖 search()")

    @staticmethod
    def _paper_key(paper: Paper) -> str:
        """跨批去重键：DOI > arXiv ID > 标准化标题"""
        if paper.doi:
            return f"doi:{paper.doi.lower().strip()}"
        if paper.arxiv_id:
            return f"arxiv:{paper.arxiv_id.strip()}"
        return f"title:{normalize_title(paper.title)}"

    @abstractmethod
    def get_name(self) -> str:
        """返回数据源名称"""
        pass
