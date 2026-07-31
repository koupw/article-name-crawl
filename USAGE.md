# 使用指南

## 最简方式：Web 界面

不用记命令行，直接在浏览器里操作：

```bash
# 方式 1（最推荐）：双击 web\launch.vbs
#     无 CMD 黑窗弹出，启动后浏览器打开 http://127.0.0.1:8501
#     停止方式：双击 web\stop.vbs
#
# 方式 2：Python 启动器
python web/launch.py
#
# 方式 3：手动启动
streamlit run web/streamlit_app.py
```

然后在浏览器打开 **`http://127.0.0.1:8501/`**，即可：
- 下拉选择研究领域
- 勾选数据源（推荐 arXiv + OpenAlex）
- 滑块调整引用数、年份
- 实时看进度 → 表格看结果 → 按钮下载 Markdown

> **Windows 连接问题？** 确保用 `web\launch.vbs` 双击启动（已配置好 127.0.0.1 绑定和 telemetry 禁用），
> 然后在**外部浏览器**（Chrome/Edge）手动输入 `http://127.0.0.1:8501/`，不要用 IDE 内嵌浏览器。

---

## CLI 快速开始

如果你习惯命令行，或需要脚本化/定时任务：

```bash
# 进入项目目录
cd article-name-crawl

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

爬取结果输出到 `papers/_output/`，深度分析结果输出到 `papers/analysis/{slug}/`：

```
papers/
├── _output/                                # 爬取结果
│   ├── _index.md                           # 索引（汇总所有列表文件）
│   ├── FMCW_Laser_Ranging_20260629.md      # 论文列表
│   ├── history_index.json                  # 历史索引（跨次去重）
│   └── translation_cache.json              # 翻译缓存（持久化）
└── analysis/                               # 深度分析报告
    └── {slug}/                             # 每篇论文独立目录
        ├── analysis.md                     # 结构化分析报告（含图片引用）
        ├── full.md                         # 原始论文全文 Markdown
        ├── meta.json                       # 元数据/评分/摘要
        └── images/                         # 论文图片
```

## 标题翻译

```bash
# 默认自动翻译（英文 → 中文）
python main.py --sources openalex --max-results 20

# 禁用翻译
python main.py --sources openalex --max-results 20 --no-translate
```

翻译默认使用 Google Translate，无需 API Key。也可在配置文件中切换为百度翻译：

```yaml
translate_backend: baidu
baidu_translate_app_id: '你的 APP ID'      # 或用环境变量 BAIDU_TRANSLATE_APP_ID
baidu_translate_app_key: '你的 Secret Key' # 或用环境变量 BAIDU_TRANSLATE_APP_KEY
```

> 注意：百度翻译免费版限制 1 QPS，使用百度引擎时自动转为单线程串行翻译，速度较慢。

**性能优化**：
- **并发翻译**：默认 5 线程同时翻译，30 篇论文约 5 秒完成
- **翻译持久化**：翻译结果自动缓存到 `history_index.json + translation_cache.json`，下次运行相同论文不再请求翻译

## 配置初始化

```bash
# 生成带注释的默认配置文件
python main.py --init
```

生成 `research_interests.yaml`，包含示例领域、API 配置项、筛选条件的完整中文注释。如果文件已存在则跳过，不会覆盖。

## 常用命令速查

| 需求 | 命令 |
|------|------|
| **默认爬取（最优三角，零配置）** | `python main.py` |
| 快速预览 | `python main.py --dry-run` |
| 含 PDF 下载（需 CORE Key） | `python main.py --sources arxiv,openalex,crossref,core` |
| 全部数据源 | `python main.py --sources arxiv,openalex,crossref,semantic_scholar,ieee_xplore,core` |
| 高质量论文 | `python main.py --min-citations 10` |
| 最新论文 | `python main.py --year-from 2024` |
| 完整爬取 | `python main.py --max-results 100` |
| 多领域爬取 | `python main.py --domain all` |
| 生成默认配置 | `python main.py --init` |
| 清除重爬 | `python main.py --clear-history` |
| 不翻译 | `python main.py --sources openalex --no-translate` |

## 论文深度分析

对单篇论文进行 LLM 驱动的结构化深度分析（MinerU PDF 解析 → LLM 14 章报告）：

```bash
# 分析本地 PDF
python analyze.py pdf "papers/download/report.pdf"

# 通过 arXiv ID 下载并分析
python analyze.py arxiv 2401.12345

# 通过 DOI 下载并分析
python analyze.py doi 10.1000/xyz

# 分析已有 Markdown（跳过 MinerU 解析，省时间）
python analyze.py from-md "papers/parsed/report/report.md"

# 指定 LLM 参数
python analyze.py pdf report.pdf --api-key sk-xxx --model deepseek-chat --language zh

# 仅做 PDF 解析，跳过 LLM 分析（省费用）
python analyze.py pdf report.pdf --skip-analysis

# 强制重新分析（忽略缓存）
python analyze.py pdf report.pdf --force

# 指定输出目录
python analyze.py pdf report.pdf --output ./my_analysis
```

### LLM 配置

在 `research_interests.yaml` 中配置：

```yaml
llm_api_key: ''                          # 或用环境变量 LLM_API_KEY
llm_api_base: 'https://api.deepseek.com/v1'  # 任何 OpenAI 兼容端点
llm_model: 'deepseek-chat'
llm_timeout: 300                         # 推理模型需较长超时
analysis_dir: 'papers/analysis'          # 报告输出目录
```

API Key 优先级：命令行 `--api-key` > 环境变量 `LLM_API_KEY` > 配置文件 `llm_api_key`

### 分析缓存

对同一篇论文的相同 LLM 模型，分析结果自动缓存到 `papers/analysis/_cache/`，避免重复调用 LLM 产生费用。使用 `--force` 可跳过缓存。

## 数据源选择

| 数据源 | 特点 | 推荐场景 |
|--------|------|----------|
| `arxiv` | 免费、稳定、预印本 | 获取最新研究 |
| `openalex` | 免费、有引用数、覆盖广 | 日常使用首选 |
| `crossref` | 免费、DOI 权威、1.3亿+文献 | 最稳三角之一，元数据最准 |
| `core` | 免费 Key、真正 PDF 下载链接 | 需要下载 PDF 时必选 |
| `semantic_scholar` | 有引用数、需 API Key | 补充引用数据 |
| `ieee_xplore` | 工程技术权威 | 工程领域研究 |
| `google_scholar` | 覆盖最广、不稳定 | 不推荐 |

## 质量筛选说明

| 筛选条件 | 说明 | 支持的数据源 |
|----------|------|--------------|
| `min_citations` | 最低引用数 | OpenAlex, Semantic Scholar, Crossref, CORE |
| `year_from` | 起始年份 | 所有数据源 |
| `year_to` | 结束年份 | 所有数据源 |
| `require_doi` | 必须有 DOI | 所有数据源 |
| `open_access_only` | 只要开放获取 | OpenAlex, CORE |

## 去重机制

### 单次去重（自动）
- DOI 相同 → 重复
- arXiv ID 相同 → 重复
- 标题相似度 > 85% → 重复

### 跨次去重（默认开启）
- 记录历史爬取到 `history_index.json + translation_cache.json`
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

不会。翻译结果会自动缓存到 `history_index.json + translation_cache.json`，下次运行相同论文直接从缓存恢复，不发起翻译请求。

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
├── README.md                  # 项目说明
├── USAGE.md                   # 使用指南（本文件）
├── requirements.txt           # Python 依赖
├── main.py                    # CLI 入口（爬取）
├── analyze.py                 # CLI 入口（论文深度分析）
├── config/                    # 配置模块
│   ├── __init__.py
│   └── loader.py              # 配置加载 + 验证
├── crawlers/                  # 爬虫模块（7 个数据源）
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
│   ├── markdown_writer.py     # Markdown 输出 + 索引生成
│   ├── history_manager.py     # 历史记录管理（索引 + 翻译缓存）
│   └── report_writer.py       # 分析报告写入（含图片注入）
├── tests/                     # 单元测试
│   ├── conftest.py            # 测试夹具与工厂函数
│   ├── test_config.py         # 配置验证测试
│   ├── test_crawlers.py       # 爬虫测试
│   ├── test_dedup.py          # 去重逻辑测试
│   ├── test_filter.py         # 质量筛选测试
│   ├── test_history.py        # 历史记录测试
│   ├── test_llm_analyzer.py   # LLM 分析引擎测试
│   ├── test_paper_model.py    # 数据模型测试
│   ├── test_report_writer.py  # 报告写入测试
│   ├── test_analyze_utils.py  # 分析工具函数测试
│   └── test_main_web.py       # Web/主流程集成测试
├── utils/
│   ├── __init__.py
│   ├── llm_analyzer.py        # LLM 深度分析引擎（Map-Reduce + 评分）
│   ├── cache_manager.py       # 分析缓存管理（避免重复调用 LLM）
│   ├── mineru_parser.py       # MinerU PDF 解析封装
│   ├── pdf_downloader.py      # arXiv/DOI/URL PDF 下载
│   ├── dedup.py               # 去重逻辑
│   ├── filter.py              # 质量筛选
│   ├── history.py             # 历史记录 CLI 接口
│   ├── logger.py              # 日志配置
│   ├── paper_translator.py    # 并发翻译
│   ├── retry.py               # 统一重试机制（指数退避）
│   └── translator.py          # 翻译引擎（Google Translate）
├── web/                       # Streamlit Web 界面
│   ├── streamlit_app.py       # 主页面（爬取 + 分析）
│   ├── pages/analysis.py      # 子页面（深度分析）
│   ├── launch.py              # Web 启动器
│   ├── launch.vbs             # Windows 一键启动
│   ├── launch.ps1             # PowerShell 启动脚本
│   ├── stop.vbs               # Windows 停止脚本
│   └── stop.ps1               # PowerShell 停止脚本
└── papers/                    # 输出目录（git 忽略）
    ├── _output/               # 爬取结果
    └── analysis/              # 深度分析报告
```
