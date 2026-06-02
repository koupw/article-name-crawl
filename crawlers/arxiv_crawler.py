"""arXiv 论文爬虫"""

import arxiv
from typing import Generator
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

    def _build_query(self, keywords: list[str], categories: list[str]) -> str:
        """构建 arXiv 搜索查询

        Args:
            keywords: 关键词列表
            categories: arXiv 分类列表

        Returns:
            查询字符串
        """
        # 关键词查询（搜索标题和摘要）
        # 限制关键词数量避免查询过长
        keyword_parts = []
        for kw in keywords[:10]:
            # 对含空格的关键词加引号
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

    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """搜索 arXiv 论文

        Args:
            keywords: 关键词列表
            categories: arXiv 分类列表
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        query = self._build_query(keywords, categories)
        self.logger.info(f"arXiv 查询: {query}")

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        count = 0
        for result in self.client.results(search):
            # 检查是否应排除
            if self.should_exclude(result.title):
                self.logger.debug(f"排除论文: {result.title}")
                continue

            # 匹配关键词
            text = f"{result.title} {result.summary}"
            matched = self.match_keywords(text, keywords)

            # 提取分类
            categories_list = result.categories if result.categories else []

            # 转换日期
            published = result.published.replace(tzinfo=timezone.utc) if result.published else None

            paper = Paper(
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

            count += 1
            self.logger.debug(f"[{count}] {paper.title}")
            yield paper
