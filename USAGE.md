# 使用指南

## 快速开始

```bash
# 进入项目目录
cd E:/WorkSpace/ClaudeWork/article-name-crawl

# 激活虚拟环境
.venv\Scripts\activate

# 首次使用：生成默认配置文件
python main.py --init

# 编辑 research_interests.yaml，输入你的研究领域和关键词

# 快速预览（不写入文件）
python main.py --dry-run

# 正式爬取
python main.py

# 查看完整帮助
python main.py --help
```

## 基本爬取

```bash
# 使用最安全的数据源爬取（推荐）
python main.py --sources arxiv,openalex --max-results 20

# 只用 OpenAlex（免费，有引用数）
python main.py --sources openalex --max-results 50

# 只用 arXiv
python main.py --sources arxiv --max-results 30

# 指定研究领域（默认自动处理所有领域）
python main.py --domain "FMCW Laser Ranging"

# 处理所有领域（按 priority 排序）
python main.py

# 处理多个指定领域
python main.py --domain "FMCW Laser Ranging,Lidar"
```

> **提示**：数据源之间**并发爬取**，多个数据源不额外增加等待时间，总耗时 ≈ 最慢的数据源。

## 质量筛选

```bash
# 只获取引用数 >= 5 的论文
python main.py --sources openalex --min-citations 5

# 只获取 2023 年后的论文
python main.py --sources openalex --year-from 2023

# 组合筛选
python main.py --sources openalex --min-citations 3 --year-from 2022
```

## 输出控制

```bash
# 指定输出目录
python main.py --output ./my_papers

# 干跑模式（预览结果，不写入文件）
python main.py --dry-run --max-results 10

# 详细日志
python main.py --verbose
```

## 历史记录管理

```bash
# 查看历史记录（默认开启跨次去重）
python main.py --sources openalex --max-results 20

# 禁用跨次去重（每次都爬取全部）
python main.py --sources openalex --no-history

# 清除历史记录重新爬取
python main.py --clear-history
```

## 配置文件优化

编辑 `research_interests.yaml`：

```yaml
# 设置默认数据源和筛选条件
filters:
  min_citations: 3        # 只要引用数 >= 3 的论文
  year_from: 2020         # 只要 2020 年后的论文
  require_doi: true       # 必须有 DOI

# API 配置（可选）
openalex_email: "your@email.com"  # 提高 OpenAlex 响应速度
```

## 推荐工作流

```bash
# 第一次：全面爬取
python main.py --sources arxiv,openalex --max-results 100 --output ./papers

# 后续：增量更新（自动跳过已爬取的）
python main.py --sources arxiv,openalex --max-results 50 --output ./papers

# 高质量筛选
python main.py --sources openalex --min-citations 10 --year-from 2023
```

## 保证每次爬取有新文章

由于默认开启跨次去重，多次爬取相同关键词可能没有新文章。以下是解决方案：

### 方案 1：调整关键词（最有效）

编辑 `research_interests.yaml`，添加更宽泛的关键词：

```yaml
keywords:
  # 现有关键词
  - frequency modulated continuous wave
  - FMCW
  # 添加更宽泛的关键词
  - laser ranging
  - distance measurement
  - interferometry
  - optical measurement
  - lidar
  - time of flight
```

### 方案 2：增加数据源

```bash
# 使用所有数据源
python main.py --sources arxiv,semantic_scholar,openalex,ieee_xplore --max-results 50
```

### 方案 3：调整时间范围

```yaml
# research_interests.yaml
filters:
  year_from: 2024  # 只爬取 2024 年以后的论文
```

或命令行：

```bash
python main.py --sources arxiv,openalex --year-from 2024
```

### 方案 4：增加最大结果数

```bash
python main.py --sources arxiv,openalex --max-results 100
```

### 方案 5：定期更新关键词

根据研究进展，在 `research_interests.yaml` 中添加新出现的技术术语：

```yaml
keywords:
  # 添加新术语
  - synthetic aperture lidar
  - coherent detection
  - frequency comb ranging
```

### 推荐配置

```bash
# 每周运行一次，使用宽泛关键词，只爬取最近论文
python main.py --sources arxiv,openalex,semantic_scholar --max-results 100 --year-from 2024
```

## 输出文件位置

默认输出到配置文件中的 `vault_path/papers_dir`：

```
E:/WorkSpace/ClaudeWork/article-name-crawl/Papers/
├── _index.md                          # 📚 索引（汇总所有列表文件）
├── FMCW_Laser_Ranging_20260629.md     # 论文列表（每次爬取生成一个文件）
├── FMCW_Laser_Ranging_20260604.md     # 历史爬取记录
└── crawled_papers.json                # 历史记录（跨次去重 + 翻译缓存）
```

## 标题翻译

```bash
# 默认自动翻译（英文 → 中文）
python main.py --sources openalex --max-results 20

# 禁用翻译
python main.py --sources openalex --max-results 20 --no-translate
```

翻译使用 Google Translate，无需 API Key。

**性能优化**：
- **并发翻译**：默认 5 线程同时翻译，30 篇论文约 5 秒完成
- **翻译持久化**：翻译结果自动缓存到 `crawled_papers.json`，下次运行相同论文不再请求翻译

## 配置初始化

```bash
# 生成带注释的默认配置文件
python main.py --init
```

生成 `research_interests.yaml`，包含示例领域、API 配置项、筛选条件的完整中文注释。如果文件已存在则跳过，不会覆盖。

## 常用命令速查

| 需求 | 命令 |
|------|------|
| 快速预览 | `python main.py --dry-run --sources openalex` |
| 高质量论文 | `python main.py --sources openalex --min-citations 10` |
| 最新论文 | `python main.py --sources arxiv,openalex --year-from 2024` |
| 完整爬取 | `python main.py --sources arxiv,openalex --max-results 100` |
| 多领域爬取 | `python main.py --domain all` |
| 生成默认配置 | `python main.py --init` |
| 清除重爬 | `python main.py --clear-history` |
| 不翻译 | `python main.py --sources openalex --no-translate` |

## 数据源选择

| 数据源 | 特点 | 推荐场景 |
|--------|------|----------|
| `arxiv` | 免费、稳定、预印本 | 获取最新研究 |
| `openalex` | 免费、有引用数、覆盖广 | 日常使用首选 |
| `semantic_scholar` | 有引用数、需 API Key | 补充引用数据 |
| `ieee_xplore` | 工程技术权威 | 工程领域研究 |
| `google_scholar` | 覆盖最广、不稳定 | 不推荐 |

## 质量筛选说明

| 筛选条件 | 说明 | 支持的数据源 |
|----------|------|--------------|
| `min_citations` | 最低引用数 | OpenAlex, Semantic Scholar |
| `year_from` | 起始年份 | 所有数据源 |
| `year_to` | 结束年份 | 所有数据源 |
| `require_doi` | 必须有 DOI | 所有数据源 |
| `open_access_only` | 只要开放获取 | OpenAlex |

## 去重机制

### 单次去重（自动）
- DOI 相同 → 重复
- arXiv ID 相同 → 重复
- 标题相似度 > 85% → 重复

### 跨次去重（默认开启）
- 记录历史爬取到 `crawled_papers.json`
- 自动跳过已爬取的论文
- 使用 `--no-history` 禁用
- 使用 `--clear-history` 清除历史

## 常见问题

### Q: 如何只获取高质量论文？

```bash
python main.py --sources openalex --min-citations 10 --year-from 2020
```

### Q: 多次运行会重复吗？

不会。默认开启跨次去重，自动跳过已爬取的论文。

### Q: 如何重新爬取所有论文？

```bash
python main.py --clear-history
python main.py --sources arxiv,openalex --max-results 100
```

### Q: 哪个数据源最安全？

OpenAlex 和 arXiv 最安全，不会被封 IP。

### Q: 如何获取最新论文？

```bash
python main.py --sources arxiv --year-from 2024 --max-results 50
```

### Q: 翻译功能需要付费吗？

不需要。翻译使用 Google Translate 免费接口，无需 API Key。

### Q: 如何禁用翻译？

```bash
python main.py --sources openalex --no-translate
```

### Q: 翻译准确吗？

翻译质量取决于 Google Translate。对于专业术语可能不完全准确，建议参考原文。

### Q: 翻译会重复请求 Google API 吗？

不会。翻译结果会自动缓存到 `crawled_papers.json`，下次运行相同论文直接从缓存恢复，不发起翻译请求。

### Q: 如何配置多个研究领域？

在 `research_interests.yaml` 的 `research_domains` 下并列添加：

```yaml
research_domains:
  FMCW Laser Ranging:
    keywords: [...]
    arxiv_categories: [...]
    priority: 5

  Lidar:
    keywords:
      - lidar
      - time-of-flight
      - 3D imaging
    arxiv_categories:
      - physics.optics
    priority: 3
```

运行 `python main.py` 自动按 priority 从高到低处理所有领域。

### Q: 如何对新用户快速上手？

```bash
# 1. 生成默认配置
python main.py --init

# 2. 编辑 research_interests.yaml，填入你的研究关键词

# 3. 快速预览
python main.py --dry-run

# 4. 正式爬取
python main.py
```

## 输出格式

爬取结果为 Markdown 文件，包含：

```markdown
---
title: FMCW Laser Ranging Papers
date: 2026-06-02
domain: FMCW Laser Ranging
total: 42
sources:
  arxiv: 25
  openalex: 17
---

# FMCW Laser Ranging 论文列表

| # | 标题 | 中文标题 | 作者 | 日期 | 链接 |
|---|------|----------|------|------|------|
| 1 | [论文标题](url) | 论文中文标题 | 作者 | 2024-03 | [PDF](pdf_url) |
```

## 目录结构

```
article-name-crawl/
├── research_interests.yaml    # 配置文件
├── OPTIMIZATION.md            # 优化方案文档
├── README.md                  # 项目说明
├── USAGE.md                   # 使用指南（本文件）
├── requirements.txt           # Python 依赖
├── main.py                    # CLI 入口
├── config/                    # 配置模块
│   ├── __init__.py
│   └── loader.py              # 配置加载 + 验证
├── crawlers/                  # 爬虫模块
│   ├── __init__.py
│   ├── base.py                # 爬虫基类（含重试机制）
│   ├── arxiv_crawler.py       # arXiv 爬虫
│   ├── semantic_scholar.py    # Semantic Scholar 爬虫（多轮搜索）
│   ├── google_scholar.py      # Google Scholar 爬虫
│   ├── openalex_crawler.py    # OpenAlex 爬虫（多轮搜索）
│   └── ieee_xplore_crawler.py # IEEE Xplore 爬虫（多轮搜索）
├── models/
│   ├── __init__.py
│   └── paper.py               # 论文数据模型
├── storage/
│   ├── __init__.py
│   └── markdown_writer.py     # Markdown 输出 + 索引生成
├── tests/                     # 单元测试（69 个测试用例）
│   ├── conftest.py            # 测试夹具与工厂函数
│   ├── test_config.py         # 配置验证测试
│   ├── test_dedup.py          # 去重逻辑测试
│   ├── test_filter.py         # 质量筛选测试
│   ├── test_history.py        # 历史记录测试
│   └── test_paper_model.py    # 数据模型测试
└── utils/
    ├── __init__.py
    ├── dedup.py               # 去重逻辑
    ├── filter.py              # 质量筛选
    ├── history.py             # 历史记录管理（跨次去重 + 翻译缓存）
    ├── logger.py              # 日志配置
    ├── paper_translator.py    # 并发翻译
    ├── retry.py               # 统一重试机制（指数退避）
    └── translator.py          # 翻译引擎（Google Translate）
```
