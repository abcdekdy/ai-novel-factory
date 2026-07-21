# AI 小说工厂

AI 小说工厂是一款基于 PyQt6 的桌面小说生成工具。输入一个创作灵感后，应用会依次构建世界观、细化章节大纲、生成正文、进行质量评估与修订，并保存为可继续创作的项目。

## 灵感来源

本项目的灵感来源于美团 LongCat 官方演示。开发过程完全由 Claude（Anthropic 的 AI 助手）执行，包括需求分析、架构设计、代码编写、测试和迭代优化。这是一次"AI 全程驱动软件开发"的实践探索。

### 开发历程

**第一阶段：核心流水线搭建**
- 设计 7 Agent 协作架构：世界观构建 → 大纲生成 → 章节并行生成 → 质量评估 → 回流修订 → 多平台适配 → 续写大纲
- 实现基于 Semaphore 的多线程章节并行生成
- 建立项目持久化体系（world_view / outline / summary / chapters）

**第二阶段：质量体系强化**
- 新增程序化规则校验器（rule_checker）：字数、禁用句式、章尾钩子、关键事件覆盖、出场人物
- 改造质量评估为"硬校验 + LLM 主观打分"双层体系
- 重构修订 Agent 为 JSON patch 协议（锚点 + 替换），避免全量重写导致的 token 浪费和风格漂移

**第三阶段：人机协作体验**
- 新增世界观审查检查点（HITL）：生成世界观后弹出对话框让用户编辑确认
- 预览页支持手动编辑章节正文并保存，标记 manually_edited 跳过 AI 修订
- 设置页重构为滚动布局，适配各种窗口高度

**第四阶段：续写与长期记忆**
- 实现时间线快照机制：追踪角色状态变化、未回收伏笔、未闭合人物弧
- 支持多批次续写，每批生成独立大纲文件（outline_batch_N.json）
- 跨批次合并一致性规则，确保长篇连载不出现设定矛盾

### 技术栈

- **UI**：PyQt6 + 自定义 Frosted Glass / Acrylic 设计系统
- **LLM**：支持 LongCat（Anthropic 协议）和 DeepSeek（OpenAI 协议）
- **并发**：threading.Semaphore 控制章节并行数
- **Web 监控**：Flask 提供本地 HTTP 状态接口（默认端口 5000）

## 功能概览

- 从一句灵感生成世界观、人物和章节粗纲。
- 使用独立大纲阶段生成详细章节大纲、一致性规则和角色弧线。
- 多线程并行生成章节，并自动进行质量评估、回流修订和格式适配。
- 可暂停并保存，之后在项目库中从断点继续生成。
- 在预览页查看世界观、按章节号排序的目录和章节正文。
- 导出为 TXT 或 Markdown。
- 启动本地运行监控页，默认地址为 `http://localhost:5000`。

## 环境要求

- Python 3.10 或更高版本
- 可用的 LongCat 或 DeepSeek API Key
- Windows、macOS 或 Linux 图形桌面环境

## 安装与启动

建议在虚拟环境中安装依赖。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

首次启动后，在“设置”页填写 API Key，并确认服务商、模型与接口地址。应用会把配置保存在项目根目录的 `config.json`。

> 请不要将包含真实 API Key 的 `config.json` 提交到公开仓库或发送给他人。

## 使用流程

1. 在“创作”页输入小说灵感，选择章节数量和目标字数。
2. 确认后，任务会在“工作台”依次经历：世界观构建 → 大纲生成 → 章节生成 → 质量评估 → 回流修订 → 多平台适配。
3. 在“预览”页查看世界观、详细大纲、章节目录与正文；章节目录始终按章节号排列。
4. 全部完成后，在预览页点击“导出 TXT”或“导出 Markdown”。

## 暂停、保存与继续生成

工作台顶部提供“暂停并保存”按钮。

- 点击后，应用不会再启动新的生成步骤。
- 已经发出的单次模型请求无法强制取消；它返回后，已完成的世界观、大纲或章节会先保存，再进入暂停状态。
- 暂停后的项目会在“项目库”显示“已暂停”。点击“继续生成”即可恢复。
- 若项目缺少 `outline.json`，继续生成会先恢复大纲阶段；若大纲完整，则只生成缺失章节。
- 继续生成会沿用项目保存时的目标章节字数。

暂停后可以浏览和打开其他项目。若当前模型请求仍在返回中，请等待状态变为“已暂停”后，再启动另一项生成任务。

## 项目文件说明

每次创作会在 `projects/` 下创建一个独立目录，通常包含：

```text
projects/<项目名_时间戳>/
├── summary.json                 # 灵感、状态、字数、暂停/完成信息
├── world_view.json              # 世界观、人物、章节粗纲
├── outline.json                 # 详细大纲、一致性规则、角色弧线
└── chapters/
    ├── chapter_001.txt          # 章节正文
    └── chapter_001_meta.json    # 章节元数据
```

当模型返回的 JSON 格式存在少量常见笔误时，程序会尝试进行保守修复；若仍无法解析，原始响应会保存到 `projects/_parse_failures/`，便于排查。

## 配置项

常用配置位于 `config.json`：

| 配置项 | 说明 |
| --- | --- |
| `api_key` | 服务商 API Key |
| `provider` | `longcat` 或 `deepseek` |
| `model` | 调用的模型名称 |
| `base_url` | 服务商 API 接口地址 |
| `concurrency` | 章节并行生成数量 |
| `default_chapter_count` | 默认章节数 |
| `default_chapter_length` | 默认每章目标字数 |
| `outline_max_tokens` | 大纲生成的最大 token 数 |
| `outline_temperature` | 大纲生成的温度参数 |
| `web_monitor_port` | 本地监控页端口 |

## 常见问题

### 启动后没有生成内容

请先在“设置”页检查 API Key、服务商、模型名称和接口地址；也可检查运行日志中的具体报错。

### 大纲生成失败

应用会将无法解析的原始模型响应保存到 `projects/_parse_failures/`。可在日志中确认失败原因，然后在项目库点击“继续生成”从大纲阶段重试。

### 端口被占用

本地监控默认使用固定端口。请先关闭另一个正在运行的应用实例，或修改 `web_monitor_port` 后重启应用。

### 如何打包为 Windows 程序

安装 PyInstaller 后，在项目根目录执行：

```powershell
pyinstaller -y --clean "AI小说工厂.spec"
```

输出目录为 `dist/AI小说工厂/`。

## 开发检查

修改 Python 文件后，可先进行语法检查：

```powershell
python -m py_compile core/pipeline.py
```
