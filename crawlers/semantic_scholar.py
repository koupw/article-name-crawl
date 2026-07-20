"""Semantic Scholar 论文爬虫"""

from typing import Optional
from datetime import datetime

from semanticscholar import SemanticScholar
from semanticscholar.SemanticScholarException import ObjectNotFoundException

from crawlers.base import BaseCrawler
from models.paper import Paper


class SemanticScholarCrawler(BaseCrawler):
    """Semantic Scholar API 爬虫"""

    # 请求的字段
    FIELDS = [
        "title",
        "abstract",
        "authors",
        "year",
        "externalIds",
        "url",
        "publicationDate",
        "venue",
        "citationCount",
        "openAccessPdf",
        "isOpenAccess",
    ]

    def __init__(
        self,
        api_key: Optional[str] = None,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        if api_key:
            self.sch = SemanticScholar(api_key=api_key)
            self.logger.info("Semantic Scholar: 使用 API Key")
        else:
            self.sch = SemanticScholar()
            self.logger.info("Semantic Scholar: 无 API Key (速率限制较低)")

    def get_name(self) -> str:
        return "semantic_scholar"

    def _parse_paper(self, result, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 Semantic Scholar 结果为 Paper 对象

        Args:
            result: API 返回的论文数据
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            title = result.title
            if not title:
                return None

            # 检查是否应排除
            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 提取作者
            authors = []
            if result.authors:
                authors = [author.name for author in result.authors if author.name]

            # 提取摘要
            abstract = result.abstract or ""

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # 提取外部 ID
            external_ids = result.externalIds or {}
            doi = external_ids.get("DOI")
            arxiv_id = external_ids.get("ArXiv")

            # 构建 URL
            url = result.url or ""
            if arxiv_id and not url:
                url = f"https://arxiv.org/abs/{arxiv_id}"

            # 提取 PDF URL（开放获取）
            pdf_url = None
            open_access_pdf = result.openAccessPdf
            if isinstance(open_access_pdf, dict):
                pdf_url = open_access_pdf.get("url")

            # 提取引用数与开放获取状态
            citations = result.citationCount or 0
            is_open_access = bool(result.isOpenAccess)

            # 提取日期
            published_date = None
            if result.publicationDate:
                try:
                    published_date = datetime.strptime(result.publicationDate, "%Y-%m-%d")
                except ValueError:
                    pass
            elif result.year:
                published_date = datetime(result.year, 1, 1)

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
                arxiv_id=arxiv_id,
                doi=doi,
                categories=[],
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
        """单批关键词搜索

        Args:
            query: 搜索查询
            keywords: 本批关键词
            categories: 分类列表（未使用）
            domain: 研究领域
            limit: 本批最大结果数

        Returns:
            论文列表
        """
        try:
            results = self.sch.search_paper(
                query=query,
                limit=limit,
                fields=self.FIELDS,
            )
        except ObjectNotFoundException:
            return []
        except Exception as e:
            self.logger.error("Semantic Scholar 查询 '%s' 失败: %s", query[:40], e)
            return []

        papers = []
        for result in results.items:
            paper = self._parse_paper(result, keywords, domain)
            if paper:
                papers.append(paper)

        return papers
