# 优化方案

> 基于 `article-name-crawl` 项目的全面代码审查，提出的系统性优化方案。
> 审查日期：2026-06-29

---

## 目录

1. [总览](#1-总览)
2. [P0 - 最高优先级](#2-p0-最高优先级)
   - [2.1 翻译持久化](#21-翻译持久化)
   - [2.2 并发爬取](#22-并发爬取)
3. [P1 - 高优先级](#3-p1-高优先级)
   - [3.1 关键词查询优化](#31-关键词查询优化)
   - [3.2 统一重试机制](#32-统一重试机制)
   - [3.3 翻译并发化](#33-翻译并发化)
4. [P2 - 中优先级](#4-p2-中优先级)
   - [4.1 添加单元测试](#41-添加单元测试)
   - [4.2 配置文件验证](#42-配置文件验证)
   - [4.3 多领域并行处理](#43-多领域并行处理)
5. [P3 - 低优先级](#5-p3-低优先级)
   - [5.1 输出增强](#51-输出增强)
   - [5.2 配置初始化命令](#52-配置初始化命令)
6. [性能预估](#6-性能预估)
7. [项目结构对照](#7-项目结构对照)

---

## 1. 总览

### 当前状态

| 维度 | 现状 |
|------|------|
| 总代码量 | 22 个文件，~2368 行 Python |
| 测试 | 0 |
| 爬取速度 | 5 源串行，~50s/次 |
| 翻译速度 | 逐篇串行，~25s/30篇 |
| 翻译缓存 | 无，每次重启丢失 |
| 关键词利用 | 只用了前 5 个 |
| 错误恢复 | Google Scholar 有，其余无 |

### 文件与问题对照

| 文件 | 行数 | 主要问题 |
|------|------|---------|
| `main.py` | 334 | 串行爬取、仅单领域、无进度 ETA |
| `crawlers/arxiv_crawler.py` | 118 | 无重试 |
| `crawlers/openalex_crawler.py` | 216 | 无重试、单轮搜索 |
| `crawlers/semantic_scholar.py` | 158 | 无重试、单轮搜索 |
| `crawlers/ieee_xplore_crawler.py` | 203 | 无重试 |
| `crawlers/google_scholar.py` | 195 | 有重试但延迟过大 |
| `crawlers/base.py` | 68 | 缺少通用重试、session 管理 |
| `utils/translator.py` | 88 | 单线程翻译 |
| `utils/paper_translator.py` | 44 | 逐篇串行翻译 |
| `utils/history.py` | 133 | 未缓存翻译结果 |
| `utils/dedup.py` | 124 | 逻辑正确 |
| `utils/filter.py` | 76 | 逻辑正确 |
| `config/loader.py` | 132 | 无验证、无 schema |

---

## 2. P0 - 最高优先级

### 2.1 翻译持久化

**问题**：翻译结果只存在内存中的 `paper.title_zh` 属性，每次运行需重新翻译相同论文。

**影响**：每次运行浪费 25-50s。多次运行后翻译量不会减少。

**位置**：
- `utils/history.py` — `deduplicate_with_history()` 和 `load_history()`
- `utils/history.py` — 扩展 `history[key]` 存储结构
- `main.py:306-310` — 修改跨次去重逻辑

**方案**：

```
1. 扩展历史记录结构，增加 title_zh 字段
2. deduplicate_with_history() 时，从历史恢复已有翻译
3. 翻译后，将新翻译回写到历史对象
4. save_history() 自动保存翻译结果
```

**关键变更**：

```python
# history.py: 扩展历史记录结构
history[key] = {
    "title": paper.title,
    "title_zh": paper.title_zh,    # 新增
    "source": paper.source,
    "domain": paper.domain,
    "crawled_at": datetime.now().isoformat(),
    "doi": paper.doi,
    "arxiv_id": paper.arxiv_id,
}

# main.py: 翻译前先恢复历史翻译
def _restore_translations(papers, history):
    for paper in papers:
        key = get_paper_key(paper)
        cached = history.get(key, {}).get("title_zh")
        if cached:
            paper.title_zh = cached
    return papers
```

**验证**：
- 首次运行：翻译所有新论文 → 保存到 history
- 二次运行：相同论文 → 应从 history 恢复 title_zh，无翻译请求
- 清除历史 → 重新翻译

---

### 2.2 并发爬取

**问题**：`main.py:crawl_papers()` 串行遍历爬虫列表，5 个数据源依次阻塞等待。

**影响**：假设每个数据源 5-10s，总耗时 30-50s。95% 的时间花在等待网络 IO。

**位置**：
- `main.py:159-198` — `crawl_papers()` 函数
- `main.py:269-276` — 调用处

**方案**：

```
1. 使用 concurrent.futures.ThreadPoolExecutor
2. 每个爬虫一个线程
3. 保持 console.status 进度提示
4. 单个爬虫失败不影响其他
```

**关键变更**：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def crawl_papers(crawlers, keywords, categories, domain, max_results):
    all_papers = []
    with ThreadPoolExecutor(max_workers=len(crawlers)) as executor:
        future_map = {
            executor.submit(
                _crawl_single, c, keywords, categories, max_results, domain
            ): c
            for c in crawlers
        }
        for future in as_completed(future_map):
            crawler = future_map[future]
            try:
                papers = future.result()
                all_papers.extend(papers)
                console.print(f"[green]  {crawler.get_name()}: {len(papers)} 篇[/green]")
            except Exception as e:
                console.print(f"[red]  {crawler.get_name()}: 失败 - {e}[/red]")
    return all_papers

def _crawl_single(crawler, keywords, categories, max_results, domain):
    return list(crawler.search(keywords=keywords, categories=categories,
                               max_results=max_results, domain=domain))
```

**验证**：
- 3 数据源：耗时从 ~25s 降至 ~8s
- 5 数据源：耗时从 ~50s 降至 ~12s
- 单个爬虫失败（如 API 超时），其他正常返回

---

## 3. P1 - 高优先级

### 3.1 关键词查询优化

**问题**：所有爬虫只使用 `keywords[:5]`，36 个关键词中 31 个浪费。

| 数据源 | 当前策略 | 使用关键词数 |
|--------|---------|------------|
| OpenAlex | `" ".join(keywords[:5])` | 5 |
| arXiv | `ti:kw OR abs:kw` × 10 | 10 |
| Semantic Scholar | `" ".join(keywords[:5])` | 5 |
| Google Scholar | `" ".join(keywords[:3])` | 3 |
| IEEE Xplore | `kw OR kw OR kw... × 5` | 5 |

**影响**：搜索结果覆盖面窄，很多潜在匹配论文未被发现。

**位置**：
- `crawlers/openalex_crawler.py:166-168`
- `crawlers/semantic_scholar.py:134`
- `crawlers/google_scholar.py:156`
- `crawlers/ieee_xplore_crawler.py:48-53`
- `crawlers/arxiv_crawler.py:38`

**方案**：

**分轮搜索（推荐）**：将 36 个关键词拆分为 N 组，每组 5-6 个，分别搜索后合并去重。

```python
def search(self, keywords, categories, max_results, domain):
    batch_size = 5
    per_batch = max(max_results // (len(keywords) // batch_size + 1), 10)
    seen_dois = set()
    total = 0
    
    for i in range(0, len(keywords), batch_size):
        if total >= max_results:
            break
        batch = keywords[i:i + batch_size]
        query = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in batch)
        for paper in self._search_query(query, min(per_batch, max_results - total)):
            if paper.doi and paper.doi in seen_dois:
                continue
            if paper.doi:
                seen_dois.add(paper.doi)
            total += 1
            yield paper
```

**按优先级分组**：用关键词的分类（学术、单频、扫频、非线性等）分组搜索，每组覆盖不同方向。

**验证**：
- 相同关键词数量下，搜索结果去重后数量增加
- 不降低单个查询的精度
- 总搜索结果数接近 `max_results × 轮数`

---

### 3.2 统一重试机制

**问题**：

| 爬虫 | 重试 | 回退策略 |
|------|------|---------|
| arXiv | arxiv.Client 内置 2 次 | 固定 5s 延迟 |
| Semantic Scholar | 无 | - |
| Google Scholar | 最多 3 次 | 固定 10s × retry |
| OpenAlex | 无 | - |
| IEEE Xplore | 无 | - |

**影响**：网络波动、API 限流时直接报错，一次失败导致整个数据源无结果。

**位置**：
- 新建 `crawlers/retry.py` 或 `utils/retry.py`
- 修改 `crawlers/base.py` — `BaseCrawler` 添加重试方法

**方案**：

```python
# utils/retry.py
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def with_retry(max_retries=3, base_delay=1.0, backoff=2.0):
    """指数退避重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = base_delay * (backoff ** attempt)
                        logger.warning(f"{func.__name__} 失败，"
                                      f"重试 {attempt+1}/{max_retries}，"
                                      f"等待 {delay:.1f}s: {e}")
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator
```

**可重试的异常类型**：
- `requests.exceptions.Timeout` — 超时可重试
- `requests.exceptions.ConnectionError` — 连接失败可重试
- `requests.exceptions.HTTPError` — 429/503 可重试
- `requests.exceptions.HTTPError` — 4xx（不含 429）不重试

**验证**：
- 超时场景：第一次超时 → 等待 → 重试成功
- 持续失败：重试 `max_retries` 次后正确报错
- 非重试错误（403/404）：立即失败

---

### 3.3 翻译并发化

**问题**：`utils/paper_translator.py:28-42` 逐个串行翻译，10 篇耗时 10-20s。

**影响**：30 篇论文翻译需 30-60s，是整个流程中最慢的阶段之一。

**位置**：
- `utils/paper_translator.py` — `translate_paper_titles()`
- `utils/translator.py` — 无需改动

**方案**：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def translate_paper_titles(papers):
    to_translate = [p for p in papers if not p.title_zh]
    if not to_translate:
        return papers
    
    success = 0
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {
            executor.submit(_translate_one, p): p for p in to_translate
        }
        for future in as_completed(future_map):
            paper = future_map[future]
            try:
                future.result()
                success += 1
            except Exception as e:
                logger.debug(f"翻译失败: {paper.title[:50]} - {e}")
    
    logger.info(f"翻译完成: {success}/{len(to_translate)}")
    return papers

def _translate_one(paper):
    from utils.translator import translate_to_chinese
    paper.title_zh = translate_to_chinese(paper.title)
```

**配合 2.1 翻译持久化**的叠加效果：
- 首次运行 30 篇：并发翻译 → ~5s（vs 原 25s）
- 后续运行：0 篇需翻译（从 history 恢复）

**验证**：
- 10 篇翻译耗时 < 3s
- 50 篇翻译耗时 < 10s
- 0 篇翻译（全缓存）耗时 < 1s

---

## 4. P2 - 中优先级

### 4.1 添加单元测试

**当前**：0 个测试文件。

**目标**：核心逻辑有测试覆盖，防止回归。

**结构**：

```
tests/
├── __init__.py
├── test_dedup.py        # DOI / arXiv / 标题去重
├── test_filter.py       # 各筛选条件组合
├── test_history.py      # 加载 / 保存 / 去重
├── test_config.py       # 配置解析 / 验证
└── test_paper_model.py  # 属性计算
```

**测试优先级**：

| 模块 | 测试点 | 用例数 | 优先级 |
|------|--------|--------|--------|
| dedup | DOI 去重、arXiv 去重、相似标题、不同标题 | 10 | 高 |
| filter | 引用数、年份、DOI、开放获取、组合条件 | 10 | 高 |
| history | 加载无文件、加载损坏文件、key 生成、合并 | 8 | 中 |
| config | 合法 YAML、空配置、字段缺失、多领域 | 6 | 中 |
| paper | year、authors_str、date_str 计算 | 4 | 低 |

**关键测试用例**（dedup）：

```python
def test_dedup_by_doi():
    """相同 DOI 应去重"""
    p1 = Paper(title="Paper A", doi="10.1234/a", source="arxiv", domain="test")
    p2 = Paper(title="Paper B", doi="10.1234/a", source="openalex", domain="test")
    assert len(deduplicate([p1, p2])) == 1

def test_dedup_by_similar_title():
    """相似标题应去重（>85% 阈值）"""
    p1 = Paper(title="FMCW Laser Ranging System", source="arxiv", domain="test")
    p2 = Paper(title="FMCW Laser Ranging Systems", source="openalex", domain="test")
    result = deduplicate([p1, p2])
    assert len(result) == 1

def test_dedup_no_false_positive():
    """不同论文保留"""
    p1 = Paper(title="Laser Ranging", source="arxiv", domain="test")
    p2 = Paper(title="Laser Welding", source="openalex", domain="test")
    assert len(deduplicate([p1, p2])) == 2
```

**运行方式**：

```bash
pip install pytest
pytest tests/ -v
```

---

### 4.2 配置文件验证

**问题**：`config/loader.py` 不做输入验证。负 priority、空 keywords、非法年份均静默通过。

**影响**：用户配置错误在运行时才暴露，且错误信息不友好。

**位置**：
- `config/loader.py` — 新增 `validate_config()` 函数
- `main.py` — 加载配置后调用验证

**方案**：

```python
def validate_config(config: AppConfig) -> list[str]:
    """验证配置，返回警告/错误列表"""
    issues = []

    if not config.vault_path:
        issues.append("vault_path 未设置，输出将写入当前目录")
    elif not Path(config.vault_path).exists():
        issues.append(f"vault_path 路径不存在: {config.vault_path}")

    if not config.research_domains:
        issues.append("research_domains 为空，至少需要一个研究领域")

    for name, domain in config.research_domains.items():
        if not domain.keywords:
            issues.append(f"领域 '{name}': keywords 为空")
        elif len(domain.keywords) < 3:
            issues.append(f"领域 '{name}': 关键词少于 3 个，搜索结果可能较少")
        if domain.priority < 1 or domain.priority > 10:
            issues.append(f"领域 '{name}': priority 应为 1-10")

    f = config.filters
    if f.min_citations < 0:
        issues.append("filters.min_citations 不能为负数")
    if f.year_from and f.year_to and f.year_from > f.year_to:
        issues.append(f"filters.year_from ({f.year_from}) > year_to ({f.year_to})")
    if f.year_from and f.year_from < 1900:
        issues.append(f"filters.year_from ({f.year_from}) 可能不正确")

    return issues
```

**main.py 中的调用**：

```python
config = load_config(args.config)
warnings = validate_config(config)
for w in warnings:
    console.print(f"[yellow]警告: {w}[/yellow]")
```

---

### 4.3 多领域并行处理

**问题**：配置文件支持多 `research_domains`，但 `main.py` 只处理一个（优先级最高的），其余被忽略。

**影响**：配置了多个研究领域，每次运行只能爬取一个。

**位置**：
- `main.py:220-224` — `get_domain(config, args.domain)`
- `main.py:270-276` — 爬取调用

**方案**：

```python
def process_domain(domain_config, config, args):
    """处理单个领域"""
    crawlers = get_crawlers(sources, config)
    papers = crawl_papers(...)
    unique = deduplicate(papers)
    filtered = filter_papers(unique, config.filters)
    # ... 翻译、去重、写入
    return file_path  # 每个领域生成独立文件

def main():
    ...
    domains = get_domains(config, args.domain)  # 返回列表
    for domain_config in domains:
        console.print(f"[bold]处理领域: {domain_config.name}[/bold]")
        process_domain(domain_config, config, args)
```

**CLI 接口**：

```bash
# 处理所有领域
python main.py

# 处理指定领域（不变）
python main.py --domain "FMCW Laser Ranging"

# 处理多个领域
python main.py --domain "FMCW Laser Ranging,Lidar"
```

---

## 5. P3 - 低优先级

### 5.1 输出增强

**中文字段折叠**：Markdown 中中文标题用 `<details>` 折叠，减少非中文阅读者的视觉噪音。

```markdown
| # | 标题 | 作者 | 年份 |
|---|------|------|------|
| 1 | [Title](url) <details><summary>中文</summary>中文标题</details> | Author | 2024 |
```

**摘要预览列**：

```markdown
| # | 标题 | 摘要 | 作者 | 年份 |
|---|------|------|------|------|
| 1 | [Title](pdf) | 前100字... | Author | 2024 |
```

**输出目录索引**：在 `Papers/` 目录下生成 `_index.md`，汇总所有爬取记录。

```
Papers/
├── _index.md              # 所有文件汇总索引（新增）
├── FMCW_Laser_Ranging_20260602.md
└── crawled_papers.json
```

---

### 5.2 配置初始化命令

```bash
python main.py --init          # 生成默认 research_interests.yaml
```

生成带中文注释的默认配置，降低新用户上手成本。

---

## 6. 性能预估

### 场景对比

| 场景 | 当前 | P0 | P0+P1 | P0+P1+P2 |
|------|------|-----|-------|----------|
| 3 数据源 × 30 篇 | ~30s | ~15s | ~10s | ~10s |
| 5 数据源 × 50 篇 | ~55s | ~20s | ~15s | ~15s |
| 翻译 30 篇 | ~25s | ~25s | ~5s | ~5s |
| 翻译 30 篇（有缓存） | ~25s | ~1s | ~1s | ~1s |
| 二次运行（全缓存） | ~55s | ~20s | ~15s | ~15s |

### 收益分布

```
总收益预估：3 数据源 30 篇：30s → 10s（3x 提升）
          5 数据源 50 篇：55s → 15s（3.7x 提升）

贡献比例：
  并发爬取   40%  —— 串行转并行
  翻译持久化 35%  —— 避免重复翻译
  翻译并发化 15%  —— 单篇串行转并行
  其他       10%  —— 重试、关键词等
```

---

## 7. 项目结构对照

### 当前结构

```
article-name-crawl/
├── config/
│   ├── __init__.py
│   └── loader.py          # 配置加载，无验证
├── crawlers/
│   ├── __init__.py
│   ├── base.py            # 爬虫基类，无重试
│   ├── arxiv_crawler.py   # 单轮搜索
│   ├── semantic_scholar.py
│   ├── google_scholar.py
│   ├── openalex_crawler.py
│   └── ieee_xplore_crawler.py
├── models/
│   ├── __init__.py
│   └── paper.py
├── storage/
│   ├── __init__.py
│   └── markdown_writer.py
├── utils/
│   ├── __init__.py
│   ├── translator.py      # 单线程
│   ├── paper_translator.py # 逐篇串行
│   ├── dedup.py
│   ├── filter.py
│   ├── history.py          # 无翻译缓存
│   └── logger.py
├── main.py                 # 串行，单领域
├── research_interests.yaml
├── requirements.txt
├── README.md
├── USAGE.md
└── OPTIMIZATION.md         # 本文件（优化方案）
```

### 优化后结构（新增/修改）

```
├── tests/                  ★ 新增
│   ├── __init__.py
│   ├── test_dedup.py
│   ├── test_filter.py
│   ├── test_history.py
│   └── test_config.py
├── utils/
│   ├── retry.py            ★ 新增：统一重试
│   ├── history.py           ✏ 修改：翻译持久化
│   └── paper_translator.py  ✏ 修改：并发翻译
├── crawlers/
│   ├── base.py             ✏ 修改：集成重试
│   ├── openalex_crawler.py ✏ 修改：多轮搜索
│   ├── semantic_scholar.py ✏ 修改：多轮搜索
│   └── ieee_xplore_crawler.py ✏ 修改：多轮搜索
├── config/
│   └── loader.py           ✏ 修改：配置验证
├── main.py                 ✏ 修改：并发+多领域
└── research_interests.yaml ✏ 修改：分组关键词
```

---

## 附录

### 版本演进建议

```
✅ v1.1 - 性能优化（P0）
  ├── ✅ 新增 utils/retry.py
  ├── ✅ 修改 utils/history.py（翻译持久化）
  ├── ✅ 修改 utils/paper_translator.py（并发翻译）
  ├── ✅ 修改 main.py（并发爬取）
  └── ✅ 修改 crawlers/base.py（集成重试）

✅ v1.2 - 搜索增强（P1）
  ├── ✅ 修改 crawlers/openalex_crawler.py（多轮搜索）
  ├── ✅ 修改 crawlers/semantic_scholar.py（多轮搜索）
  └── ✅ 修改 crawlers/ieee_xplore_crawler.py（多轮搜索）

✅ v1.3 - 质量改进（P2）
  ├── ✅ 新增 tests/ 目录（69 个测试）
  ├── ✅ 修改 config/loader.py（配置验证）
  ├── ✅ 修改 main.py（多领域支持）
  └── ✅ 新增 tests/test_config.py（配置单元测试）

✅ v1.4 - 体验优化（P3）
  ├── ✅ 修改 storage/markdown_writer.py（索引文件 _index.md）
  └── ✅ 新增 --init 命令（生成默认配置）
```

### 相关资源

- [concurrent.futures 文档](https://docs.python.org/3/library/concurrent.futures.html)
- [requests 重试策略](https://requests.readthedocs.io/en/latest/user/advanced/#transport-adapters)
- [pytest 文档](https://docs.pytest.org/)
- [OpenAlex API](https://docs.openalex.org/)
- [arXiv API](https://info.arxiv.org/help/api/index.html)
