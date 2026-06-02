"""OpenAlex 论文爬虫

OpenAlex 是免费、开放的学术数据源，覆盖 2 亿+ 学术文献。
API 文档: https://docs.openalex.org/
"""

import requests
from typing import Generator, Optional
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
        self.session = requests.Session()
        # 添加 polite pool 邮箱以获得更快响应
        if email:
            self.session.params = {"mailto": email}

    def get_name(self) -> str:
        return "openalex"

    def _build_filter(
        self,
        keywords: list[str],
    ) -> str:
        """构建 OpenAlex 过滤器

        Args:
            keywords: 关键词列表

        Returns:
            过滤器字符串
        """
        # OpenAlex 使用 search 参数进行全文搜索，不需要额外过滤器
        return ""

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

    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """搜索 OpenAlex 论文

        Args:
            keywords: 关键词列表
            categories: 分类列表（OpenAlex 使用概念而非 arXiv 分类）
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        # 构建搜索查询
        query = " ".join(keywords[:5])
        self.logger.info(f"OpenAlex 查询: {query}")

        # 构建过滤器
        filter_str = self._build_filter(keywords)

        page = 1
        per_page = min(max_results, 50)  # OpenAlex 每页最多 50
        count = 0

        while count < max_results:
            params = {
                "search": query,
                "per_page": per_page,
                "page": page,
                "sort": "publication_date:desc",
            }
            if filter_str:
                params["filter"] = filter_str

            try:
                response = self.session.get(
                    f"{self.BASE_URL}/works",
                    params=params,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenAlex 请求失败: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            for work in results:
                paper = self._parse_work(work, keywords, domain)
                if paper:
                    count += 1
                    self.logger.debug(f"[{count}] {paper.title}")
                    yield paper

                    if count >= max_results:
                        break

            page += 1
            time.sleep(0.1)  # 短暂延迟

        self.logger.info(f"OpenAlex 共返回 {count} 篇论文")
