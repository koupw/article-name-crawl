# 论文名称爬取工具

根据研究领域关键词，从多个学术数据源爬取相关论文信息，输出为 Obsidian 兼容的 Markdown 文件。

## 功能特性

- **多数据源支持**：arXiv、Semantic Scholar、Google Scholar、OpenAlex、IEEE Xplore、Crossref、CORE
- **并发爬取**：所有数据源同时爬取，总耗时 ≈ 最慢的单个数据源
- **智能去重**：基于 DOI、arXiv ID、标题相似度的多级去重 + 跨次去重
- **标题翻译**：自动翻译英文标题为中文（Google / 百度），结果持久化缓存
- **论文深度分析**：选择论文 → MinerU PDF 解析 → LLM 生成 14 章结构化报告（含评分/执行摘要/图片）
- **Web 界面**：Streamlit 双页面（爬取 + 分析），双击 vbs 一键启动

## 安装

### 1. 克隆项目

```bash
cd article-name-crawl
```

### 2. 创建虚拟环境

```bash
python -m venv .venv
```

### 3. 激活虚拟环境

**Windows:**
```bash
.venv\Scripts\activate
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 🔒 安全提示

本项目**不将任何 API Key 或凭证存入 Git**。`research_interests.yaml` 和 `.env` 已被 `.gitignore` 排除。

**推荐使用环境变量管理密钥（最安全的做法）：**

```bash
# Windows PowerShell
$env:SEMANTIC_SCHOLAR_API_KEY = "your-key"
$env:CORE_API_KEY = "your-key"

# 或复制 .env.example 为 .env 填入值（.env 已自动排除不入 git）
copy .env.example .env
```

> ⚠️ **切勿**将真实 API Key 填入 `research_interests.yaml` 后再分享项目目录，该文件虽被 git 排除，但本地明文仍存在泄露风险。

## 快速使用（Web 界面，推荐）

无需记命令行参数，在浏览器中图形化操作：

```bash
# 方式 1：双击 web\launch.vbs（无黑窗，最推荐）
# 方式 2：使用 Python 启动器
python web/launch.py

# 或手动启动
streamlit run web/streamlit_app.py
```

然后在浏览器打开 `http://127.0.0.1:8501/`，即可在网页上完成：
- 选择研究领域、数据源
- 调整筛选条件（引用数、年份）
- 实时查看爬取进度和日志
- 结果表格展示，支持排序筛选
- 一键下载 Markdown

## CLI 使用（高级）

编辑 `research_interests.yaml` 文件：

```yaml
language: zh
vault_path: ./
papers_dir: papers

research_domains:
  FMCW Laser Ranging:
    keywords:
      - frequency modulated continuous wave
      - FMCW
      - laser ranging
      # ... 更多关键词
    arxiv_categories:
      - physics.optics
      - physics.ins-det
      - eess.SP
      - physics.app-ph
    priority: 5

excluded_keywords:
  - workshop

# API 配置（默认无需任何 Key 即可使用 arxiv + openalex + crossref）
semantic_scholar_api_key: ''  # 可选
ieee_api_key: ''              # IEEE Xplore 需要
openalex_email: ''            # 可选，提高响应速度
core_api_key: ''              # CORE 需要（免费注册）

# 翻译引擎配置
translate_backend: google       # 翻译引擎: google | baidu
baidu_translate_app_id: ''      # 百度翻译 APP ID (使用 baidu 时必填)
baidu_translate_app_key: ''     # 百度翻译 Secret Key

# 质量筛选配置
filters:
  min_citations: 0          # 最低引用数（0 表示不限制）
  year_from: null           # 起始年份（null 表示不限制）
  year_to: null             # 结束年份（null 表示不限制）
  require_doi: false        # 是否必须有 DOI
  open_access_only: false   # 是否只要开放获取的论文
```

### 配置说明

API 密钥类配置项同时支持环境变量（配置文件留空时读取），避免明文写入文件：
`SEMANTIC_SCHOLAR_API_KEY`、`IEEE_API_KEY`、`OPENALEX_EMAIL`、`BAIDU_TRANSLATE_APP_ID`、`BAIDU_TRANSLATE_APP_KEY`

| 字段 | 说明 |
|------|------|
| `language` | 输出语言 (zh/en) |
| `vault_path` | Obsidian vault 路径 |
| `papers_dir` | vault 内的论文目录 |
| `research_domains` | 研究领域配置 |
| `keywords` | 该领域的关键词列表 |
| `arxiv_categories` | arXiv 分类代码 |
| `priority` | 优先级 (数字越大越优先) |
| `excluded_keywords` | 排除含这些词的论文 |
| `semantic_scholar_api_key` | Semantic Scholar API Key (可选) |
| `ieee_api_key` | IEEE Xplore API Key (使用 IEEE 数据源时必填) |
| `openalex_email` | OpenAlex 邮箱 (可选，提高响应速度) |
| `translate_backend` | 翻译引擎 (google/baidu)，默认 google |
| `baidu_translate_app_id` | 百度翻译 APP ID (使用 baidu 时必填) |
| `baidu_translate_app_key` | 百度翻译 Secret Key |
| `filters.min_citations` | 最低引用数（0 表示不限制） |
| `filters.year_from` | 起始年份（null 表示不限制） |
| `filters.year_to` | 结束年份（null 表示不限制） |
| `filters.require_doi` | 是否必须有 DOI |
| `filters.open_access_only` | 是否只要开放获取的论文 |

## 使用方法

### 基本用法

```bash
# 爬取默认领域（优先级最高）
python main.py

# 爬取指定领域
python main.py --domain "FMCW Laser Ranging"
```

### 高级选项

```bash
# 指定数据源（默认已用最优组合 arxiv+openalex+crossref）
python main.py --sources arxiv,openalex,crossref,core

# 指定最大结果数
python main.py --max-results 100

# 指定输出目录
python main.py --output ./output

# 详细日志
python main.py --verbose

# 干跑模式（不写入文件）
python main.py --dry-run

# 质量筛选（只获取引用数 >= 10 的论文）
python main.py --min-citations 10

# 年份筛选（只获取 2020 年后的论文）
python main.py --year-from 2020

# 不使用历史记录（禁用跨次去重）
python main.py --no-history

# 清除历史记录
python main.py --clear-history

# 不翻译论文标题
python main.py --no-translate

# 生成默认配置文件（首次使用）
python main.py --init

# 处理指定领域
python main.py --domain "FMCW Laser Ranging"

# 处理多个领域
python main.py --domain "FMCW Laser Ranging,Lidar"

# 处理所有领域
python main.py --domain all
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | `research_interests.yaml` |
| `--domain` | 研究领域名称。支持逗号分隔（`"A,B"`）或 `all`（全部领域） | 全部领域（按 priority 排序） |
| `--sources` | 数据源，逗号分隔 | `arxiv,semantic_scholar,google_scholar,openalex,ieee_xplore` |
| `--max-results` | 每个数据源最大结果数 | `50` |
| `--output` | 输出目录 | 配置文件中的 `vault_path/papers_dir` |
| `--verbose` | 详细日志 | `False` |
| `--dry-run` | 干跑模式（预览不写入） | `False` |
| `--init` | 生成默认配置文件 | `False` |
| `--no-history` | 不使用历史记录（禁用跨次去重） | `False` |
| `--clear-history` | 清除历史记录 | `False` |
| `--min-citations` | 最低引用数（覆盖配置文件） | 配置文件值 |
| `--year-from` | 起始年份（覆盖配置文件） | 配置文件值 |
| `--no-translate` | 不翻译论文标题 | `False` |

## 输出格式

生成的 Markdown 文件结构如下：

```markdown
---
title: FMCW Laser Ranging Papers
date: 2026-06-02
domain: FMCW Laser Ranging
total: 42
sources:
  arxiv: 25
  semantic_scholar: 15
  google_scholar: 2
---

# FMCW Laser Ranging 论文列表

共找到 **42** 篇相关论文

## arXiv (25 篇)

### 2024

| # | 标题 | 中文标题 | 作者 | 日期 | 链接 |
|---|------|----------|------|------|------|
| 1 | [FMCW Laser Ranging with...](https://arxiv.org/abs/xxx) | FMCW 激光测距... | Wang et al. | 2024-03 | [PDF](https://arxiv.org/pdf/xxx) |

## Semantic Scholar (15 篇)

...
```

## 数据源说明

### arXiv
- **可靠性**: 高
- **速率限制**: 3 秒/请求
- **覆盖范围**: arXiv 预印本
- **官方 API**: 是

### Semantic Scholar
- **可靠性**: 高
- **速率限制**: 无 Key: 100 请求/5 分钟；有 Key: 1 请求/秒
- **覆盖范围**: 广泛学术论文
- **官方 API**: 是
- **建议**: 申请免费 API Key 提高速率

### Google Scholar
- **可靠性**: 低到中
- **速率限制**: 易被封 IP
- **覆盖范围**: 最广泛
- **官方 API**: 否（非官方爬虫）
- **注意**: 作为可选数据源，失败时不影响其他数据源

### OpenAlex
- **可靠性**: 高
- **速率限制**: 无限制（建议添加邮箱以获得更快响应）
- **覆盖范围**: 2 亿+ 学术文献，正在取代 Google Scholar
- **官方 API**: 是
- **特点**: 完全免费、开放、覆盖广

### IEEE Xplore
- **可靠性**: 高
- **速率限制**: 取决于 API Key 类型
- **覆盖范围**: 工程技术领域权威文献
- **官方 API**: 是
- **特点**: 工程、电子、计算机领域最权威的数据源之一
- **注意**: 需要申请 API Key (https://developer.ieee.org/)

### Crossref
- **可靠性**: ⭐⭐⭐⭐⭐
- **速率限制**: 无硬性限制（建议加邮箱进入 Polite Pool）
- **覆盖范围**: 1.3 亿+ 学术文献，DOI 权威来源
- **官方 API**: 是
- **特点**: 元数据最权威，所有正规期刊都有 DOI
- **注意**: 无需 API Key，免费使用

### CORE
- **可靠性**: ⭐⭐⭐⭐⭐
- **速率限制**: 免费 tier 每月 10,000 tokens
- **覆盖范围**: 3 亿+ 学术论文，开放获取全文聚合
- **官方 API**: 是
- **特点**: 真正返回 **PDF 下载链接**，开放获取判断极准
- **注意**: 需要免费注册获取 API Key (https://core.ac.uk/services/apis/)

## 推荐组合

| 场景 | 推荐数据源 |
|------|-----------|
| **日常使用（零配置）** | `arxiv, openalex, crossref` |
| **需要 PDF 下载** | `arxiv, openalex, crossref, core`（CORE 免费 Key） |
| **工程领域** | 加上 `ieee_xplore`（需 Key） |
| **引用数据补充** | 加上 `semantic_scholar`（建议申请 Key） |

## 项目结构

```
article-name-crawl/
├── research_interests.yaml    # 配置文件
├── README.md                  # 项目说明
├── requirements.txt           # Python 依赖
├── main.py                    # CLI 入口
├── config/
│   ├── __init__.py
│   └── loader.py              # 配置加载 + 验证
├── crawlers/
│   ├── __init__.py
│   ├── base.py                # 爬虫基类（含重试机制 + 多轮搜索模板）
│   ├── arxiv_crawler.py       # arXiv 爬虫
│   ├── semantic_scholar.py    # Semantic Scholar 爬虫
│   ├── google_scholar.py      # Google Scholar 爬虫
│   ├── openalex_crawler.py    # OpenAlex 爬虫
│   ├── ieee_xplore_crawler.py # IEEE Xplore 爬虫
│   ├── crossref_crawler.py    # Crossref 爬虫（DOI 权威）
│   └── core_crawler.py        # CORE 爬虫（PDF 下载链接）
├── models/
│   ├── __init__.py
│   └── paper.py               # 论文数据模型
├── storage/
│   ├── __init__.py
│   └── markdown_writer.py     # Markdown 输出 + 索引生成
├── tests/                     # 单元测试（94 个测试用例）
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_crawlers.py       # 爬虫实例化/解析/分批模板/重试
│   ├── test_dedup.py
│   ├── test_filter.py
│   ├── test_history.py
│   └── test_paper_model.py
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

## 常见问题

### Q: Google Scholar 被封 IP 怎么办？

A: Google Scholar 是可选数据源，可以：
1. 只使用 arXiv 和 Semantic Scholar：`--sources arxiv,semantic_scholar`
2. 配置代理（需要修改代码）

### Q: 如何提高 Semantic Scholar 的速率限制？

A: 申请免费 API Key：
1. 访问 https://www.semanticscholar.org/product/api#api-key
2. 填写申请表单
3. 将获得的 Key 填入配置文件的 `semantic_scholar_api_key` 字段

### Q: 如何添加新的研究领域？

A: 编辑 `research_interests.yaml`，在 `research_domains` 下添加新的领域配置。也可以先用 `--init` 生成默认配置作为参考。

```yaml
research_domains:
  现有关键词
  FMCW Laser Ranging:
    keywords: [...]

  # 新领域
  Lidar:
    keywords:
      - lidar
      - time-of-flight
      - 3D imaging
    arxiv_categories:
      - physics.optics
    priority: 3
```

运行 `python main.py` 自动处理所有领域。

### Q: 生成默认配置？

A: 运行 `python main.py --init` 生成带中文注释的 `research_interests.yaml`，包含所有配置项的说明。

### Q: 如何添加新的数据源？

A: 在 `crawlers/` 目录下创建新的爬虫类，继承 `BaseCrawler` 并实现 `search` 方法。

### Q: 如何获取 IEEE Xplore API Key？

A: 访问 https://developer.ieee.org/ 注册账号并申请 API Key。

### Q: OpenAlex 需要 API Key 吗？

A: 不需要，OpenAlex 完全免费。但建议在配置文件中添加邮箱 (`openalex_email`) 以获得更快的响应速度（Polite Pool）。

### Q: 如何只获取高质量论文？

A: 使用质量筛选功能：
```bash
# 只获取引用数 >= 10 的论文
python main.py --min-citations 10

# 只获取 2020 年后的论文
python main.py --year-from 2020

# 在配置文件中设置默认筛选条件
filters:
  min_citations: 5
  year_from: 2020
  require_doi: true
```

### Q: 多次运行会重复爬取相同的论文吗？

A: 默认不会。程序会记录历史爬取记录到 `crawled_papers.json`，自动跳过已爬取的论文。如果需要禁用此功能，使用 `--no-history` 参数。

### Q: 如何清除历史记录重新爬取？

A: 运行 `python main.py --clear-history` 清除历史记录。

### Q: 哪些数据源支持引用数筛选？

A: OpenAlex 和 Semantic Scholar 支持引用数数据。arXiv、Google Scholar 和 IEEE Xplore 不提供引用数，这些数据源的论文引用数默认为 0。

## 许可证

MIT License
