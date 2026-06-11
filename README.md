# AI Knowledge Base

基于 LangGraph 的 AI 知识库采集与分析系统。每日定时从 GitHub Trending、Hacker News、arXiv 采集 AI 资讯，经过 LangGraph 多轮审核工作流分析整理，分发到飞书 / Telegram 等渠道，并提供交互式知识库机器人。

## 功能

- **自动采集** — 每日 8:00 和 20:00 定时从 GitHub Trending、Hacker News、arXiv 采集 AI 相关资讯
- **LangGraph 工作流** — Planner → Collector → Analyzer → Organizer → Reviewer 多轮审核循环，LLM 驱动的质量把关
- **多平台分发** — 支持飞书 Webhook、Telegram Bot、文件输出
- **交互式机器人** — 支持自然语言和命令两种交互方式，意图识别 + 关键词搜索 + 标签订阅
- **Docker 部署** — Docker Compose 一键启动 pipeline + bot 双服务

## 技术栈

| 层级 | 技术 |
|------|------|
| 工作流引擎 | LangGraph + LangChain |
| LLM | OpenAI API |
| 存储 | JSON 文件存储 |
| 机器人 | 自研 KnowledgeBot（意图识别 + 权限 + 订阅） |
| 容器化 | Docker + Docker Compose + Cron |
| 异步 | aiohttp |

## 快速开始

```bash
# 1. 克隆仓库
git clone git@github.com:CodeMoss24/ai-knowledge-base.git
cd ai-knowledge-base/v4-production

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OPENAI_API_KEY 等

# 3. 一键启动（pipeline 定时采集 + bot 交互服务）
docker compose up -d

# 4. 查看日志
docker compose logs -f
```

## 项目结构

```
v4-production/
├── pipeline/        # 采集分析流水线入口
├── workflows/       # LangGraph 工作流定义（plan/collect/analyze/organize/review）
├── patterns/        # Router / Supervisor 模式
├── bot/             # 交互式知识库机器人
├── distribution/    # 多平台分发（飞书/Telegram）
├── scripts/         # 部署脚本
├── Dockerfile       # 多阶段构建
└── docker-compose.yml
```

## 机器人命令

| 命令 | 说明 |
|------|------|
| `/search <关键词>` | 搜索知识库 |
| `/today` | 查看今日简报 |
| `/top` | 本周热门 Top 5 |
| `/subscribe <标签>` | 订阅主题 |
| `/help` | 查看帮助 |

## License

MIT
