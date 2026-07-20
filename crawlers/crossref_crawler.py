"""Crossref 论文爬虫

Crossref 是 DOI 的注册管理机构，覆盖 1.3 亿+ 学术文献。
API 文档: https://api.crossref.org/
免费使用，建议添加 mailto 邮箱进入 Polite Pool。
"""

import requests
from typing import Optional
from datetime import datetime
import time

from crawlers.base import BaseCrawler
from models.paper import Paper


class CrossrefCrawler(BaseCrawler):
    """Crossref REST API 爬虫"""

    BASE_URL = "https://api.crossref.org/works"

    def __init__(
        self,
        email: Optional[str] = None,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        self.email = email

    def get_name(self) -> str:
        return "crossref"

    def _parse_item(self, item: dict, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 Crossref work 为 Paper 对象

        Args:
            item: API 返回的单个 work
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            # 标题（可能是列表，取第一个）
            title_raw = item.get("title", [])
            if isinstance(title_raw, list):
                title = title_raw[0] if title_raw else ""
            else:
                title = title_raw or ""
            if not title:
                return None

            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 作者
            authors = []
            for author in item.get("author", []):
                given = author.get("given", "")
                family = author.get("family", "")
                name = f"{given} {family}".strip()
                if name:
                    authors.append(name)

            # 摘要（Crossref 通常不提供，优先取 abstract）
            abstract = ""
            if "abstract" in item and item["abstract"]:
                abstract = item["abstract"]

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # DOI
            doi = item.get("DOI")

            # URL（使用 DOI  resolver）
            url = f"https://doi.org/{doi}" if doi else ""
            if not url:
                url = item.get("URL", "")

            # 引用数
            citations = item.get("is-referenced-by-count", 0) or 0

            # 日期：优先 published-print，其次 published-online，再次 created
            published_date = None
            for date_key in ("published-print", "published-online", "created"):
                date_info = item.get(date_key, {})
                date_parts = date_info.get("date-parts", [])
                if date_parts and isinstance(date_parts, list) and len(date_parts) > 0:
                    parts = date_parts[0]
                    if parts and isinstance(parts, list) and len(parts) >= 1:
                        year = int(parts[0])
                        month = int(parts[1]) if len(parts) > 1 else 1
                        day = int(parts[2]) if len(parts) > 2 else 1
                        try:
                            published_date = datetime(year, month, day)
                        except ValueError:
                            published_date = datetime(year, 1, 1)
                        break

            # 分类：使用 type（journal-article, conference-paper 等）
            categories = []
            work_type = item.get("type")
            if work_type:
                categories.append(work_type)
            container = item.get("container-title", [])
            if isinstance(container, list) and container:
                categories.append(container[0])

            return Paper(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip(),
                url=url,
                pdf_url=None,  # Crossref 不直接提供 PDF
                source=self.get_name(),
                domain=domain,
                matched_keywords=matched,
                published_date=published_date,
                arxiv_id=None,
                doi=doi,
                categories=categories,
                citations=citations,
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
        """单批关键词搜索（分页，带重试）

        Args:
            query: 搜索查询字符串
            keywords: 本批关键词列表（用于解析匹配）
            categories: 分类列表（未使用）
            domain: 研究领域
            limit: 本批最大结果数

        Returns:
            论文列表
        """
        offset = 0
        per_page = min(limit, 50)  # Crossref 建议 rows <= 50
        results = []

        while len(results) < limit:
            params = {
                "query": query,
                "rows": per_page,
                "offset": offset,
            }
            if self.email:
                params["mailto"] = self.email

            try:
                response = self.request_with_retry(
                    "GET",
                    self.BASE_URL,
                    params=params,
                    timeout=30,
                )
                data = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                self.logger.error("Crossref 查询 '%s' 失败: %s", query[:40], e)
                break

            message = data.get("message", {})
            items = message.get("items", [])
            if not items:
                break

            for item in items:
                if len(results) >= limit:
                    break
                paper = self._parse_item(item, keywords, domain)
                if paper:
                    results.append(paper)

            total_results = message.get("total-results", 0)
            if offset + len(items) >= total_results:
                break

            offset += len(items)
            time.sleep(0.5)  # Polite pool 建议间隔

        return results
