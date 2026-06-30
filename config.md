# 会打岔的学术速递 — 配置文件

> 本文件是速递工作流的内容配置源。修改此文件即可调整每日速递的关注领域、内容数量等，无需改动代码。
> 任务 prompt 开头会 Read 本文件；若读取失败则回退到 prompt 内默认配置并在日志标注 `config_missing`。

## 一、学术领域（每个领域独立采集，可自由增删改）

> 在表格中增删行即可更换关注领域。领域名称会直接作为 Markdown 二级标题（##），TTS 解析器会自动识别。
> 「关键词范围」供采集时的 WebSearch 使用；「每日条数」是该领域预期的论文数量。

| 编号 | 领域 | 关键词范围 | 每日条数 |
| --- | --- | --- | --- |
| 1 | 复杂系统 | complex systems / 网络 / 涌现 / 多智能体动力学 | 3-5 |
| 2 | AI4S / S4AI | AI for Science / Science for AI | 3-5 |
| 3 | AI 基础与大模型 | foundation models / 训练 / 推理优化 / 评测 / 对齐 | 3-5 |
| 4 | Agent / harness 工程 | agent 框架 / 工具调用 / 评测 harness / 工程实践 | 3-5 |

**添加新领域示例**：在表格末尾加一行即可，如 `5 | 计算神经科学 | computational neuroscience /  spiking neural networks | 2-3`。

## 二、学术来源（按优先级从上到下）

- arXiv（近期新论文）
- GitHub Trending
- Hugging Face（papers / models）
- Papers with Code
- 广域 WebSearch 补充（博客 / 技术报告 / 开源项目发布）

## 三、打岔内容

> 打岔不局限于学术相关，鼓励跨领域趣味内容——生活趣事、冷知识、奇闻、互联网梗、好书好片推荐、自然奇观等皆可。

- 艺术一刻：每日 2-3 条，方向在下方「艺术方向偏好」中配置
- 会心一笑：每日 1-2 条，轻松幽默 / 冷知识 / 段子 / 有趣发现 / 生活趣事（合规、不低俗、不涉及敏感话题），不强求链接

### 艺术方向偏好（首次配置向导中由用户指定，可随时修改）

当前偏好方向：艺术摄影、数字艺术、行为艺术、当代装置、插画

> 修改此段即可更换艺术推荐方向，例如改为：建筑、雕塑、动画、国画、书法、电影海报设计、陶瓷艺术、街头涂鸦等。

## 四、时效窗口

- 默认窗口：近 24 小时
- 降级窗口：若某领域 24h 内不足 3 条，可放宽到近 48 小时补足，并在条目标题后标注 `(48h)`
- 艺术 / 幽默 / 打岔：可放宽到「近期」以保证质量与趣味性

## 五、文件路径约定

> 所有路径均相对于项目根目录（脚本通过 `Path(__file__).resolve().parent.parent` 自动推导工作目录）。

- 项目根目录：脚本自动定位，无需配置
- 当日速递 Markdown：`data/YYYY-MM-DD_学术速递.md`
- 当日速递音频：`data/YYYY-MM-DD_学术播报.mp3`
- 当日朗读稿：`data/YYYY-MM-DD_播报稿.txt`
- 运行日志：`data/runs.log`
- 月度归档目录：`archive/YYYY-MM/`
- Python 虚拟环境：`.venv/`（edge-tts 等依赖安装于此）
- 后处理脚本目录：`scripts/`
  - `tts_generate.py`：将当日 Markdown 转为新闻播报式 MP3
  - `push_email.py`：将速递内容 + MP3 附件通过邮件发送
  - `postprocess.ps1`：PowerShell 一键入口（TTS + 推送）

## 六、语言

- 中文为主
- 论文标题 / 专有名词 / 项目名保留英文原文
- 语音播报语言：中文（默认女声 `zh-CN-XiaoxiaoNeural`，语速适中偏新闻播报风格）

## 七、推送配置

> 默认推送通道为邮件（SMTP），支持 MP3 附件。邮件配置在 `.env` 文件中，详见 `.env.example`。

| 通道 | 说明 | MP3 附件 | 配置方式 |
| --- | --- | --- | --- |
| **邮件（默认推荐）** | SMTP 邮件，可发送到 Gmail/QQ/Outlook 等任意邮箱，手机邮箱 App 直接接收 | ✅ 是 | 编辑 `.env` 填写 `SMTP_HOST/SMTP_USER/SMTP_PASS/MAIL_TO` |
| Bark（iOS） | iOS 推送神器，App Store 免费下载 | ❌ 否 | 在 `push_email.py` 中取消注释相关代码，`.env` 填 `BARK_URL` |
| Server酱（微信） | 微信服务号推送 | ❌ 否 | 同上，`.env` 填 `SERVERCHAN_KEY` |
| 飞书 Webhook | 飞书群机器人推送 | ❌ 否 | 同上，`.env` 填 `FEISHU_WEBHOOK` |

- 邮件为默认通道，安装 setup 后只需配置 `.env` 即可使用；
- 其他通道代码在 `push_email.py` 中以注释形式保留，取消注释即可启用。

## 八、音频播报配置

- TTS 引擎：edge-tts（微软 Edge 在线 TTS，免费、高质量中文语音）
- 默认语音：`zh-CN-XiaoxiaoNeural`（晓晓，自然女声，适合新闻播报）
- 备选语音：`zh-CN-YunxiNeural`（云希，男声）、`zh-CN-YunjianNeural`（云健，沉稳男声）、`zh-CN-XiaoyiNeural`（晓伊，甜美）
- 语速：通过 `.env` 的 `TTS_RATE` 调整（`+0%` 默认，`+10%` 加快，`-10%` 减慢）
- 输出格式：MP3
- 播报结构（新闻播报风格）：
  1. 开场白：「会打岔的学术速递，YYYY 年 M 月 D 日。」
  2. 按领域播报：每个领域一段引言 + 每篇论文的一句话摘要
  3. 今日打岔：艺术一刻精选 + 会心一笑
  4. 结束语：「以上就是今天的学术速递，祝你今天也有好的灵感。」

## 九、自定义指南速查

| 想改什么 | 改哪个文件 | 怎么改 |
| --- | --- | --- |
| 关注领域 | `config.md` 第一节表格 | 增删表格行，领域名自由命名 |
| 每个领域论文数 | `config.md` 第一节表格 | 修改「每日条数」列（如 3-5 → 5-8） |
| 艺术/打岔条数 | `config.md` 第三节 | 直接改数字 |
| TTS 语音 | `.env` | 修改 `TTS_VOICE`（可选值见上方列表） |
| TTS 语速 | `.env` | 修改 `TTS_RATE`（如 `+10%`） |
| 推送邮箱 | `.env` | 修改 `SMTP_USER`、`SMTP_PASS`、`MAIL_TO` |
| 播报开场白/结束语 | `scripts/tts_generate.py` | 修改 `build_broadcast_text()` 中的句子 |
| 摘要截断长度 | `scripts/tts_generate.py` | 修改 `smart_truncate()` 调用中的数字参数 |

## 十、任务续期提醒

- Schedule 任务过期日：`2026-12-25`
- 提醒阈值：`2026-12-01` 起，每日会话推送末尾追加一行提醒
  「⚠️ 任务将于 2026-12-25 过期，请用 Schedule action: update 续期。」
