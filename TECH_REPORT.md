# TECH_REPORT.md — 技术架构文档

> 本文档供 AI Agent / 开发者快速理解项目结构和工作原理，便于二次开发和维护。

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                     AI 采集（TRAE Work 中执行）            │
│  读取 config.md → 并行 WebSearch/WebFetch → 去重/校验    │
│  → 生成 Markdown → 写入 data/YYYY-MM-DD_学术速递.md       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  postprocess.ps1（入口）                  │
│  Step 1: tts_generate.py → data/YYYY-MM-DD_学术播报.mp3  │
│  Step 2: push_email.py  → SMTP 邮件（正文+MP3附件）        │
└─────────────────────────────────────────────────────────┘
```

核心模块：
- **内容生成**：不在本仓库代码中，由 TRAE Work 中的 AI Agent 根据 `config.md` 配置执行采集。Markdown 输出格式是 TTS 解析的契约。
- **TTS 语音合成**：[scripts/tts_generate.py](scripts/tts_generate.py)
- **邮件推送**：[scripts/push_email.py](scripts/push_email.py)
- **一键后处理**：[scripts/postprocess.ps1](scripts/postprocess.ps1)

## 2. 配置体系

项目采用**双配置文件分离**设计：

| 文件 | 用途 | 是否入库 | 修改者 |
|------|------|---------|--------|
| [config.md](config.md) | 内容配置：关注领域、条数、来源、路径、语音参数、TTS结构 | ✅ 入库 | 用户（决定采什么内容） |
| `.env` | 密钥/环境配置：SMTP密码、TTS语音选择、可选通道key | ❌ 不入库 | 用户（决定怎么发/发给谁） |
| `.env.example` | `.env` 的模板，含注释说明 | ✅ 入库 | 开发者 |

**设计原则**：
- `config.md` 是 Markdown 格式，人类可读，AI Agent 也能直接 Read 获取采集指令
- `.env` 是 KEY=VALUE 格式，适合 Python `os.environ` 或自定义 loader 读取
- 任何可能泄露隐私的字段（密码、key、邮箱地址）只放 `.env`

## 3. 核心模块详解

### 3.1 scripts/tts_generate.py

**职责**：将 Markdown 格式的学术速递转换为新闻播报风格 MP3。

#### 常量与路径
```python
WORK_DIR = Path(__file__).resolve().parent.parent  # 项目根目录
DATA_DIR = WORK_DIR / "data"                        # 输出目录
```
- 所有路径通过 `__file__` 相对推导，**不依赖绝对路径**，克隆到任意目录都能运行
- `ensure_data_dir()` 在运行时确保 data/ 存在

#### 配置加载：`load_env()`
简单的 KEY=VALUE 解析器，跳过空行和注释行，自动去除值两侧的引号。

#### 文本清理：`clean_text(s)`
用正则去除 Markdown 标记：
- `[text](url)` → `text`
- 去除 `*_`\`#> 等格式符号
- 去除 http(s) URL
- 合并空白

#### 智能截断：`smart_truncate(text, max_len)`
**核心算法**：在标点处截断，避免在句子中间硬切。

优先级：
1. 如果文本 ≤ max_len，补句号后直接返回
2. 在 40%~100% 范围内，从后往前找中文句末标点（。！？）
3. 再找英文句末标点（排除小数点：前一字符是数字的 `.` 不算）
4. 再找中文分句标点（；，、），截断后补句号
5. 再找英文分号逗号
6. 兜底：max_len-1 处截断并补句号

#### 关键词匹配（泛化设计）
```python
DIVERSION_KEYWORDS = ("打岔", "休闲", "轻松一刻", "diversion")
ART_KEYWORDS = ("艺术", "摄影", "art")
HUMOR_KEYWORDS = ("笑", "幽默", "趣味", "冷知识", "趣闻", "段子", "humor")
```
通过关键词模糊匹配识别板块类型，而非硬编码板块名称。用户在 config.md 中修改领域名后，只要 Markdown 格式一致，解析就能正确工作。

#### Markdown 解析：`parse_markdown(md_text)` → dict
**状态机解析器**，逐行扫描，模式（mode）在以下状态间切换：
- `None`（初始/打岔标题层）
- `"academic"`（学术板块内）
- `"art"`（艺术板块内）
- `"humor"`（趣味板块内）

状态转换规则：
| 当前模式 | 遇到 | 新模式 |
|---------|------|--------|
| None | `## xxx`（含打岔关键词） | None（进入打岔模式in_diversion=True） |
| None | `## xxx`（不含打岔关键词） | academic（新建section） |
| academic/art/humor | `## xxx` | 同上（flush 当前section后切换） |
| in_diversion | `### xxx`（含艺术关键词） | art |
| in_diversion | `### xxx`（含幽默关键词） | humor |

学术条目识别：`^[-*]\s+\*\*` 开头的行（粗体列表项），紧随其后的缩进行（2空格或tab开头）作为详情，从中提取"摘要"和"为什么值得看"。

返回结构：
```python
{
    "date": "2026-06-30",
    "intro": "开头引用语",
    "sections": [
        {"title": "复杂系统", "items": [{"summary": "...", "why": "..."}]},
        ...
    ],
    "arts": [{"title": "...", "intro": "..."}],
    "humors": ["趣味文本1", "趣味文本2"]
}
```

#### 播报词构建：`build_broadcast_text(parsed)` → str
将解析结果拼装为新闻播报风格的中文朗读文本。特点：
- 开场白包含日期（中文格式）
- 板块过渡语自动生成（"首先来看XX"、"接下来是XX"、"最后来看XX"）
- 论文按编号朗读，每篇摘要经 smart_truncate 截断到150字
- 艺术条目截断到90字，趣味条目截断到130字
- 结束语固定
- 句子之间用 `\n` 分隔，edge-tts 会在换行处自然停顿

#### 语音合成：`synthesize(text, output_path, voice, rate)`
异步调用 `edge_tts.Communicate` 生成 MP3。

### 3.2 scripts/push_email.py

**职责**：构造 MIME 多段邮件，通过 SMTP 发送，Markdown 转为 HTML 正文，MP3 作为附件。

#### Markdown → HTML 转换：`_md_to_html(text)` / `_inline_md(text)`
轻量级转换器（不依赖 markdown 库）：
- `# ` → `<h2>`（邮件中用 h2 而非 h1 更协调）
- `## ` → `<h3>`，自动去除中文编号前缀（"一、"、"二、"）
- `### ` → `<h4>`
- `>` 引用块 → `<blockquote>` 带蓝色左边框
- `- / *` 列表 → `<ul><li>`
- `**bold**` → `<strong>`
- `` `code` `` → `<code>`
- `[text](url)` → `<a>`
- `---` → `<hr>`
- 其他段落 → `<p>`

内联样式使用 inline CSS（邮件客户端兼容性好）。

#### 邮件发送：`push_email(env, title, body_summary, md_path, mp3_path)`
- 使用 `MIMEMultipart` 构造多段邮件
- 正文为 HTML 格式（蓝色渐变标题头 + 转换后的Markdown正文）
- MP3 以 `MIMEApplication` 方式附加，`Content-Disposition: attachment`
- 自动选择 SSL（port=465）或 STARTTLS（其他端口）
- 超时30秒

#### 可选通道（注释保留）
Bark、Server酱、飞书 Webhook 的实现代码以注释形式保留在文件中，取消注释即可启用。代码已写好，用户只需：
1. 取消函数注释
2. 在 `main()` 中取消对应调用行注释
3. `.env` 填入对应key

### 3.3 scripts/postprocess.ps1

**职责**：PowerShell 入口，串联 TTS 和推送。

流程：
1. 参数解析（`-Date`，默认今天）
2. 路径推导（`$WorkDir = Split-Path -Parent $PSScriptRoot`）
3. 检查 `.venv` 是否存在，不存在则提示运行 `setup.ps1`
4. 检查 `data/` 目录和 Markdown 文件是否存在
5. 调用 `tts_generate.py`，检查退出码
6. 调用 `push_email.py`，失败仅警告（因为音频已生成）
7. 打印结果

### 3.4 setup.ps1

**职责**：一键环境初始化。
1. 检测 Python（默认 `py` 命令，可通过 `-PythonCmd` 覆盖）
2. 创建 `.venv` 虚拟环境（如不存在）
3. `pip install -r requirements.txt`
4. 复制 `.env.example` → `.env`（如 `.env` 不存在）
5. 打印下一步指引

## 4. Markdown 输出格式约定（生成端 ↔ 解析端契约）

AI 采集生成的 Markdown **必须**遵循以下格式，否则 TTS 解析会失败（会 fallback 到朗读前3000字纯文本）：

```markdown
# 会打岔的学术速递 — YYYY-MM-DD

> 开头一句话总览/引言（引用块，可选）

## 一、领域名称A

- **论文标题** — arXiv:ID（分类，日期）
  摘要：一句话摘要。
  为什么值得看：一句话理由。
  链接：https://arxiv.org/abs/XXXX.XXXXX

- **第二篇论文** ...
  摘要：...
  为什么值得看：...
  链接：...

## 二、领域名称B

（同上格式）

## 五、今日打岔（或含"打岔"关键词的任意二级标题）

### 艺术一刻（或含"艺术"/"摄影"关键词的三级标题）

- **艺术作品名称** — 来源（日期）
  简介：一句话介绍。
  链接：https://...

### 会心一笑（或含"笑"/"幽默"/"趣味"/"冷知识"关键词的三级标题）

- 趣味内容文本。
- 另一条趣味内容。
```

**关键约定**：
- 一级标题（`#`）包含日期（正则 `(\d{4}-\d{2}-\d{2})`）
- 学术板块用 `##` 二级标题，板块名称自由
- 打岔板块的 `##` 标题必须包含"打岔"等关键词
- 打岔下的子板块用 `###` 三级标题
- 学术/艺术条目以 `- **标题**` 开头，后续缩进行为详情
- 幽默条目以 `- ` 开头（无粗体），内容在同一行或后续缩进行

## 5. 数据流

```
config.md (内容配置)
    ↓ AI Agent 读取
WebSearch / WebFetch (arXiv, GitHub, HF, PapersWithCode)
    ↓ 采集/去重/校验
data/YYYY-MM-DD_学术速递.md (Markdown)
    ↓ tts_generate.py 解析+合成
data/YYYY-MM-DD_学术播报.mp3 (音频)
data/YYYY-MM-DD_播报稿.txt (朗读文本，调试用)
    ↓ push_email.py 组装MIME邮件
SMTP服务器 (Gmail/QQ/Outlook)
    ↓
收件人邮箱 → 手机邮箱App（查看正文+收听MP3）
```

日志写入：`data/runs.log`（制表符分隔，日期、时间、条数、链接数等）。

## 6. 扩展点

### 添加新推送通道
1. 在 `push_email.py` 中添加 `push_xxx(config, title, body, md_path, mp3_path) -> bool` 函数
2. 在 `main()` 中调用，遵循"返回 False 继续尝试下一个通道"模式
3. 在 `.env.example` 中添加对应配置项注释
4. 在 `config.md` 推送配置表格中添加行

### 添加新 TTS 引擎
1. 新建 `scripts/tts_xxx.py`（替换 edge-tts），保持与 `tts_generate.py` 相同的 CLI 接口（`python tts_xxx.py [date]`）
2. 或在 `tts_generate.py` 中抽象出 `synthesize()` 函数，根据 env 选择引擎
3. 更新 `requirements.txt`
4. 更新 `config.md` 音频配置段

### 自定义播报风格
修改 `build_broadcast_text()` 中的 sentences 列表。常用调整：
- 开场白/结束语：直接修改字符串
- 板块过渡语：修改 `_section_intro()` 函数
- 摘要长度：修改 `smart_truncate(summary, 150)` 中的 `150`
- 艺术/趣味长度：修改对应的 `90`/`130` 数字

### 添加新的打岔子板块
在 Markdown 中使用新的 `###` 标题，在 `tts_generate.py` 的 `HUMOR_KEYWORDS` 或新建关键词元组中添加识别词，在 `parse_markdown()` 中添加对应 mode 处理。

## 7. 常见修改场景速查

| 需求 | 修改文件 | 修改位置 |
|------|---------|---------|
| 换关注领域 | `config.md` | 第一节表格增删行 |
| 调论文数量 | `config.md` | 第一节表格「每日条数」列 |
| 换TTS语音 | `.env` | `TTS_VOICE` |
| 换TTS语速 | `.env` | `TTS_RATE` |
| 换邮箱 | `.env` | `SMTP_HOST/USER/PASS/MAIL_TO` |
| 改开场白/结束语 | `scripts/tts_generate.py` | `build_broadcast_text()` 中 sentences |
| 改摘要朗读长度 | `scripts/tts_generate.py` | `smart_truncate(summary, 150)` 的 150 |
| 启用微信推送 | `scripts/push_email.py` | 取消 Server酱 相关代码注释 |
| 启用Bark/飞书 | `scripts/push_email.py` | 取消对应函数注释 + main()中调用 |
| 改邮件样式 | `scripts/push_email.py` | `push_email()` 中 body_html 的 CSS |
| 添加新推送通道 | `scripts/push_email.py` | 新增函数 + main()调用 + .env.example |

## 8. 定时任务（Schedule）配置说明

项目配合 TRAE Work 的 Schedule 功能实现每日自动化。典型配置：

- **执行时间**：每天早上 7:00（可自定义）
- **任务内容**：AI Agent 按照工作流（初始化→并行采集→去重→校验→生成Markdown→运行postprocess.ps1）执行
- **工作目录**：项目根目录
- **config.md** 中的「任务续期提醒」段记录过期日，到期前 Agent 应提醒用户续期

## 9. 测试建议

- **TTS 解析测试**：对已有 `data/` 下的 Markdown 运行 `tts_generate.py`，观察输出的板块数、论文数、艺术/趣味数是否与预期一致
- **邮件发送测试**：填好 `.env` 后对指定日期运行 `push_email.py`，检查邮箱是否收到 HTML 正文和 MP3 附件
- **路径测试**：将项目克隆到不同深度的目录，确认脚本能正确找到 `data/` 和 `.env`

## 10. 依赖清单

**生产依赖**（`requirements.txt`）：
- `edge-tts>=7.0`：微软 Edge TTS 在线服务的 Python 封装，免费、无需 API key

**标准库依赖**（无需安装）：
- `asyncio`：异步 I/O（edge-tts 异步 API）
- `smtplib` / `email`：SMTP 邮件发送
- `urllib.request`：HTTP 请求（可选通道使用）
- `re` / `pathlib` / `json` / `datetime`：基础工具
