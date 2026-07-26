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

将 `config.example.json` 复制为 `config.json`，填入你的 Token：

```bash
cd E:\WorkSpace\OpencodeWork\test\mineru-api-client
copy config.example.json config.json
```

编辑 `config.json`：
```json
{
  "token": "你的MinerU API Token"
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

#### 解析本地 PDF（自动上传临时直链）
```bash
python mineru_client.py "C:\Users\we\Desktop\report.pdf"
```
> 文件会被上传到 file.io 获取一次性直链，MinerU 下载后自动失效，14 天后彻底删除。

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
- **本地文件解析**：文件先上传至 file.io 获取一次性临时直链，MinerU 服务器下载后即失效，14 天后自动删除。若文件涉密，建议自行上传到私有 OSS 获取直链后传入 URL 解析。

---

## 常见问题

**Q: 为什么解析本地文件需要先上传？**  
A: 官方 API 当前只接受公网直链 URL，不支持直接上传文件。脚本通过 file.io 临时上传获取直链，这是目前最便捷的方案。

**Q: 上传失败怎么办？**  
A: file.io 对文件大小有限制（约 100MB）。大文件请自行上传到图床/OSS 获取直链后传入 URL。

**Q: 可以解析 DOCX/PPTX/XLSX 吗？**  
A: 当前脚本针对官方 PDF 解析 API 设计。如需解析 Office 文档，建议将文件另存为 PDF 后再调用。
