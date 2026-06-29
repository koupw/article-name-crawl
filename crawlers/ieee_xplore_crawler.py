"""IEEE Xplore 论文爬虫

IEEE Xplore 是工程技术领域的权威数据源。
需要 API Key: https://developer.ieee.org/
API 文档: https://developer.ieee.org/docs-read
"""

import requests
from typing import Generator, Optional
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
        self.session = requests.Session()

    def get_name(self) -> str:
        return "ieee_xplore"

    def _build_batch_query(self, batch: list[str]) -> str:
        """构建一批关键词的查询字符串

        Args:
            batch: 一批关键词

        Returns:
            OR 连接的查询字符串
        """
        query_parts = []
        for kw in batch:
            if " " in kw:
                query_parts.append(f'"{kw}"')
            else:
                query_parts.append(kw)
        return " OR ".join(query_parts)

    def _search_single(
        self,
        query: str,
        keywords: list[str],
        domain: str,
        max_results: int,
        seen_dois: set[str],
    ) -> list[Paper]:
        """单批关键词搜索

        Args:
            query: 查询字符串
            keywords: 本批关键词列表
            domain: 研究领域
            max_results: 本批最大结果数
            seen_dois: 已见 DOI 集合

        Returns:
            论文列表
        """
        start_record = 1
        count = 0
        papers = []

        while count < max_results:
            params = {
                "querytext": query,
                "apikey": self.api_key,
                "max_records": min(200, max_results - count),
                "start_record": start_record,
            }

            try:
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as e:
                self.logger.error("IEEE Xplore 查询 '%s' 失败: %s", query[:40], e)
                break

            articles = data.get("articles", [])
            if not articles:
                break

            for article in articles:
                if count >= max_results:
                    break
                paper = self._parse_article(article, keywords, domain)
                if not paper:
                    continue

                if paper.doi:
                    if paper.doi in seen_dois:
                        continue
                    seen_dois.add(paper.doi)

                count += 1
                papers.append(paper)

            total_records = data.get("total_records", 0)
            if start_record + len(articles) >= total_records:
                break

            start_record += len(articles)
            time.sleep(1)

        return papers

    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """搜索 IEEE Xplore 论文（多轮关键词搜索）

        Args:
            keywords: 关键词列表
            categories: 分类列表（未使用）
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        # 将关键词分批
        batch_size = 6
        batches = [keywords[i:i + batch_size] for i in range(0, len(keywords), batch_size)]
        per_batch = max(max_results // len(batches), 8)

        self.logger.info(
            "IEEE Xplore 多轮搜索: %d 批, 每批最多 %d 篇",
            len(batches), per_batch,
        )

        seen_dois: set[str] = set()
        total = 0

        for batch_idx, batch in enumerate(batches):
            if total >= max_results:
                break

            query = self._build_batch_query(batch)
            remaining = max_results - total
            batch_limit = min(per_batch, remaining)

            self.logger.debug(
                "第 %d/%d 批: %s", batch_idx + 1, len(batches), query[:80],
            )

            papers = self._search_single(
                query=query,
                keywords=batch,
                domain=domain,
                max_results=batch_limit,
                seen_dois=seen_dois,
            )

            for paper in papers:
                total += 1
                self.logger.debug("[%d/%d] %s", total, max_results, paper.title[:70])
                yield paper

        self.logger.info("IEEE Xplore 共返回 %d 篇论文（%d 批搜索）", total, len(batches))

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
