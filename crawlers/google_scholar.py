"""Google Scholar 论文爬虫

注意：Google Scholar 无官方 API，使用 scholarly 库进行爬取。
该库不稳定，可能因 CAPTCHA 或 HTML 结构变化而失败。
"""

import time
import random
from typing import Generator, Optional
from datetime import datetime

from crawlers.base import BaseCrawler
from models.paper import Paper


class GoogleScholarCrawler(BaseCrawler):
    """Google Scholar 爬虫（不稳定，作为可选数据源）"""

    def __init__(
        self,
        use_proxy: bool = False,
        proxy_url: Optional[str] = None,
        excluded_keywords: list[str] = None,
    ):
        super().__init__(excluded_keywords)
        self.use_proxy = use_proxy
        self.proxy_url = proxy_url
        self._scholarly = None
        self._setup_scholarly()

    def _setup_scholarly(self):
        """初始化 scholarly 库"""
        try:
            from scholarly import scholarly, ProxyGenerator

            self._scholarly = scholarly

            if self.use_proxy and self.proxy_url:
                pg = ProxyGenerator()
                pg.SingleProxy(http=self.proxy_url, https=self.proxy_url)
                scholarly.use_proxy(pg)
                self.logger.info(f"Google Scholar: 使用代理 {self.proxy_url}")
            elif self.use_proxy:
                pg = ProxyGenerator()
                pg.FreeProxies()
                scholarly.use_proxy(pg)
                self.logger.info("Google Scholar: 使用免费代理")
            else:
                self.logger.info("Google Scholar: 无代理")

        except ImportError:
            self.logger.error("scholarly 库未安装，请运行: pip install scholarly")
            self._scholarly = None
        except Exception as e:
            self.logger.error(f"初始化 scholarly 失败: {e}")
            self._scholarly = None

    def get_name(self) -> str:
        return "google_scholar"

    def _random_delay(self):
        """随机延迟 5-10 秒，避免被封"""
        delay = random.uniform(5.0, 10.0)
        time.sleep(delay)

    def _parse_paper(self, result, keywords: list[str], domain: str) -> Optional[Paper]:
        """解析 Google Scholar 结果为 Paper 对象

        Args:
            result: scholarly 返回的论文数据
            keywords: 关键词列表
            domain: 研究领域

        Returns:
            Paper 对象，解析失败返回 None
        """
        try:
            bib = result.get("bib", {})
            title = bib.get("title", "")
            if not title:
                return None

            # 检查是否应排除
            if self.should_exclude(title):
                self.logger.debug(f"排除论文: {title}")
                return None

            # 提取作者
            authors = bib.get("author", [])
            if isinstance(authors, str):
                authors = [authors]

            # 提取摘要
            abstract = bib.get("abstract", "")

            # 匹配关键词
            text = f"{title} {abstract}"
            matched = self.match_keywords(text, keywords)

            # 提取 URL
            url = result.get("pub_url", "") or result.get("eprint_url", "")

            # 提取 PDF URL
            pdf_url = result.get("eprint_url", "")

            # 提取年份
            published_date = None
            year = bib.get("pub_year")
            if year:
                try:
                    published_date = datetime(int(year), 1, 1)
                except (ValueError, TypeError):
                    pass

            return Paper(
                title=title.strip(),
                authors=authors,
                abstract=abstract.strip(),
                url=url,
                pdf_url=pdf_url if pdf_url else None,
                source=self.get_name(),
                domain=domain,
                matched_keywords=matched,
                published_date=published_date,
                arxiv_id=None,
                doi=None,
                categories=[],
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
        """搜索 Google Scholar 论文

        Args:
            keywords: 关键词列表
            categories: 分类列表（未使用）
            max_results: 最大结果数
            domain: 研究领域名称

        Yields:
            Paper 对象
        """
        if not self._scholarly:
            self.logger.warning("scholarly 库不可用，跳过 Google Scholar")
            return

        # 组合关键词查询
        query = " ".join(keywords[:3])
        self.logger.info(f"Google Scholar 查询: {query}")

        count = 0
        retries = 0
        max_retries = 3

        try:
            search_query = self._scholarly.search_pubs(query)

            while count < max_results:
                try:
                    result = next(search_query)
                    self._random_delay()

                    paper = self._parse_paper(result, keywords, domain)
                    if paper:
                        count += 1
                        self.logger.debug(f"[{count}] {paper.title}")
                        yield paper

                    retries = 0  # 重置重试计数

                except StopIteration:
                    break
                except Exception as e:
                    retries += 1
                    self.logger.warning(f"Google Scholar 请求失败 ({retries}/{max_retries}): {e}")

                    if retries >= max_retries:
                        self.logger.error("Google Scholar 达到最大重试次数，停止爬取")
                        break

                    # 增加延迟后重试
                    time.sleep(10 * retries)

        except Exception as e:
            self.logger.error(f"Google Scholar 搜索失败: {e}")

        self.logger.info(f"Google Scholar 共返回 {count} 篇论文")
