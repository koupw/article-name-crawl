"""爬虫层测试：实例化冒烟、结果解析、分批搜索模板、HTTP 重试"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests

from crawlers.base import BaseCrawler
from crawlers.arxiv_crawler import ArxivCrawler
from crawlers.semantic_scholar import SemanticScholarCrawler
from crawlers.openalex_crawler import OpenAlexCrawler
from crawlers.ieee_xplore_crawler import IEEEXploreCrawler
from crawlers.google_scholar import GoogleScholarCrawler
from crawlers.crossref_crawler import CrossrefCrawler
from crawlers.core_crawler import CoreCrawler
from utils.retry import retryable_request
from conftest import make_paper


# ---------------------------------------------------------------------------
# 实例化冒烟测试（防止 session 属性等初始化回归）
# ---------------------------------------------------------------------------

class TestCrawlerInstantiation:
    def test_arxiv(self):
        assert ArxivCrawler().get_name() == "arxiv"

    def test_semantic_scholar(self):
        assert SemanticScholarCrawler().get_name() == "semantic_scholar"

    def test_openalex(self):
        assert OpenAlexCrawler().get_name() == "openalex"

    def test_openalex_with_email(self):
        crawler = OpenAlexCrawler(email="test@example.com")
        assert crawler.session.params["mailto"] == "test@example.com"

    def test_ieee_xplore(self):
        assert IEEEXploreCrawler(api_key="dummy").get_name() == "ieee_xplore"

    def test_ieee_xplore_requires_key(self):
        with pytest.raises(ValueError):
            IEEEXploreCrawler(api_key="")

    def test_google_scholar(self):
        assert GoogleScholarCrawler().get_name() == "google_scholar"


# ---------------------------------------------------------------------------
# 结果解析测试
# ---------------------------------------------------------------------------

class TestOpenAlexParse:
    def _work(self):
        return {
            "title": "FMCW Lidar Ranging",
            "authorships": [
                {"author": {"display_name": "Alice"}},
                {"author": {"display_name": None}},
                {"author": {"display_name": "Bob"}},
            ],
            "abstract_inverted_index": {"world": [1], "hello": [0]},
            "id": "https://openalex.org/W1",
            "open_access": {"is_oa": True, "oa_url": "http://example.com/a.pdf"},
            "ids": {"doi": "https://doi.org/10.1234/ABC"},
            "cited_by_count": 42,
            "publication_year": 2023,
            "concepts": [
                {"score": 0.5, "display_name": "Optics"},
                {"score": 0.1, "display_name": "LowScore"},
            ],
        }

    def test_parse_full_work(self):
        paper = OpenAlexCrawler()._parse_work(self._work(), ["fmcw"], "d")
        assert paper.title == "FMCW Lidar Ranging"
        assert paper.authors == ["Alice", "Bob"]
        assert paper.abstract == "hello world"
        assert paper.doi == "10.1234/ABC"  # 去掉 https://doi.org/ 前缀
        assert paper.citations == 42
        assert paper.is_open_access is True
        assert paper.pdf_url == "http://example.com/a.pdf"
        assert paper.year == 2023
        assert paper.categories == ["Optics"]  # 低分概念被过滤
        assert paper.matched_keywords == ["fmcw"]

    def test_parse_excluded_keyword(self):
        work = self._work()
        work["title"] = "Workshop on FMCW"
        crawler = OpenAlexCrawler(excluded_keywords=["workshop"])
        assert crawler._parse_work(work, ["fmcw"], "d") is None

    def test_parse_missing_title(self):
        work = self._work()
        work["title"] = ""
        assert OpenAlexCrawler()._parse_work(work, [], "d") is None


class TestSemanticScholarParse:
    def _result(self):
        return SimpleNamespace(
            title="FMCW Ranging Paper",
            authors=[SimpleNamespace(name="Alice"), SimpleNamespace(name=None)],
            abstract="An abstract",
            externalIds={"DOI": "10.1/x", "ArXiv": "2301.00001"},
            url="",
            publicationDate="2023-05-01",
            year=2023,
            citationCount=7,
            openAccessPdf={"url": "http://example.com/b.pdf"},
            isOpenAccess=True,
        )

    def test_parse_full_result(self):
        paper = SemanticScholarCrawler()._parse_paper(self._result(), ["fmcw"], "d")
        assert paper.doi == "10.1/x"
        assert paper.arxiv_id == "2301.00001"
        assert paper.url == "https://arxiv.org/abs/2301.00001"  # 由 arXiv ID 构建
        assert paper.citations == 7  # citationCount 已接入
        assert paper.pdf_url == "http://example.com/b.pdf"  # openAccessPdf 已接入
        assert paper.is_open_access is True
        assert paper.published_date.month == 5

    def test_parse_no_citation_data(self):
        result = self._result()
        result.citationCount = None
        result.openAccessPdf = None
        result.isOpenAccess = None
        paper = SemanticScholarCrawler()._parse_paper(result, [], "d")
        assert paper.citations == 0
        assert paper.pdf_url is None
        assert paper.is_open_access is False

    def test_parse_missing_title(self):
        result = self._result()
        result.title = None
        assert SemanticScholarCrawler()._parse_paper(result, [], "d") is None


class TestIEEEXploreParse:
    def _article(self):
        return {
            "title": "FMCW Signal Generator",
            "authors": [
                {"preferred_name": "Alice"},
                {"full_name": "Bob"},
            ],
            "abstract": "Abstract text",
            "html_url": "http://ieee.org/doc/1",
            "pdf_url": "http://ieee.org/doc/1.pdf",
            "doi": "10.1109/XYZ",
            "publication_date": "03/2023",
            "content_type": "Journals",
        }

    def test_parse_full_article(self):
        paper = IEEEXploreCrawler(api_key="k")._parse_article(self._article(), ["fmcw"], "d")
        assert paper.authors == ["Alice", "Bob"]
        assert paper.doi == "10.1109/XYZ"
        assert paper.url == "http://ieee.org/doc/1"
        assert paper.pdf_url == "http://ieee.org/doc/1.pdf"
        assert paper.published_date.year == 2023
        assert paper.published_date.month == 3
        assert paper.categories == ["Journals"]

    def test_parse_fallback_year(self):
        article = self._article()
        del article["publication_date"]
        article["publication_year"] = "2022"
        paper = IEEEXploreCrawler(api_key="k")._parse_article(article, [], "d")
        assert paper.year == 2022

    def test_build_query(self):
        crawler = IEEEXploreCrawler(api_key="k")
        query = crawler.build_query(["FMCW", "laser ranging"], [])
        assert query == 'FMCW OR "laser ranging"'


class TestArxivParse:
    def _result(self):
        from datetime import datetime
        return SimpleNamespace(
            title="  FMCW arXiv Paper  ",
            authors=["Alice", "Bob"],
            summary="Summary text",
            categories=["physics.optics"],
            published=datetime(2024, 1, 15),
            entry_id="http://arxiv.org/abs/2401.00001v1",
            pdf_url="http://arxiv.org/pdf/2401.00001v1",
            doi=None,
        )

    def test_parse_result(self):
        paper = ArxivCrawler()._parse_result(self._result(), ["fmcw"], "d")
        assert paper.title == "FMCW arXiv Paper"  # 去除首尾空格
        assert paper.arxiv_id == "2401.00001v1"
        assert paper.published_date.year == 2024
        assert paper.matched_keywords == ["fmcw"]

    def test_build_query_with_categories(self):
        query = ArxivCrawler().build_query(["FMCW", "laser ranging"], ["physics.optics"])
        assert 'cat:physics.optics' in query
        assert 'ti:FMCW' in query
        assert 'abs:"laser ranging"' in query  # 含空格关键词加引号
        assert " AND " in query


# ---------------------------------------------------------------------------
# 分批搜索模板测试
# ---------------------------------------------------------------------------

class DummyCrawler(BaseCrawler):
    """按批次序号返回预置结果的测试爬虫"""

    def __init__(self, results_per_batch: list):
        super().__init__()
        self.results_per_batch = results_per_batch
        self.queries: list[str] = []

    def get_name(self) -> str:
        return "dummy"

    def fetch_batch(self, query, keywords, categories, domain, limit):
        self.queries.append(query)
        idx = len(self.queries) - 1
        if idx < len(self.results_per_batch):
            return self.results_per_batch[idx]
        return []


class TestBatchSearchTemplate:
    def test_keywords_split_into_batches(self):
        crawler = DummyCrawler([])
        list(crawler.search(keywords=[f"kw{i}" for i in range(13)], categories=[], max_results=50))
        # 13 个关键词按每批 6 个分为 3 批
        assert len(crawler.queries) == 3

    def test_cross_batch_dedup_by_doi_and_title(self):
        p1 = make_paper(title="Paper One", doi="10.1/a")
        p2 = make_paper(title="Paper Two", doi="10.1/b")
        p2_dup = make_paper(title="Paper Two Duplicate", doi="10.1/b")  # DOI 重复
        p3 = make_paper(title="Paper Three")
        p3_dup = make_paper(title="Paper Three")  # 标题重复（无 DOI）
        crawler = DummyCrawler([[p1, p2], [p2_dup, p3], [p3_dup]])

        papers = list(crawler.search(keywords=["kw"] * 13, categories=[], max_results=50))

        assert [p.title for p in papers] == ["Paper One", "Paper Two", "Paper Three"]

    def test_max_results_cap(self):
        batch1 = [make_paper(title=f"P{i}", doi=f"10.1/{i}") for i in range(10)]
        crawler = DummyCrawler([batch1, batch1])
        papers = list(crawler.search(keywords=["kw"] * 13, categories=[], max_results=5))
        assert len(papers) <= 5

    def test_empty_keywords(self):
        crawler = DummyCrawler([])
        papers = list(crawler.search(keywords=[], categories=[], max_results=50))
        assert papers == []
        assert crawler.queries == []


class TestCrossrefParse:
    def _item(self):
        return {
            "title": ["FMCW Laser Ranging with Kerr Soliton"],
            "author": [
                {"given": "Alice", "family": "Smith"},
                {"given": "Bob", "family": "Jones"},
            ],
            "abstract": "An abstract about ranging.",
            "DOI": "10.1000/xyz123",
            "is-referenced-by-count": 15,
            "published-print": {"date-parts": [[2023, 6, 15]]},
            "type": "journal-article",
            "container-title": ["Optics Letters"],
        }

    def test_parse_full_item(self):
        paper = CrossrefCrawler()._parse_item(self._item(), ["fmcw", "ranging"], "d")
        assert paper.title == "FMCW Laser Ranging with Kerr Soliton"
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert paper.doi == "10.1000/xyz123"
        assert paper.citations == 15
        assert paper.year == 2023
        assert paper.published_date.month == 6
        assert paper.categories == ["journal-article", "Optics Letters"]
        assert paper.url == "https://doi.org/10.1000/xyz123"
        assert paper.matched_keywords == ["fmcw", "ranging"]

    def test_parse_fallback_date(self):
        item = self._item()
        del item["published-print"]
        item["published-online"] = {"date-parts": [[2022, 3]]}
        paper = CrossrefCrawler()._parse_item(item, [], "d")
        assert paper.year == 2022
        assert paper.published_date.month == 3

    def test_parse_missing_title(self):
        item = self._item()
        item["title"] = []
        assert CrossrefCrawler()._parse_item(item, [], "d") is None

    def test_build_query(self):
        crawler = CrossrefCrawler()
        query = crawler.build_query(["FMCW", "laser ranging"], [])
        assert query == "FMCW laser ranging"


class TestCoreParse:
    def _result(self):
        return {
            "title": "FMCW Lidar Signal Processing",
            "authors": ["Alice Smith", {"name": "Bob Jones"}],
            "abstract": "Abstract text here.",
            "doi": "10.1000/abc456",
            "downloadUrl": "http://example.com/paper.pdf",
            "links": ["https://doi.org/10.1000/abc456"],
            "citationCount": 8,
            "publishedDate": "2024-02-10",
            "documentType": "journal-article",
            "language": "en",
            "isOpenAccess": True,
        }

    def test_parse_full_result(self):
        paper = CoreCrawler(api_key="k")._parse_result(self._result(), ["fmcw"], "d")
        assert paper.title == "FMCW Lidar Signal Processing"
        assert paper.authors == ["Alice Smith", "Bob Jones"]
        assert paper.doi == "10.1000/abc456"
        assert paper.pdf_url == "http://example.com/paper.pdf"
        assert paper.citations == 8
        assert paper.year == 2024
        assert paper.published_date.month == 2
        assert paper.is_open_access is True
        assert paper.categories == ["journal-article", "lang:en"]

    def test_parse_missing_title(self):
        result = self._result()
        result["title"] = ""
        assert CoreCrawler(api_key="k")._parse_result(result, [], "d") is None

    def test_requires_api_key(self):
        with pytest.raises(ValueError):
            CoreCrawler(api_key="")


# ---------------------------------------------------------------------------
# HTTP 重试测试
# ---------------------------------------------------------------------------

def _response(status: int):
    resp = Mock(spec=requests.Response)
    resp.status_code = status
    if status >= 400:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError(str(status))
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestRetryableRequest:
    def test_retry_on_429_then_success(self):
        session = Mock()
        session.request.side_effect = [_response(429), _response(200)]
        resp = retryable_request("GET", "http://x", session=session, base_delay=0)
        assert resp.status_code == 200
        assert session.request.call_count == 2

    def test_retry_on_connection_error(self):
        session = Mock()
        session.request.side_effect = [
            requests.exceptions.ConnectionError("boom"),
            _response(200),
        ]
        resp = retryable_request("GET", "http://x", session=session, base_delay=0)
        assert resp.status_code == 200

    def test_retry_on_timeout(self):
        session = Mock()
        session.request.side_effect = [
            requests.exceptions.ReadTimeout("slow"),
            _response(200),
        ]
        resp = retryable_request("GET", "http://x", session=session, base_delay=0)
        assert resp.status_code == 200

    def test_no_retry_on_404(self):
        session = Mock()
        session.request.side_effect = [_response(404)]
        with pytest.raises(requests.exceptions.HTTPError):
            retryable_request("GET", "http://x", session=session, base_delay=0)
        assert session.request.call_count == 1

    def test_exhausted_retries_raise(self):
        session = Mock()
        session.request.side_effect = requests.exceptions.ConnectionError("down")
        with pytest.raises(requests.exceptions.ConnectionError):
            retryable_request("GET", "http://x", session=session, max_retries=3, base_delay=0)
        assert session.request.call_count == 3
