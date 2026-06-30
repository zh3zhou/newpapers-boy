# 📰 会打岔的学术速递

每天一份，自动筛论文、生成语音播报，并把 Markdown + MP3 发到你的邮箱。

这是一个明显偏 **agent-first** 的项目：你可以把它当成个人学术编辑部，也可以直接让你的 agent 读取 `AGENTS.md`、`config.md` 和相关脚本，自行完成采集、生成、播报和推送。学术内容之外，它还会插播一点艺术和轻松内容，让信息流不那么板着脸。

## 定位

- 面向研究者、技术爱好者和喜欢自动化工作流的人
- 用 agent 负责采集与整理，用脚本负责 TTS 和邮件推送
- 输出既可读，也可听，适合通勤、散步或低注意力场景

## 亮点

- 🎯 **多领域并行采集**：arXiv / GitHub Trending / HuggingFace / Papers with Code，按你配置的领域并行检索
- 🤖 **Agent 友好工作流**：核心流程写在 `AGENTS.md`，适合直接交给 agent 执行
- 🎙️ **语音播报**：微软 Edge TTS 生成新闻播报风格 MP3，中文女声，语速可调
- 📧 **邮件推送**：Markdown 正文 + MP3 附件发到你邮箱，手机邮箱 App 直接听
- 🎨 **打岔内容**：艺术一刻（摄影/装置/数字艺术）+ 会心一笑（冷知识/段子）
- ⚙️ **零代码定制**：改 `config.md` 就能换领域、调条数；改 `.env` 就能换语音、换邮箱
- 🕐 **可配定时任务**：配合 TRAE Work Schedule 每天自动运行

## 3 步上手

### 环境要求

- Windows（PowerShell）—— 脚本以 `.ps1` 为主，核心 Python 脚本可跨平台
- Python 3.9+
- 一个能收邮件的邮箱（推荐 Gmail）

### 1. 克隆并安装

```powershell
git clone <your-repo-url>
cd <repo-dir>
.\setup.ps1
```

`setup.ps1` 会自动：检测 Python → 创建虚拟环境 `.venv` → 安装依赖 → 复制 `.env.example` 为 `.env`。

### 2. 选择使用方式

你有两种启动姿势：

- **直接手动跑脚本**：自己准备或生成 `data/YYYY-MM-DD_学术速递.md`，再执行后处理
- **直接让你的 agent 处理一切**：让 agent 先读取 `AGENTS.md`、`config.md` 和 `README.md`，再按文档执行完整工作流

如果你要把这个项目交给 agent，推荐它至少先读这几个文件：

- `AGENTS.md`
- `config.md`
- `README.md`
- `scripts/postprocess.ps1`

### 3. 配置邮箱并运行

编辑 `.env` 文件，填写你的邮箱 SMTP 信息：

**Gmail（推荐）**：

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_USER=your-name@gmail.com
SMTP_PASS=你的16位应用专用密码
MAIL_TO=your-name@gmail.com
```

> Gmail 需要先开启「两步验证」，然后创建「应用专用密码」：
> https://myaccount.google.com/security → 安全性 → 两步验证 → 应用专用密码

**QQ 邮箱**：

```env
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=你的QQ号@qq.com
SMTP_PASS=QQ邮箱授权码（非登录密码）
MAIL_TO=你的QQ号@qq.com
```

> QQ 邮箱授权码获取：QQ邮箱网页版 → 设置 → 账户 → IMAP/SMTP服务 → 开启 → 生成授权码

**Outlook/Hotmail**：

```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=your-name@outlook.com
SMTP_PASS=你的密码
MAIL_TO=your-name@outlook.com
```

### 4. 生成当日速递

项目的核心流程是**在 TRAE Work 中让 AI 执行采集**（见下文"完整工作流"），后处理部分（TTS + 邮件推送）可以一键运行：

```powershell
.\scripts\postprocess.ps1              # 处理今天
.\scripts\postprocess.ps1 2026-06-30   # 处理指定日期
```

前提：`data/` 目录下已有 `YYYY-MM-DD_学术速递.md`（由 AI 采集生成）。

也可以分步执行：

```powershell
.\.venv\Scripts\python.exe scripts\tts_generate.py 2026-06-30   # 仅生成 MP3
.\.venv\Scripts\python.exe scripts\push_email.py 2026-06-30     # 仅发邮件
```

## 自定义配置

### 换关注领域

编辑 [config.md](config.md) 第一节的表格，增删行即可。例如添加计算神经科学：

```markdown
| 5 | 计算神经科学 | computational neuroscience / spiking neural networks | 2-3 |
```

领域名可以自由命名，TTS 播报会自动识别，无需改代码。

### 调整每领域论文数量

同样在 [config.md](config.md) 的表格中修改「每日条数」列，例如 `3-5` → `5-8`。

### 换 TTS 语音

编辑 `.env`：

```env
TTS_VOICE=zh-CN-YunxiNeural    # 换男声
TTS_RATE=+10%                  # 略快
```

可选中文语音：

| Voice | 风格 |
|-------|------|
| `zh-CN-XiaoxiaoNeural` | 晓晓，女，自然，默认推荐 |
| `zh-CN-YunxiNeural` | 云希，男，年轻活力 |
| `zh-CN-YunjianNeural` | 云健，男，沉稳新闻腔 |
| `zh-CN-XiaoyiNeural` | 晓伊，女，甜美 |

### 换推送邮箱

编辑 `.env` 的 `SMTP_*` 和 `MAIL_TO` 字段即可。支持任何支持 SMTP 的邮箱服务。

### 启用其他推送通道（可选）

默认只走邮件。如需 Bark（iOS）、Server酱（微信）、飞书 Webhook：

1. 打开 `scripts/push_email.py`
2. 找到底部"可选推送通道"注释区域，取消对应函数的注释
3. 在 `main()` 中取消对应调用行的注释
4. 在 `.env` 中填入对应配置项（见 `.env.example` 注释）

> ⚠️ 注意：微信服务号、Bark、飞书 Webhook 均**不支持 MP3 附件**，只能推送文字摘要。邮件是唯一能在手机上直接收到音频的通道。

## 完整工作流（在 TRAE Work 中执行）

每日速递的完整生成流程是：

1. **初始化**：读取 `config.md`、读取前一日速递做去重参考
2. **并行采集**：针对 config 中的每个领域，AI 通过 WebSearch/WebFetch 检索 arXiv、GitHub Trending 等来源
3. **聚合去重**：跨领域合并、与历史比对去重
4. **链接验证**：确保论文链接可访问
5. **Markdown 生成**：按约定格式写入 `data/YYYY-MM-DD_学术速递.md`
6. **后处理**：运行 `postprocess.ps1` 生成 TTS 音频 + 发送邮件
7. **日志记录**：追加到 `data/runs.log`

在 TRAE Work 中，可以把这个流程配置为每日定时任务（Schedule）。

## 目录结构

```
academic-dispatch/
├── config.md                 # 内容配置（领域/条数/来源/路径）
├── .env.example              # 环境变量模板（提交到Git）
├── .env                      # 你的私有配置（不提交）
├── .gitignore
├── requirements.txt          # Python依赖
├── setup.ps1                 # 一键安装脚本
├── README.md                 # 本文件
├── TECH_REPORT.md            # 技术架构文档（给Agent/开发者）
├── scripts/
│   ├── tts_generate.py       # Markdown → MP3语音播报
│   ├── push_email.py         # SMTP邮件推送（含MP3附件）
│   └── postprocess.ps1       # 一键后处理（TTS+邮件）
├── data/                     # 每日输出（gitignored）
│   ├── .gitkeep
│   ├── YYYY-MM-DD_学术速递.md
│   ├── YYYY-MM-DD_学术播报.mp3
│   └── runs.log
└── archive/                  # 月度归档（gitignored）
    └── .gitkeep
```

## 隐私说明

- `.env` 包含你的邮箱授权码，**永远不要提交到 Git**
- `data/` 目录下的每日速递和音频是你的个人内容，默认不入库
- 提交到 GitHub 的只有代码、配置模板和文档

## 常见问题

**Q: Gmail 发信失败提示"Username and Password not accepted"？**
A: 你填的是 Gmail 登录密码而不是应用专用密码。开启两步验证后重新生成16位应用密码。

**Q: TTS 生成的音频听起来不自然/有些论文被跳过？**
A: 每篇论文摘要会被 `smart_truncate()` 在标点处智能截断到约150字，避免超长。想听到更多内容，编辑 `tts_generate.py` 中 `smart_truncate(summary, 150)` 的 `150` 改为更大数字。

**Q: 想改开场白/结束语？**
A: 编辑 `scripts/tts_generate.py` 的 `build_broadcast_text()` 函数，修改 `sentences.append(...)` 中的句子。

**Q: 如何在 Linux/Mac 上使用？**
A: Python 脚本跨平台，直接用 `python3 scripts/tts_generate.py` 和 `python3 scripts/push_email.py` 即可。`setup.ps1` 和 `postprocess.ps1` 是 Windows PowerShell 脚本，Linux/Mac 用户可自行编写对应的 bash 脚本（核心命令相同）。

## License

MIT
