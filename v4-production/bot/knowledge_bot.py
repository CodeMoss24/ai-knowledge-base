"""
bot/knowledge_bot.py — 交互式 AI 知识库机器人

支持多种用户意图识别、命令系统和权限管理。
可对接 Telegram / 飞书 / 命令行等多种前端。
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================
# 权限系统
# ============================================================

class PermissionLevel(Enum):
    """用户权限级别。"""
    READ = "read"       # 只读：搜索、浏览（默认）
    WRITE = "write"     # 读写：管理订阅（管理员）
    DELETE = "delete"    # 完全控制：删除条目（拥有者）


@dataclass
class User:
    """用户信息。"""
    user_id: str
    username: str = ""
    permission: PermissionLevel = PermissionLevel.READ
    subscriptions: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 意图识别
# ============================================================

class Intent(Enum):
    """用户意图类型。"""
    SEARCH = "search"
    BROWSE_TODAY = "browse_today"
    BROWSE_TOP = "browse_top"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    HELP = "help"
    UNKNOWN = "unknown"


# 意图识别规则（正则 + 关键词）
INTENT_PATTERNS: list[tuple[Intent, re.Pattern]] = [
    (Intent.SEARCH, re.compile(
        r"(?:搜索|查询|查找|搜|找|search|find|关于)\s*(.+)", re.IGNORECASE
    )),
    (Intent.BROWSE_TODAY, re.compile(
        r"(?:今[天日]|简报|摘要|today|daily|digest)", re.IGNORECASE
    )),
    (Intent.BROWSE_TOP, re.compile(
        r"(?:热门|top|排行|热榜|trending|本周)", re.IGNORECASE
    )),
    (Intent.SUBSCRIBE, re.compile(
        r"(?:订阅|subscribe)\s*(.+)", re.IGNORECASE
    )),
    (Intent.UNSUBSCRIBE, re.compile(
        r"(?:取消订阅|unsubscribe)\s*(.+)", re.IGNORECASE
    )),
    (Intent.HELP, re.compile(
        r"(?:帮助|help|命令|怎么用|使用说明)", re.IGNORECASE
    )),
]

# 命令前缀映射
COMMAND_MAP: dict[str, Intent] = {
    "/search": Intent.SEARCH,
    "/today": Intent.BROWSE_TODAY,
    "/top": Intent.BROWSE_TOP,
    "/subscribe": Intent.SUBSCRIBE,
    "/unsubscribe": Intent.UNSUBSCRIBE,
    "/help": Intent.HELP,
}


def recognize_intent(text: str) -> tuple[Intent, str]:
    """识别用户输入的意图和参数。

    优先匹配命令前缀（/search 等），再匹配自然语言关键词。

    Args:
        text: 用户输入文本

    Returns:
        (意图类型, 提取的参数字符串)
    """
    text = text.strip()

    # 优先：命令前缀匹配
    for cmd, intent in COMMAND_MAP.items():
        if text.lower().startswith(cmd):
            args = text[len(cmd):].strip()
            return intent, args

    # 其次：自然语言关键词匹配
    for intent, pattern in INTENT_PATTERNS:
        match = pattern.search(text)
        if match:
            # 尝试提取参数（第一个捕获组）
            args = match.group(1) if match.lastindex else ""
            return intent, args

    return Intent.UNKNOWN, text


# ============================================================
# 知识库检索引擎
# ============================================================

class KnowledgeSearchEngine:
    """知识库检索引擎，基于本地 JSON 文件。"""

    def __init__(self, knowledge_dir: str = "knowledge/articles"):
        self.knowledge_dir = Path(knowledge_dir)

    def search(
        self,
        keyword: str = "",
        tags: list[str] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """搜索知识库条目。

        Args:
            keyword: 关键词（匹配标题和摘要）
            tags: 标签过滤列表
            date_from: 起始日期（YYYY-MM-DD）
            date_to: 截止日期（YYYY-MM-DD）
            limit: 最大返回条数

        Returns:
            匹配的知识条目列表，按相关性排序
        """
        results: list[dict] = []

        if not self.knowledge_dir.exists():
            logger.warning(f"知识库目录不存在：{self.knowledge_dir}")
            return results

        for json_file in self.knowledge_dir.glob("*.json"):
            if json_file.name == "index.json":
                continue

            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    article = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"读取失败：{json_file} ({e})")
                continue

            # 日期过滤
            collected = article.get("collected_at", "")[:10]
            if date_from and collected < date_from:
                continue
            if date_to and collected > date_to:
                continue

            # 标签过滤
            if tags:
                article_tags = set(article.get("tags", []))
                if not article_tags.intersection(set(tags)):
                    continue

            # 关键词匹配（标题 + 摘要）
            if keyword:
                searchable = (
                    article.get("title", "") + " " + article.get("summary", "")
                ).lower()
                if keyword.lower() not in searchable:
                    continue

            results.append(article)

        # 按相关性排序
        results.sort(key=lambda a: a.get("relevance_score", 0), reverse=True)
        return results[:limit]

    def get_today(self, limit: int = 5) -> list[dict]:
        """获取今日知识条目。"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.search(date_from=today, date_to=today, limit=limit)

    def get_top(self, days: int = 7, limit: int = 5) -> list[dict]:
        """获取近 N 天热门条目。"""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.search(date_from=date_from, limit=limit)


# ============================================================
# 订阅管理
# ============================================================

class SubscriptionManager:
    """用户订阅管理器。"""

    def __init__(self, data_file: str = "data/subscriptions.json"):
        self.data_file = Path(data_file)
        self._subscriptions: dict[str, list[str]] = {}
        self._load()

    def _load(self):
        """从文件加载订阅数据。"""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self._subscriptions = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._subscriptions = {}

    def _save(self):
        """持久化订阅数据到文件。"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._subscriptions, f, ensure_ascii=False, indent=2)

    def subscribe(self, user_id: str, tags: list[str]) -> list[str]:
        """为用户添加标签订阅。返回更新后的订阅列表。"""
        current = set(self._subscriptions.get(user_id, []))
        current.update(tags)
        self._subscriptions[user_id] = sorted(current)
        self._save()
        return self._subscriptions[user_id]

    def unsubscribe(self, user_id: str, tags: list[str]) -> list[str]:
        """为用户取消标签订阅。返回更新后的订阅列表。"""
        current = set(self._subscriptions.get(user_id, []))
        current -= set(tags)
        self._subscriptions[user_id] = sorted(current)
        self._save()
        return self._subscriptions[user_id]

    def get_subscriptions(self, user_id: str) -> list[str]:
        """获取用户的订阅标签列表。"""
        return self._subscriptions.get(user_id, [])

    def get_subscribers(self, tag: str) -> list[str]:
        """获取订阅某标签的所有用户 ID。"""
        return [
            uid for uid, tags in self._subscriptions.items()
            if tag in tags
        ]


# ============================================================
# 权限管理
# ============================================================

class PermissionManager:
    """用户权限管理器。"""

    def __init__(self, config_file: str = "data/permissions.json"):
        self.config_file = Path(config_file)
        self._permissions: dict[str, str] = {}
        self._load()

    def _load(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self._permissions = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._permissions = {}

    def get_level(self, user_id: str) -> PermissionLevel:
        """获取用户权限级别，默认 READ。"""
        level_str = self._permissions.get(user_id, "read")
        try:
            return PermissionLevel(level_str)
        except ValueError:
            return PermissionLevel.READ

    def check(self, user_id: str, required: PermissionLevel) -> bool:
        """检查用户是否有指定权限。"""
        level_order = {
            PermissionLevel.READ: 0,
            PermissionLevel.WRITE: 1,
            PermissionLevel.DELETE: 2,
        }
        user_level = self.get_level(user_id)
        return level_order[user_level] >= level_order[required]


# ============================================================
# 响应格式化
# ============================================================

def format_search_results(articles: list[dict], query: str = "") -> str:
    """将搜索结果格式化为用户可读的文本。"""
    if not articles:
        tips = "💡 试试换个关键词，或去掉时间限制。"
        return f"🔍 未找到与「{query}」相关的内容。\n{tips}"

    header = f"🔍 找到 {len(articles)} 条与「{query}」相关的内容：\n"
    lines = [header]

    for i, article in enumerate(articles, 1):
        score = article.get("relevance_score", 0)
        tags = ", ".join(article.get("tags", [])[:3])
        source = article.get("source", "未知")
        date = article.get("collected_at", "")[:10]

        lines.append(f"📌 {i}. **{article['title']}**")
        lines.append(f"   {article.get('summary', '暂无摘要')[:80]}...")
        lines.append(f"   📊 {score:.1f} | {source} | {date} | {tags}")
        lines.append(f"   🔗 {article.get('url', '#')}")
        lines.append("")

    return "\n".join(lines)


def format_digest(articles: list[dict], title: str = "今日简报") -> str:
    """将文章列表格式化为简报。"""
    if not articles:
        return f"📭 {title}：今日暂无新增内容。"

    lines = [f"📰 **{title}** — {datetime.now().strftime('%Y-%m-%d')}\n"]

    for i, article in enumerate(articles, 1):
        tags = " ".join(f"#{t}" for t in article.get("tags", [])[:3])
        lines.append(f"{i}. **{article['title']}**")
        lines.append(f"   {article.get('summary', '')[:60]}...")
        lines.append(f"   {tags}")
        lines.append("")

    return "\n".join(lines)


def format_help() -> str:
    """生成帮助信息。"""
    return """🤖 **AI 知识库助手** — 使用指南

📋 **命令列表**：
  /search <关键词>  — 搜索知识库
  /today            — 查看今日简报
  /top              — 本周热门 Top 5
  /subscribe <标签>  — 订阅特定主题
  /unsubscribe <标签> — 取消订阅
  /help             — 显示本帮助

💬 **自然语言**：
  你也可以直接用中文描述需求，例如：
  - "搜索 MCP 协议相关的文章"
  - "今天有什么新内容？"
  - "帮我订阅 agent 和 rag 标签"

📊 **知识来源**：GitHub Trending, Hacker News, arXiv
🕐 **更新频率**：每日自动采集"""


# ============================================================
# 核心机器人类
# ============================================================

class KnowledgeBot:
    """AI 知识库交互式机器人。

    整合意图识别、知识检索、订阅管理和权限控制。
    可对接任意前端（Telegram、飞书、CLI）。

    Usage:
        bot = KnowledgeBot(knowledge_dir="knowledge/articles")
        response = bot.handle_message(user_id="user123", text="搜索 MCP")
        print(response)
    """

    def __init__(
        self,
        knowledge_dir: str = "knowledge/articles",
        data_dir: str = "data",
    ):
        self.search_engine = KnowledgeSearchEngine(knowledge_dir)
        self.subscription_mgr = SubscriptionManager(f"{data_dir}/subscriptions.json")
        self.permission_mgr = PermissionManager(f"{data_dir}/permissions.json")
        logger.info("KnowledgeBot 初始化完成")

    def handle_message(self, user_id: str, text: str) -> str:
        """处理用户消息，返回响应文本。

        这是机器人的主入口。根据意图识别结果分发到对应处理器。

        Args:
            user_id: 用户唯一标识
            text: 用户输入文本

        Returns:
            响应文本
        """
        intent, args = recognize_intent(text)
        logger.info(f"[Bot] user={user_id} intent={intent.value} args={args!r}")

        # 路由到对应处理器
        handlers = {
            Intent.SEARCH: self._handle_search,
            Intent.BROWSE_TODAY: self._handle_today,
            Intent.BROWSE_TOP: self._handle_top,
            Intent.SUBSCRIBE: self._handle_subscribe,
            Intent.UNSUBSCRIBE: self._handle_unsubscribe,
            Intent.HELP: self._handle_help,
            Intent.UNKNOWN: self._handle_unknown,
        }

        handler = handlers.get(intent, self._handle_unknown)
        return handler(user_id, args)

    def _handle_search(self, user_id: str, query: str) -> str:
        """处理搜索请求。"""
        if not query:
            return "🔍 请提供搜索关键词。\n例如：/search MCP 协议"

        # 尝试提取标签（#tag 格式）
        tags = re.findall(r"#(\S+)", query)
        # 去掉标签后的纯关键词
        keyword = re.sub(r"#\S+", "", query).strip()

        results = self.search_engine.search(
            keyword=keyword,
            tags=tags if tags else None,
            limit=5,
        )

        return format_search_results(results, query)

    def _handle_today(self, user_id: str, args: str) -> str:
        """处理今日简报请求。"""
        articles = self.search_engine.get_today(limit=5)
        return format_digest(articles, title="今日简报")

    def _handle_top(self, user_id: str, args: str) -> str:
        """处理热门排行请求。"""
        articles = self.search_engine.get_top(days=7, limit=5)
        return format_digest(articles, title="本周热门 Top 5")

    def _handle_subscribe(self, user_id: str, args: str) -> str:
        """处理订阅请求。需要 WRITE 权限。"""
        if not self.permission_mgr.check(user_id, PermissionLevel.WRITE):
            return "⚠️ 订阅功能需要管理员权限。请联系管理员开通。"

        if not args:
            current = self.subscription_mgr.get_subscriptions(user_id)
            if current:
                tags_str = ", ".join(f"`{t}`" for t in current)
                return f"📋 你当前的订阅标签：{tags_str}\n\n使用 `/subscribe <标签>` 添加新订阅。"
            return "📋 你还没有订阅任何标签。\n\n使用 `/subscribe llm agent rag` 订阅感兴趣的主题。"

        # 解析标签（空格或逗号分隔）
        tags = [t.strip().lower() for t in re.split(r"[,\s]+", args) if t.strip()]
        updated = self.subscription_mgr.subscribe(user_id, tags)
        tags_str = ", ".join(f"`{t}`" for t in updated)
        return f"✅ 订阅成功！当前订阅列表：{tags_str}"

    def _handle_unsubscribe(self, user_id: str, args: str) -> str:
        """处理取消订阅请求。"""
        if not args:
            return "请指定要取消的标签。\n例如：/unsubscribe llm"

        tags = [t.strip().lower() for t in re.split(r"[,\s]+", args) if t.strip()]
        updated = self.subscription_mgr.unsubscribe(user_id, tags)
        if updated:
            tags_str = ", ".join(f"`{t}`" for t in updated)
            return f"✅ 已取消订阅。剩余订阅：{tags_str}"
        return "✅ 已取消订阅。当前无任何订阅。"

    def _handle_help(self, user_id: str, args: str) -> str:
        """返回帮助信息。"""
        return format_help()

    def _handle_unknown(self, user_id: str, text: str) -> str:
        """处理无法识别的意图。"""
        return (
            "🤔 我没有理解你的意思。\n\n"
            "你可以试试：\n"
            "- 搜索 MCP 协议\n"
            "- /today 查看今日简报\n"
            "- /help 查看完整命令列表"
        )


# ============================================================
# CLI 交互模式
# ============================================================

def run_cli():
    """命令行交互模式，方便本地测试。"""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    bot = KnowledgeBot()
    user_id = "cli-user"

    print("🤖 AI 知识库助手（CLI 模式）")
    print("输入 /help 查看命令，输入 quit 退出\n")

    while True:
        try:
            text = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if text.lower() in ("quit", "exit", "q"):
            print("👋 再见！")
            break

        if not text:
            continue

        response = bot.handle_message(user_id, text)
        print(f"\n助手：{response}\n")


if __name__ == "__main__":
    run_cli()
