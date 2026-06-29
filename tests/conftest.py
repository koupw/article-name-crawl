"""测试配置 - 添加项目根目录到 sys.path"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# 将项目根目录加入导入路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.paper import Paper


def make_paper(
    title: str = "Test Paper",
    authors: Optional[list[str]] = None,
    abstract: str = "",
    url: str = "",
    source: str = "arxiv",
    domain: str = "test",
    citations: int = 0,
    year: Optional[int] = None,
    doi: Optional[str] = None,
    arxiv_id: Optional[str] = None,
    is_open_access: bool = False,
    title_zh: Optional[str] = None,
) -> Paper:
    """创建测试用论文，提供合理的默认值"""
    published_date = datetime(year, 1, 1) if year else None
    return Paper(
        title=title,
        authors=authors or [],
        abstract=abstract,
        url=url,
        source=source,
        domain=domain,
        citations=citations,
        published_date=published_date,
        doi=doi,
        arxiv_id=arxiv_id,
        is_open_access=is_open_access,
        title_zh=title_zh,
    )
