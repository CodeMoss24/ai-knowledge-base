---
name: github-trending
description: |
  采集 GitHub Trending 页面热门项目，过滤 AI/ML/LLM/Agent 相关 repo。Use when 用户说采集 GitHub Trending、抓取 GitHub 热门、GitHub trending、GitHub 排行榜、GitHub 热门项目、获取 GitHub trending 数据、扫描 GitHub 热门、看看 GitHub 有什么热门项目、github trending 有哪些、github-trending、gh trending、或任何提及 GitHub 热门/排行榜/trending 的场景。
---

# GitHub Trending 采集

## Quick start

```bash
node .opencode/skills/github-trending/scripts/scrape.js
```

## Workflow

1. 获取 `https://github.com/trending` HTML 页面
2. 解析提取 Top 50 repo：name, url, stars, topics, description
3. 过滤 topics 包含以下关键词的 repo：`ai`, `llm`, `agent`, `ml`, `machine-learning`, `deep-learning`, `nlp`, `large-language-model`, `generative-ai`, `gpt`, `llm-agent`, `ai-agent`, `rag`, `vector-database`, `langchain`, `autonomous`, `neural`, `transformer`, `chatbot`
4. 输出 JSON 数组到 stdout

## 输出格式

```json
[
  {
    "name": "owner/repo-name",
    "url": "https://github.com/owner/repo-name",
    "stars": "12.3k",
    "topics": ["ai", "machine-learning"],
    "description": "Repo description"
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | `owner/repo-name` 格式 |
| url | string | 完整 GitHub URL |
| stars | string | 原始格式（如 `1.2k`、`3,456`） |
| topics | string[] | 小写 topic 列表 |
| description | string | repo 描述原文 |

## 边界处理

- 单次执行 < 10s
- 失败时返回空数组 `[]`，不抛异常
- 不调 GitHub API（rate limit 限制），走 HTML 解析
- 不做去重（由 caller 处理）

## 脚本说明

- `scripts/scrape.js` - Node.js 抓取脚本，使用内置 https 模块

## 触发场景（供参考）

| 用户表达 | 场景 |
|---------|------|
| "采集今天的 GitHub Trending" | 每日采集 |
| "抓取 GitHub 热门项目" | 通用请求 |
| "GitHub trending 有哪些 AI 项目" | 筛选 AI 类 |
| "github trending" / "gh trending" | 缩写形式 |
| "看看今天 GitHub 热门" | 口语化 |
| "GitHub 排行榜" | 排行榜语境 |
| "扫描 GitHub 热门" | 扫描类 |
| "看看 GitHub 有什么热门项目" | 探索类 |