"""arXiv 论文爬虫"""

import arxiv
from typing import Optional
from datetime import timezone

from crawlers.base import BaseCrawler
from models.paper import Paper


class ArxivCrawler(BaseCrawler):
    """arXiv API 爬虫"""

    def __init__(self, excluded_keywords: list[str] = None):
        super().__init__(excluded_keywords)
        self.client = arxiv.Client(
            page_size=50,
            delay_seconds=5.0,  # 增加延迟避免 429 错误
            num_retries=2,
        )

    def get_name(self) -> str:
        return "arxiv"

    def build_query(self, batch: list[str], categories: list[str]) -> str:
        """构建一批关键词的 arXiv 搜索查询

        Args:
            batch: 一批关键词
            categories: arXiv 分类列表

        Returns:
            查询字符串
        """
        # 关键词查询（搜索标题和摘要），对含空格的关键词加引号
        keyword_parts = []
        for kw in batch:
            if " " in kw:
                keyword_parts.append(f'ti:"{kw}"')
                keyword_parts.append(f'abs:"{kw}"')
            else:
                keyword_parts.append(f"ti:{kw}")
                keyword_parts.append(f"abs:{kw}")

        keyword_query = " OR ".join(keyword_parts)

        # 分类查询
        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            return f"({cat_query}) AND ({keyword_query})"

        return keyword_query

    def _parse_result(self, result, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 arXiv 结果为 Paper 对象

        Args:
            result: arxiv 库返回的结果
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            # 检查是否应排除
            if self.should_exclude(result.title):
                self.logger.debug(f"排除论文: {result.title}")
                return None

            # 匹配关键词
            text = f"{result.title} {result.summary}"
            matched = self.match_keywords(text, keywords)

            # 提取分类
            categories_list = result.categories if result.categories else []

            # 转换日期
            published = result.published.replace(tzinfo=timezone.utc) if result.published else None

            return Paper(
                title=result.title.strip(),
                authors=[str(author) for author in result.authors],
                abstract=result.summary.strip(),
                url=result.entry_id,
                pdf_url=result.pdf_url,
                source=self.get_name(),
                domain=domain,
                matched_keywords=matched,
                published_date=published,
                arxiv_id=result.entry_id.split("/abs/")[-1] if "/abs/" in result.entry_id else None,
                doi=result.doi,
                categories=categories_list,
            )
        except Exception as e:
            self.logger.warning(f"解析论文失败: {e}")
            return None

    def fetch_batch(
        self,
        query: str,
        keywords: list[str],
        categories: list[str],
        domain: str,
        limit: int,
    ) -> list[Paper]:
        """单批关键词搜索

        Args:
            query: arXiv 查询字符串
            keywords: 本批关键词列表
            categories: arXiv 分类列表
            domain: 研究领域
            limit: 本批最大结果数

        Returns:
            论文列表
        """
        search = arxiv.Search(
            query=query,
            max_results=limit,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        papers = []
        try:
            for result in self.client.results(search):
                paper = self._parse_result(result, keywords, domain)
                if paper:
                    papers.append(paper)
        except Exception as e:
            self.logger.error("arXiv 查询失败: %s", e)

        return papers
