# Agent 协作规格

> 来源：specs/agents-collaboration-draft.md + AGENTS.md（修订版）
> 版本：2.0

---

## 一、触发模式

| 模式 | 用途 | 切换方式 |
|------|------|----------|
| **手动触发** | 开发调试、首次运行、问题排查 | 直接运行 `@collector` 等命令 |
| **定时触发** | 稳定生产环境 | 外部 cron + OpenCode CLI（如 `opencode run --agent collector`） |

两者共享同一套代码逻辑，无状态差异。

---

## 二、数据流定义

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      完整数据流                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Collector                                                       │
│  ┌────────────┐    ┌──────────────────────────┐                 │
│  │ GitHub API │───▶│ knowledge/raw/          │                 │
│  │ Trending   │    │ {source}-{YYYY-MM-DD}.json│               │
│  └────────────┘    └──────────────────────────┘                 │
│                                    │                             │
│                                    ▼                             │
│  Analyzer                           │                             │
│  ┌────────────┐    ┌──────────────────────────┐                 │
│  │ 读取raw/   │◀───│ enrichment（追加分析结果）│                 │
│  └────────────┘    └──────────────────────────┘                 │
│                                    │                             │
│                                    ▼                             │
│  Organizer                          │                             │
│  ┌────────────┐    ┌──────────────────────────┐                 │
│  │ 读取enriched│───▶│ knowledge/articles/     │                 │
│  └────────────┘    │ {date}-{slug}.json       │                 │
│                    └──────────────────────────┘                 │
│                           │                                      │
│                           ▼                                      │
│                    ┌──────────────────┐                          │
│                    │ index.json 索引  │                          │
│                    └──────────────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 传递机制

- **Collector → Analyzer**：文件路径 + JSON 文件内容
- **Analyzer → Organizer**：enriched JSON 文件（追加分析结果）
- **Organizer → 索引**：更新 `knowledge/articles/index.json`

### 2.3 文件命名规则

| 文件类型 | 命名格式 | 示例 |
|----------|----------|------|
| 原始采集 | `knowledge/raw/{source}-{YYYY-MM-DD}.json` | `knowledge/raw/github-trending-2026-04-17.json` |
| 错误记录 | `knowledge/raw/errors-{YYYY-MM-DD}.json` | `knowledge/raw/errors-2026-04-17.json` |
| 知识条目 | `knowledge/articles/{YYYY-MM-DD}-{slug}.json` | `knowledge/articles/2026-04-17-openai-agents-sdk.json` |
| 索引文件 | `knowledge/articles/index.json` | — |

---

## 三、各 Agent 职责与规格

### 3.1 Collector（采集 Agent）

**职责**：抓取 GitHub Trending Top 10

**输入**：
- 环境变量：`GITHUB_TOKEN`（可选）

**处理逻辑**：
1. 调用 GitHub API，按星标数排序，取 Top 10
2. 追加写入 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`
3. 幂等性：运行前先检查当日文件是否已存在，存在则跳过（避免重复采集）

**输出 JSON Schema**：
```json
{
  "source": "github_trending",
  "collected_at": "ISO8601 时间戳",
  "url": "string",
  "title": "string",
  "description": "string",
  "language": "string",
  "stars": "integer",
  "forks": "integer",
  "open_issues": "integer",
  "author": "string",
  "repo_name": "string"
}
```

**边界情况处理**：
| 情况 | 处理方式 |
|------|----------|
| GitHub API 返回空 | 记录 WARNING，写入空数组到文件，继续执行 |
| 网络超时 | 重试 3 次，间隔 5s/10s/20s（指数退避），失败则写入 `errors-{date}.json` |
| API 限流（403） | 使用 `GITHUB_TOKEN` 重试，无 token 则等待 60s 后重试 |
| 当日文件已存在 | 跳过写入（幂等性），记录 INFO 日志 |

---

### 3.2 Analyzer（分析 Agent）

**职责**：读取 `raw/` 文件，打分并生成摘要、标签，写入 enriched 数据

**输入**：
- 文件：`knowledge/raw/{source}-{YYYY-MM-DD}.json`

**处理逻辑**：
1. 读取指定日期的 raw JSON 文件
2. 对每个条目调用 LLM API，生成：
   - `summary`：100-500 字摘要
   - `tags`：3-5 个标签数组
   - `relevance_score`：0.0-1.0 质量分
3. 将分析结果追加写入原文件的每条记录中（enriched）

**输出 JSON Schema（追加到原条目）**：
```json
{
  "source": "github_trending",
  "collected_at": "ISO8601 时间戳",
  "url": "string",
  "title": "string",
  "description": "string",
  "language": "string",
  "stars": "integer",
  "forks": "integer",
  "open_issues": "integer",
  "author": "string",
  "repo_name": "string",
  "summary": "string（新增）",
  "tags": ["string"]（新增）,
  "relevance_score": 0.0-1.0（新增）,
  "analyzed_at": "ISO8601 时间戳（新增）"
}
```

**边界情况处理**：
| 情况 | 处理方式 |
|------|----------|
| 原文件不存在 | 记录 ERROR，跳过，流程继续 |
| LLM 返回格式错误 | 重试 3 次，间隔 5s/10s/20s（指数退避），失败则写入 `errors-{date}.json` |
| LLM 返回空白内容 | 视为分析失败，记录 `error_message` |
| 条目已有 enriched 数据 | 跳过已分析条目（幂等性） |

---

### 3.3 Organizer（整理 Agent）

**职责**：从 enriched JSON 读取，进行质量过滤、去重，生成知识条目

**输入**：
- 文件：`knowledge/raw/{source}-{YYYY-MM-DD}.json`（已 enriched）

**处理逻辑**：
1. 读取 enriched JSON
2. 质量过滤：`relevance_score < 0.6` 的条目丢弃
3. 去重检查：基于 `url` 精确匹配，已存在于 `index.json` 则跳过
4. 生成知识条目 JSON，写入 `knowledge/articles/{YYYY-MM-DD}-{slug}.json`
5. 更新 `knowledge/articles/index.json` 索引

**输出 JSON Schema（知识条目）**：
```json
{
  "id": "UUID v4",
  "title": "string",
  "source": "github_trending",
  "url": "string",
  "collected_at": "ISO8601 时间戳",
  "summary": "string",
  "tags": ["string"],
  "relevance_score": 0.0-1.0,
  "analyzed_at": "ISO8601 时间戳"
}
```

**index.json 格式**：
```json
[
  {
    "id": "UUID v4",
    "title": "string",
    "url": "string",
    "source": "github_trending",
    "file": "2026-04-17-openai-agents-sdk.json",
    "collected_at": "ISO8601 时间戳"
  }
]
```

**边界情况处理**：
| 情况 | 处理方式 |
|------|----------|
| 条目 relevance_score < 0.6 | 丢弃，记录 DEBUG 日志 |
| URL 已存在于 index.json | 跳过去重，记录 INFO 日志 |
| slug 冲突（相同标题不同条目） | slug 末尾加 `-{n}` 序号 |

---

## 四、异常处理矩阵

| 异常场景 | 触发位置 | 检测方式 | 处理策略 | 影响范围 |
|----------|----------|----------|----------|----------|
| GitHub API 网络超时 | Collector | `requests.exceptions.RequestException` | 重试3次，指数退避，失败写入 errors 文件 | 仅该次采集 |
| GitHub API 限流 | Collector | HTTP 403 | 使用 token 重试，无 token 则等待 60s | 仅该次采集 |
| 原文件不存在 | Analyzer | `FileNotFoundError` | 记录 ERROR，跳过 | 仅该文件 |
| LLM API 超时 | Analyzer | `httpx/requests timeout` | 重试3次，指数退避，失败写入 errors 文件 | 仅该条目 |
| LLM 返回格式错误 | Analyzer | `JSON parse fail` | 重试3次，指数退避，失败写入 errors 文件 | 仅该条目 |
| LLM 分析结果为空 | Analyzer | 返回内容为空 | 写入 errors 文件 | 仅该条目 |
| 文件写入失败（IOError） | 任意 | `OSError` | 流程终止，进程退出码 1 | 全流程 |
| JSON 写入失败（序列化错误） | 任意 | `json.JSONDecodeError` | 流程终止，进程退出码 1 | 全流程 |

**指数退避规则**：
- 第1次重试：等待 5s
- 第2次重试：等待 10s
- 第3次重试：等待 20s
- 3次全部失败：写入 `knowledge/raw/errors-{date}.json`，流程继续

---

## 五、权限矩阵

| 操作 | Collector | Analyzer | Organizer |
|------|-----------|----------|-----------|
| **读取 GitHub API** | ✅ | ❌ | ❌ |
| **写入 `knowledge/raw/{source}-{date}.json`** | ✅ | ❌ | ❌ |
| **读取 `knowledge/raw/{source}-{date}.json`** | ❌ | ✅ | ❌ |
| **追加写入 enriched 数据到 raw 文件** | ❌ | ✅ | ❌ |
| **写入 `knowledge/raw/errors-{date}.json`** | ✅ | ✅ | ❌ |
| **读取 enriched JSON** | ❌ | ❌ | ✅ |
| **写入 `knowledge/articles/{date}-{slug}.json`** | ❌ | ❌ | ✅ |
| **读取/更新 `knowledge/articles/index.json`** | ❌ | ❌ | ✅ |
| **调用 LLM API** | ❌ | ✅ | ❌ |
| **调用 Telegram/飞书 API** | ❌ | ❌ | ✅（如有配置） |

> **实现要求**：每个 Agent 作为独立进程或独立代码模块，不共享文件句柄，通过文件系统解耦。

---

## 六、状态机定义

本架构采用纯文件驱动，无数据库状态机。

### 文件存在性隐式状态

```
knowledge/raw/{source}-{date}.json
    │
    ├── 不存在 ──▶ [未采集]
    │
    └── 存在
          │
          ├── 无 enriched 字段 ──▶ [raw 状态，待分析]
          │
          └── 有 enriched 字段 ──▶ [enriched 状态，待整理]
```

### Organizer 处理结果

```
知识条目文件生成成功 ──▶ index.json 已更新
知识条目被丢弃(score<0.6) ──▶ 不生成文件
知识条目去重命中 ──▶ 不生成文件，记录 INFO
```

---

## 七、回答草案中的问号

| 原始问题 | 答案 |
|----------|------|
| 手动触发还是定时触发？ | 两者共存；手动通过 `@collector` 命令，定时通过外部 cron 调用 OpenCode CLI |
| collector 存哪？文件名规则？ | `knowledge/raw/{source}-{YYYY-MM-DD}.json`，如 `knowledge/raw/github-trending-2026-04-17.json` |
| 如果采集数据为空怎么办？ | 记录 WARNING，写入空数组 `[]`，继续执行 |
| 需要去重吗？ | 需要；Organizer 阶段基于 `url` 精确匹配，检查 `index.json` 是否已存在 |
| 数据怎么传递？ | 文件传递；Collector 写 raw JSON → Analyzer 追加 enriched → Organizer 读取 enriched 生成 articles |
| 上游失败下游怎么办？ | 各阶段独立；失败的条目写入 `errors-{date}.json`，不影响其他条目 |
| 权限怎么分？ | Collector 写 raw，Analyzer 读写 raw（追加 enriched），Organizer 读 enriched 写 articles + index |

---

## 八、关键规格差异对比（v1 → v2）

| 项目 | v1（SQLite） | v2（纯 JSON） |
|------|-------------|---------------|
| 存储介质 | SQLite | JSON 文件 |
| 状态管理 | `status` 字段驱动 | 文件存在性 + enriched 字段 |
| 传递方式 | 数据库行引用 | 文件路径传递 |
| 错误记录 | `error_message` 列 | `errors-{date}.json` 文件 |
| 去重方式 | `source_url` 唯一索引 | `index.json` 查找 |
| 质量门控 | `quality_score` 1-10 | `relevance_score` 0.0-1.0 |
| 索引 | 无 | `index.json` 统一索引 |