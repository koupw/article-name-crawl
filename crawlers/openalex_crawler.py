"""OpenAlex 论文爬虫

OpenAlex 是免费、开放的学术数据源，覆盖 2 亿+ 学术文献。
API 文档: https://docs.openalex.org/
"""

import requests
from typing import Optional
from datetime import datetime
import time

from crawlers.base import BaseCrawler
from models.paper import Paper


class OpenAlexCrawler(BaseCrawler):
    """OpenAlex API 爬虫"""

    BASE_URL = "https://api.openalex.org"

    def __init__(
        self,
        email: Optional[str] = None,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        self.email = email
        # 添加 polite pool 邮箱以获得更快响应
        if email:
            self.session.params = {"mailto": email}

    def get_name(self) -> str:
        return "openalex"

    def _parse_work(self, work: dict, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 OpenAlex work 为 Paper 对象

        Args:
            work: OpenAlex API 返回的 work 数据
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            title = work.get("title", "")
            if not title:
                return None

            # 检查是否应排除
            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 提取作者
            authors = []
            authorships = work.get("authorships", [])
            for authorship in authorships:
                author = authorship.get("author", {})
                name = author.get("display_name")
                if name:
                    authors.append(name)

            # 提取摘要（OpenAlex 不直接提供摘要，需要从 inverted_abstract 构建）
            abstract = ""
            inverted_abstract = work.get("abstract_inverted_index")
            if inverted_abstract:
                # 反转倒排索引构建摘要
                word_positions = []
                for word, positions in inverted_abstract.items():
                    for pos in positions:
                        word_positions.append((pos, word))
                word_positions.sort()
                abstract = " ".join([wp[1] for wp in word_positions])

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # 提取 URL
            url = work.get("id", "")

            # 提取 PDF URL 和开放获取状态
            pdf_url = None
            open_access = work.get("open_access", {})
            is_open_access = open_access.get("is_oa", False)
            if is_open_access:
                pdf_url = open_access.get("oa_url")

            # 提取 DOI
            doi = None
            ids = work.get("ids", {})
            if ids.get("doi"):
                doi = ids["doi"].replace("https://doi.org/", "")

            # 提取引用数
            citations = work.get("cited_by_count", 0)

            # 提取日期
            published_date = None
            pub_year = work.get("publication_year")
            if pub_year:
                published_date = datetime(int(pub_year), 1, 1)

            # 提取概念/分类
            concepts = []
            for concept in work.get("concepts", []):
                if concept.get("score", 0) > 0.3:  # 只保留高相关度的概念
                    concepts.append(concept.get("display_name", ""))

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
                categories=concepts[:5],  # 限制概念数量
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
        page = 1
        per_page = min(limit, 50)
        results = []

        while len(results) < limit:
            params = {
                "search": query,
                "per_page": per_page,
                "page": page,
                "sort": "publication_date:desc",
            }

            try:
                response = self.request_with_retry(
                    "GET",
                    f"{self.BASE_URL}/works",
                    params=params,
                    timeout=30,
                )
                data = response.json()
            except (requests.exceptions.RequestException, ValueError) as e:
                self.logger.error("OpenAlex 查询 '%s' 失败: %s", query[:40], e)
                break

            works = data.get("results", [])
            if not works:
                break

            for work in works:
                if len(results) >= limit:
                    break
                paper = self._parse_work(work, keywords, domain)
                if paper:
                    results.append(paper)

            page += 1
            time.sleep(0.1)

        return results
