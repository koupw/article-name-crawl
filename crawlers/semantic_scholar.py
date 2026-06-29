"""Semantic Scholar 论文爬虫"""

from typing import Generator, Optional
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
                pdf_url=None,  # Semantic Scholar 不直接提供 PDF
                source=self.get_name(),
                domain=domain,
                matched_keywords=matched,
                published_date=published_date,
                arxiv_id=arxiv_id,
                doi=doi,
                categories=[],
            )
        except Exception as e:
            self.logger.warning(f"解析论文失败: {e}")
            return None

    def _search_batch(
        self,
        query: str,
        keywords: list[str],
        domain: str,
        limit: int,
        seen_dois: set[str],
    ) -> list[Paper]:
        """单批关键词搜索

        Args:
            query: 搜索查询
            keywords: 本批关键词
            domain: 研究领域
            limit: 本批最大结果数
            seen_dois: 已见 DOI 集合（跨批去重）

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
            if not paper:
                continue

            # 跨轮去重
            if paper.doi:
                if paper.doi in seen_dois:
                    continue
                seen_dois.add(paper.doi)

            papers.append(paper)

        return papers

    def search(
        self,
        keywords: list[str],
        categories: list[str],
        max_results: int = 50,
        domain: str = "",
    ) -> Generator[Paper, None, None]:
        """搜索 Semantic Scholar 论文（多轮关键词搜索）

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
            "Semantic Scholar 多轮搜索: %d 批, 每批最多 %d 篇",
            len(batches), per_batch,
        )

        seen_dois: set[str] = set()
        total = 0

        for batch_idx, batch in enumerate(batches):
            if total >= max_results:
                break

            query = " ".join(batch)
            remaining = max_results - total
            batch_limit = min(per_batch, remaining)

            self.logger.debug(
                "第 %d/%d 批: %s", batch_idx + 1, len(batches), query[:80],
            )

            papers = self._search_batch(
                query=query,
                keywords=batch,
                domain=domain,
                limit=batch_limit,
                seen_dois=seen_dois,
            )

            for paper in papers:
                total += 1
                self.logger.debug("[%d/%d] %s", total, max_results, paper.title[:70])
                yield paper

        self.logger.info("Semantic Scholar 共返回 %d 篇论文（%d 批搜索）", total, len(batches))
