# AGENTS.md — AI 知识库 V4（生产版）

> 本文件是项目的"大脑"——OpenCode 启动时自动加载，指导所有 Agent 的行为。
> V4 在 V3 基础上新增：OpenClaw 部署、多渠道分发、交互式机器人、Docker 容器化。

## 项目定义

**AI Knowledge Base V4（AI 知识库·生产版）** 是一个完整的技术情报平台。
在 V3 的多 Agent 流水线基础上，增加了内容分发、交互式问答和容器化部署能力。

### 核心价值
- 每日自动采集 AI/LLM/Agent 领域的高质量技术文章与开源项目
- 通过 Agent 协作完成 **采集 → 分析 → 整理 → 分发** 四阶段流水线
- 多渠道内容分发：Telegram 频道、飞书群组
- 交互式知识库机器人：支持搜索、订阅、每日简报
- OpenClaw 网关统一接入，Docker 一键部署

## 项目结构

```
v4-production/
├── AGENTS.md                          # 项目记忆文件（本文件）
├── .env.example                       # 环境变量模板
├── README.md                          # 使用说明
├── requirements.txt                   # Python 依赖
├── Dockerfile                         # Docker 镜像定义
├── docker-compose.yml                 # 服务编排
│
├── pipeline/                          # 采集分析流水线（V2/V3 继承）
│   ├── __init__.py
│   └── pipeline.py                    # 三阶段流水线 + 自动发布
│
├── distribution/                      # V4 新增：多渠道分发
│   ├── __init__.py
│   ├── formatter.py                   # 格式转换（Markdown/Telegram/飞书）
│   └── publisher.py                   # 异步多渠道发布器
│
├── bot/                               # V4 新增：交互式机器人
│   ├── __init__.py
│   └── knowledge_bot.py              # 意图识别、命令系统、权限管理
│
├── openclaw/                          # V4 新增：OpenClaw 消息网关
│   ├── openclaw.json5                 # 网关配置
│   ├── SOUL.md                        # Bot 人格定义
│   ├── AGENTS.md                      # Agent 路由配置
│   └── skills/
│       └── knowledge-query/
│           └── SKILL.md               # 知识检索技能
│
├── scripts/
│   └── deploy.sh                      # 部署脚本
│
├── knowledge/                         # 知识库数据（Docker volume 挂载）
│   ├── raw/                           # 原始采集数据
│   └── articles/                      # 整理后的知识条目
│
└── data/                              # 运行时数据
    ├── subscriptions.json             # 用户订阅
    └── permissions.json               # 用户权限
```

## 编码规范

### 文件命名
- 原始数据：`knowledge/raw/{source}-{YYYY-MM-DD}.json`
- 知识条目：`knowledge/articles/{YYYY-MM-DD}-{slug}.json`
- 索引文件：`knowledge/articles/index.json`

### JSON 格式
- 使用 2 空格缩进
- 日期格式：ISO 8601（`YYYY-MM-DDTHH:mm:ssZ`）
- 字符编码：UTF-8
- 每个知识条目必须包含：`id`, `title`, `source`, `url`, `collected_at`, `summary`, `tags`, `relevance_score`

### 语言约定
- 代码、JSON 键名、文件名：英文
- 摘要、分析、注释：中文
- 标签（tags）：英文小写，用连字符分隔（如 `large-language-model`）

## 工作流规则

### 四阶段流水线（V4 扩展）

```
[Collector] ──采集──→ knowledge/raw/
                          │
[Analyzer]  ──分析──→ knowledge/raw/ (enriched)
                          │
[Organizer] ──整理──→ knowledge/articles/
                          │
[Publisher] ──分发──→ Telegram / 飞书 / OpenClaw
```

### Agent 协作规则

1. **单向数据流**：Collector → Analyzer → Organizer → Publisher，不可反向
2. **职责隔离**：每个 Agent 只操作自己权限范围内的文件
3. **幂等性**：重复运行同一天的采集不应产生重复条目
4. **质量门控**：Analyzer 评分低于 0.6 的条目，Organizer 应丢弃
5. **可追溯**：每个条目保留 `source_url` 和 `collected_at` 用于溯源

### Bot 交互规则

1. **权限分级**：read（默认） / write（管理员） / delete（拥有者）
2. **意图识别**：优先匹配命令前缀（/search），其次匹配自然语言关键词
3. **引用来源**：所有回答必须附带来源链接或日期
4. **简洁回复**：默认 3-5 句话，用户要求时才展开

### 错误处理
- 网络请求失败时，记录错误并跳过该条目，不中断整体流程
- API 限流时，等待后重试，最多 3 次
- 数据格式异常时，写入 `knowledge/raw/errors-{date}.json` 供人工排查
- 发布失败时，记录到日志，不影响流水线其他阶段

## 技术栈

- **运行时**：Python 3.12 + asyncio
- **消息网关**：OpenClaw Gateway
- **容器化**：Docker + Docker Compose
- **数据源**：GitHub API v3、Hacker News API (Firebase)
- **分发渠道**：Telegram Bot API、飞书 Webhook
- **HTTP 客户端**：aiohttp（异步）
- **输出格式**：JSON
- **版本管理**：Git
