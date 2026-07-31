# MinerU 官方 API 便捷客户端

无需安装 `mineru` 包，一个 Python 脚本即可调用 [mineru.net](https://mineru.net) 官方 API 解析 PDF。

---

## 环境要求

- **Python 3.8+**
- **requests**（唯一外部依赖）

```bash
pip install requests
```

---

## 快速开始

### 1. 配置 API Token（三选一）

**方式 A：配置文件（推荐，最方便）**

将 `.env` 或 `config.example.json` 复制为 `config.json`，填入你的 Token：

```bash
# 方式 1: 在项目根目录创建 .env 文件，设置 MINERU_TOKEN
cd article-name-crawl
echo MINERU_TOKEN=你的Token >> .env

# 方式 2: 在 mineru-api-client 目录下复制配置模板
cd mineru-api-client
copy config.example.json config.json
```

编辑 `config.json`：
```json
{
  "token": "你的MinerU API Token",
  "model": "vlm",
  "base_url": "https://mineru.net/api/v4"
}
```

**方式 B：环境变量**

```powershell
# PowerShell（当前会话）
$env:MINERU_TOKEN="your_token_here"

# CMD（当前会话）
set MINERU_TOKEN=your_token_here
```

**永久设置：** 系统属性 → 环境变量 → 用户变量 → 新建 `MINERU_TOKEN`

**方式 C：命令行参数**

每次执行时传入：
```bash
python mineru_client.py report.pdf --token "your_token_here"
```

---

### 2. 使用示例

#### 解析公网 PDF（已有直链）
```bash
python mineru_client.py "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"
```

#### 解析本地 PDF（MinerU v4 原生直传）
```bash
python mineru_client.py paper.pdf
```
> 文件通过 MinerU 预签名 URL 直传到 OSS，解析完成后自动下载结果。

#### 使用 pipeline 模型（速度更快）
```bash
python mineru_client.py report.pdf --model pipeline -o report.md
```

#### 同时保存完整 JSON 结果
```bash
python mineru_client.py report.md --json
```

#### 自动化脚本（跳过上传确认提示）
```bash
python mineru_client.py report.pdf --yes -o report.md
```

---

## 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `input` | PDF 公网 URL 或本地文件路径 | `"https://.../a.pdf"` 或 `"report.pdf"` |
| `--model` | 解析模型版本：`vlm`(高精度) / `pipeline`(速度快) | `--model pipeline` |
| `-o, --output` | 输出 Markdown 文件路径（默认打印到终端） | `-o output.md` |
| `--json` | 同时保存完整 API 返回的 JSON | `--json` |
| `--token` | API Token（优先级最高） | `--token xxx` |
| `--yes` | 上传本地文件时不弹出确认提示 | `--yes` |

### Token 优先级

脚本按以下顺序查找 Token，一旦找到即停止：

1. `--token` 命令行参数
2. `config.json` 文件中的 `"token"` 字段
3. `MINERU_TOKEN` 环境变量

---

## 模型选择建议

| 模型 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| `vlm` | 精度最高(95.39)，支持扫描件/手写/复杂排版 | 速度较慢，API 调用成本略高 | 扫描版 PDF、学术论文、复杂图文混排 |
| `pipeline` | 速度快(快 35~220%)，成本低 | 精度稍低(86.47)，纯文本为主 | 普通电子 PDF、批量处理、日常文档 |

---

## 隐私说明

- **公网 URL 解析**：PDF 由 MinerU 官方服务器直接下载并解析。
- **本地文件解析**：文件通过 MinerU 预签名 URL 直传到官方 OSS 存储，解析完成后自动清理。全程不经过第三方服务。

---

## 常见问题

**Q: 支持哪些文件格式？**  
A: 当前仅支持 PDF 解析。如需解析 Office 文档，建议先转为 PDF。
