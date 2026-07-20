"""IEEE Xplore 论文爬虫

IEEE Xplore 是工程技术领域的权威数据源。
需要 API Key: https://developer.ieee.org/
API 文档: https://developer.ieee.org/docs-read
"""

import requests
from typing import Optional
from datetime import datetime
import time

from crawlers.base import BaseCrawler
from models.paper import Paper


class IEEEXploreCrawler(BaseCrawler):
    """IEEE Xplore API 爬虫"""

    BASE_URL = "http://ieeexploreapi.ieee.org/api/v1/search/articles"

    def __init__(
        self,
        api_key: str,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        if not api_key:
            raise ValueError("IEEE Xplore 需要 API Key，请在配置文件中设置 ieee_api_key")
        self.api_key = api_key

    def get_name(self) -> str:
        return "ieee_xplore"

    def build_query(self, batch: list[str], categories: list[str]) -> str:
        """构建一批关键词的查询字符串（OR 连接，短语加引号）"""
        query_parts = []
        for kw in batch:
            if " " in kw:
                query_parts.append(f'"{kw}"')
            else:
                query_parts.append(kw)
        return " OR ".join(query_parts)

    def fetch_batch(
        self,
        query: str,
        keywords: list[str],
        categories: list[str],
        domain: str,
        limit: int,
    ) -> list[Paper]:
        """单批关键词搜索（分页，带重试）

        Args:
            query: 查询字符串
            keywords: 本批关键词列表
            categories: 分类列表（未使用）
            domain: 研究领域
            limit: 本批最大结果数

        Returns:
            论文列表
        """
        start_record = 1
        papers = []

        while len(papers) < limit:
            params = {
                "querytext": query,
                "apikey": self.api_key,
                "max_records": min(200, limit - len(papers)),
                "start_record": start_record,
            }

            try:
                response = self.request_with_retry(
                    "GET",
                    self.BASE_URL,
                    params=params,
                    timeout=30,
                )
                data = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                self.logger.error("IEEE Xplore 查询 '%s' 失败: %s", query[:40], e)
                break

            articles = data.get("articles", [])
            if not articles:
                break

            for article in articles:
                if len(papers) >= limit:
                    break
                paper = self._parse_article(article, keywords, domain)
                if paper:
                    papers.append(paper)

            total_records = data.get("total_records", 0)
            if start_record + len(articles) >= total_records:
                break

            start_record += len(articles)
            time.sleep(1)

        return papers

    def _parse_article(self, article: dict, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 IEEE Xplore 文章为 Paper 对象

        Args:
            article: IEEE API 返回的文章数据
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            title = article.get("title", "")
            if not title:
                return None

            # 检查是否应排除
            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 提取作者
            authors = []
            for author in article.get("authors", []):
                name = author.get("preferred_name") or author.get("full_name")
                if name:
                    authors.append(name)

            # 提取摘要
            abstract = article.get("abstract", "")

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # 提取 URL
            url = article.get("html_url") or article.get("pdf_url", "")

            # 提取 PDF URL
            pdf_url = article.get("pdf_url")

            # 提取 DOI
            doi = article.get("doi")

            # 提取日期
            published_date = None
            pub_date = article.get("publication_date")
            if pub_date:
                try:
                    published_date = datetime.strptime(pub_date, "%m/%Y")
                except ValueError:
                    pass
            if not published_date:
                pub_year = article.get("publication_year")
                if pub_year:
                    published_date = datetime(int(pub_year), 1, 1)

            # 提取分类
            categories = []
            content_type = article.get("content_type")
            if content_type:
                categories.append(content_type)

            return Paper(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip(),
                url=url,
                pdf_url=pdf_url,
                source=self.get_name(),
                domain=domain,
                matched_keywords=matched,
                published_date=published_date,
                arxiv_id=None,
                doi=doi,
                categories=categories,
            )
        except Exception as e:
            self.logger.warning(f"解析论文失败: {e}")
            return None
