---
name: daily-digest
description: 生成今日 AI 技术简报，汇总当天采集的 Top 5 知识条目，按相关性排序
allowed-tools:
  - Read
---

# 每日简报技能

## 触发条件

当用户想要查看今日 / 本周 AI 技术汇总时激活此技能。
典型触发词：简报、摘要、今日、daily、digest、briefing

## 生成流程

### Step 1: 定位今日数据

使用 Glob 匹配今日生成的知识条目：

```
knowledge/articles/{YYYY-MM-DD}-*.json
```

如果今日无数据，回退到最近 7 天的条目。

### Step 2: 读取并过滤

1. Read 每个匹配的 JSON 文件，提取字段
2. 过滤 `relevance_score >= 0.6` 的条目
3. 按 `relevance_score` 降序排序

### Step 3: 聚合生成简报

取 Top 5 条目，按 category 分组：

- **agent** — Agent 框架与工具
- **llm** — 模型进展
- **rag** — 检索增强
- **mcp** — 协议与生态
- **其他** — 综合资讯

每组按 relevance_score 再排序。

### Step 4: 格式化输出

简报模板：

```
📅 **{YYYY-MM-DD} AI 技术简报**

🤖 **Agent**
- [{title}]({url}) — {one_sentence_key_insight}
- ...

🧠 **LLM**
- ...

📚 **RAG**
- ...

💡 **今日要闻**
- {最高分条目的 key_insight}

—— 本简报由 AI 知识库自动生成
```

## 与 Publisher 的分工

- **本 Skill**：格式化文本，生成 Markdown 简报
- **distribution/publisher.py**：把简报推送到 Telegram / 飞书 / 文件

Skill 负责"写"，Publisher 负责"发"。

## 定时触发

在 docker-compose.yml 的 pipeline 服务里，每天 08:00 和 20:00 由 cron 触发：

```
0 8,20 * * * python -m pipeline.pipeline
```

pipeline 跑完 V3 LangGraph 工作流后，会自动调用 publisher 发布简报，
底层复用本 Skill 的格式化逻辑。

## 示例

**用户**：看看今天有什么新东西
**助手**：
```
📅 2026-04-11 AI 技术简报

🤖 Agent
- [langgenius/dify](...) — 可视化 LLM 应用编排平台，显著降低 AI 应用开发门槛
- [microsoft/autogen](...) — 多 Agent 协作框架，支持异构 LLM 混合部署

🧠 LLM
- [DeepSeek v4 发布](...) — 128K 长上下文 + 工具调用能力全面升级

💡 今日要闻
Dify 通过将复杂的智能体工作流开发抽象为可视化编排，显著降低了生产级 LLM 应用的开发门槛。
```
