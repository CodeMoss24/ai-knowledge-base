---
name: github-trending
description: 采集 GitHub Trending 页面的热门 AI/LLM 仓库信息
allowed-tools:
  - Bash
  - Write
---

# GitHub Trending 采集技能

## 触发条件

当需要采集 GitHub Trending 数据时激活。

## 执行步骤

1. 通过 GitHub Search API 搜索近期活跃的 AI/LLM/Agent 相关仓库
2. 提取字段：仓库名、描述、stars、语言、topics、URL
3. 格式化为标准 JSON 条目
4. 写入 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`

## 输出格式

```json
[
  {
    "id": "github-owner-repo",
    "title": "owner/repo — description",
    "source": "GitHub Trending",
    "url": "https://github.com/owner/repo",
    "collected_at": "2026-03-17T08:00:00Z",
    "stars": 1234,
    "language": "Python",
    "topics": ["llm", "agent"]
  }
]
```
