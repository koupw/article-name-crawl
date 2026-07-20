"""CORE 论文爬虫

CORE (core.ac.uk) 是英国开放大学运营的开放获取全文聚合引擎，
覆盖 3 亿+ 学术论文。官方 API，免费 tier 每月 10,000 tokens。
API 文档: https://api.core.ac.uk/docs/v3
注册获取 API Key: https://core.ac.uk/services/apis/
"""

import requests
from typing import Optional
from datetime import datetime
import time

from crawlers.base import BaseCrawler
from models.paper import Paper


class CoreCrawler(BaseCrawler):
    """CORE API v3 爬虫"""

    BASE_URL = "https://api.core.ac.uk/v3/search/works"

    def __init__(
        self,
        api_key: str,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        if not api_key:
            raise ValueError("CORE 需要 API Key，请在 https://core.ac.uk/services/apis/ 免费注册")
        self.api_key = api_key
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def get_name(self) -> str:
        return "core"

    def _parse_result(self, result: dict, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 CORE work 为 Paper 对象

        Args:
            result: API 返回的单个 work
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            title = result.get("title", "")
            if not title:
                return None

            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 作者（可能是字符串列表或字典列表）
            authors = []
            raw_authors = result.get("authors", [])
            for a in raw_authors:
                if isinstance(a, str):
                    authors.append(a)
                elif isinstance(a, dict):
                    name = a.get("name") or f"{a.get('givenName', '')} {a.get('familyName', '')}".strip()
                    if name:
                        authors.append(name)

            # 摘要
            abstract = result.get("abstract", "") or ""

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # DOI
            doi = result.get("doi")
            if isinstance(doi, list) and doi:
                doi = doi[0]

            # URL：优先 downloadUrl（PDF），其次 links，其次 DOI
            pdf_url = result.get("downloadUrl")
            links = result.get("links", [])
            url = ""
            if links and isinstance(links, list):
                url = links[0]
            if not url and doi:
                url = f"https://doi.org/{doi}"

            # 引用数
            citations = result.get("citationCount") or result.get("cited_by_count") or 0

            # 日期
            published_date = None
            pub_date = result.get("publishedDate") or result.get("datePublished")
            if pub_date:
                try:
                    # 尝试 ISO 格式
                    published_date = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        published_date = datetime.strptime(pub_date[:10], "%Y-%m-%d")
                    except ValueError:
                        pass
            if not published_date:
                pub_year = result.get("year")
                if pub_year:
                    try:
                        published_date = datetime(int(pub_year), 1, 1)
                    except (ValueError, TypeError):
                        pass

            # 分类
            categories = []
            doc_type = result.get("documentType") or result.get("type")
            if doc_type:
                categories.append(doc_type)
            language = result.get("language")
            if language:
                categories.append(f"lang:{language}")

            # 开放获取状态
            is_open_access = bool(pdf_url) or result.get("isOpenAccess", False)

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
                citations=citations,
                is_open_access=is_open_access,
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
        per_page = min(limit, 50)
        results = []

        while len(results) < limit:
            params = {
                "q": query,
                "limit": per_page,
                "offset": offset,
            }

            try:
                response = self.request_with_retry(
                    "GET",
                    self.BASE_URL,
                    params=params,
                    headers=self._headers,
                    timeout=30,
                )
                data = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                self.logger.error("CORE 查询 '%s' 失败: %s", query[:40], e)
                break

            items = data.get("results", [])
            if not items:
                break

            for item in items:
                if len(results) >= limit:
                    break
                paper = self._parse_result(item, keywords, domain)
                if paper:
                    results.append(paper)

            # 检查是否还有更多结果
            total_hits = data.get("totalHits", 0)
            if offset + len(items) >= total_hits:
                break

            offset += len(items)
            time.sleep(0.5)

        return results
