# AI Knowledge Base Assistant

## 1. 项目概述

本项目是一个 AI 技术动态采集与分发系统，自动从 GitHub Trending 和 Hacker News 抓取 AI/LLM/Agent 领域的技术资讯，经 AI 分析后结构化存储，并支持通过 Telegram 和飞书等多渠道分发。

## 2. 技术栈

| 组件 | 技术选型 |
|------|----------|
| 语言 | Python 3.12 |
| 大模型 | OpenCode + 国产大模型（通义千问/DeepSeek/Kimi） |
| Agent 框架 | LangGraph |
| 爬虫 | OpenClaw |
| 数据存储 | JSON 文件（knowledge/articles/） |

## 3. 编码规范

- **风格指南**：严格遵循 [PEP 8](https://pep8.org/)
- **命名规范**：变量/函数使用 `snake_case`，类名使用 `PascalCase`，常量使用 `UPPER_SNAKE_CASE`
- **文档字符串**：所有模块、类、函数必须使用 [Google 风格 docstring](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- **日志规范**：禁止使用裸 `print()`，必须使用 `logging` 模块
- **类型注解**：函数参数和返回值必须标注类型

## 4. 项目结构

```
ai-knowledge-base/
├── .opencode/
│   ├── agents/           # Agent 角色定义
│   │   ├── collector.py  # 采集 Agent
│   │   ├── analyzer.py   # 分析 Agent
│   │   └── organizer.py  # 整理 Agent
│   └── skills/           # 技能配置
├── knowledge/
│   ├── raw/              # 原始采集数据
│   └── articles/         # 结构化知识条目
└── AGENTS.md
```

## 5. 知识条目 JSON 格式

```json
{
  "id": "uuid-v4",
  "title": "string (必需, 最大 200 字符)",
  "source_url": "string (必需, 有效 URL)",
  "source_name": "string (github_trending | hacker_news)",
  "summary": "string (必需, 100-500 字)",
  "tags": ["string"],
  "status": "pending | analyzed | published | archived",
  "created_at": "ISO8601 时间戳",
  "updated_at": "ISO8601 时间戳",
  "published_at": "ISO8601 时间戳 (可选)",
  "metadata": {
    "author": "string (可选)",
    "stars": "integer (可选, GitHub)",
    "comments": "integer (可选, HN)"
  }
}
```

## 6. Agent 角色概览

| Agent | 角色名称 | 职责 | 核心工具 |
|-------|----------|------|----------|
| Collector | 技术动态采集员 | 从 GitHub Trending 和 Hacker News 抓取原始内容 | OpenClaw 爬虫、RSS 订阅 |
| Analyzer | AI 内容分析师 | 提取摘要、生成标签、判断价值 | LLM API (通义千问/DeepSeek) |
| Organizer | 知识整理工程师 | 质量审核、去重、结构化存储、多渠道分发 | LangGraph 工作流、Telegram Bot、飞书 Webhook |

## 7. 红线（绝对禁止）

> 以下行为一经发现将导致代码回滚并触发 code review。

1. **禁止提交真实 API Key 或 Access Token** — 必须使用环境变量或 `.env.example`
2. **禁止硬编码 Secrets** — 配置信息必须外置
3. **禁止直接 `print()` 输出** — 必须通过 `logging` 模块记录日志
4. **禁止绕过 LLM 分析直接写入 `knowledge/articles/`** — 所有条目必须经 Analyzer 处理
5. **禁止修改他人 Pull Request 分支** — 只能通过 PR 合入代码
6. **禁止删除 `knowledge/articles/` 历史数据** — 仅允许更新 `status` 字段
7. **禁止向第三方服务发送用户敏感信息**
