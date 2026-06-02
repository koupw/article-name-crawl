# 使用指南

## 快速开始

```bash
# 进入项目目录
cd E:/WorkSpace/ClaudeWork/article-name-crawl

# 激活虚拟环境
.venv\Scripts\activate

# 查看帮助
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
```

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

## 输出文件位置

默认输出到配置文件中的 `vault_path/papers_dir`：

```
E:/WorkSpace/ClaudeWork/fmcw-article/20_Research/Papers/
├── FMCW_Laser_Ranging_20260602_195551.md    # 论文列表
└── crawled_papers.json                      # 历史记录
```

## 标题翻译

```bash
# 默认自动翻译（英文 → 中文）
python main.py --sources openalex --max-results 20

# 禁用翻译
python main.py --sources openalex --max-results 20 --no-translate
```

翻译使用 Google Translate，无需 API Key。

## 常用命令速查

| 需求 | 命令 |
|------|------|
| 快速预览 | `python main.py --dry-run --sources openalex` |
| 高质量论文 | `python main.py --sources openalex --min-citations 10` |
| 最新论文 | `python main.py --sources arxiv,openalex --year-from 2024` |
| 完整爬取 | `python main.py --sources arxiv,openalex --max-results 100` |
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
├── README.md                  # 项目说明
├── USAGE.md                   # 使用指南（本文件）
├── main.py                    # 主程序
├── config/                    # 配置模块
├── crawlers/                  # 爬虫模块
├── models/                    # 数据模型
├── storage/                   # 存储模块
└── utils/                     # 工具模块
```
