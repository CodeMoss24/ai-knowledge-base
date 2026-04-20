---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能
allowed-tools: Read, Grep, Glob, WebFetch
---

# GitHub Trending 采集技能

## 使用场景

当需要采集 GitHub 热门开源项目、追踪 AI/LLM/Agent 领域流行趋势时使用此技能。

## 执行步骤

1. **搜索热门仓库**：调用 GitHub API 获取 GitHub Trending 页面数据
2. **提取信息**：解析返回数据，提取仓库名、URL、Star 数、语言、主题等字段
3. **过滤**：纳入 AI/LLM/Agent 相关项目，排除 Awesome 系列列表
4. **去重**：基于仓库名去重，避免同一项目多次出现
5. **撰写中文摘要**：使用公式 `项目名 + 做什么 + 为什么值得关注`，生成简洁的中文摘要
6. **排序取 Top15**：按 Star 数降序排列，选取前 15 个项目
7. **输出 JSON**：将结果以 JSON 格式保存至 `knowledge/raw/github-trending-YYYY-MM-DD.json`

## 注意事项

- GitHub API 有速率限制，批量请求时需添加延迟
- 过滤时使用关键词：ai、llm、agent、gpt、openai、machine-learning、neural-network 等
- 排除关键词：awesome、list、curated、resources
- 日期格式使用 ISO 8601：`YYYY-MM-DDTHH:mm:ssZ`
- 确保 UTF-8 编码

## 输出格式

```json
{
  "source": "github-trending",
  "skill": "github-trending",
  "collected_at": "2026-04-20T08:00:00Z",
  "items": [
    {
      "name": "owner/repo-name",
      "url": "https://github.com/owner/repo-name",
      "summary": "项目名 是一个...，值得关注是因为...",
      "stars": 12345,
      "language": "Python",
      "topics": ["ai", "llm"]
    }
  ]
}
```
