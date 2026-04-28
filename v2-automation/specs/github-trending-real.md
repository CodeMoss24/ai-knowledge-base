# 需求：GitHub Trending 采集器

## 具体任务
访问 github.com/trending，抓取 Today's Top 50 项目。
只保留 Topics 中包含 ai, llm, agent, ml, deep-learning 的项目。

## 必须输出的字段
- name (项目名)
- url (链接)
- stars (星数，纯数字)
- description (英文原描述)
- summary (一句话中文总结：格式为 [项目名]是[做什么的]，[为什么值得关注])

## 严格禁止
- 禁止调用 GitHub API (会限流)
- 禁止抓取 Awesome 开头的项目
- 如果网站反爬失败，直接输出空数组 `[]`，禁止编造数据

## 输出位置
knowledge/raw/github-trending-$(date +%Y-%m-%d).json