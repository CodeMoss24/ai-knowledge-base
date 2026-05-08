"""
distribution/publisher.py — 多渠道内容发布器

异步发布知识库内容到 Telegram、飞书等渠道。
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

from distribution.formatter import generate_daily_digest, json_to_feishu, json_to_telegram

logger = logging.getLogger(__name__)


# ============================================================
# 发布结果
# ============================================================

@dataclass
class PublishResult:
    """单次发布的结果。"""
    channel: str
    success: bool
    message_id: str | None = None
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ============================================================
# 抽象发布器基类
# ============================================================

class BasePublisher(ABC):
    """发布器抽象基类，定义统一接口。"""

    def __init__(self, channel_name: str):
        self.channel_name = channel_name

    @abstractmethod
    async def send_message(self, chat_id: str, content: str | dict) -> PublishResult:
        """发送单条消息到指定会话。"""
        ...

    @abstractmethod
    async def send_digest(self, chat_id: str, digest_content: str | dict) -> PublishResult:
        """发送每日简报到指定会话。"""
        ...

    async def health_check(self) -> bool:
        """检查渠道连接是否正常。"""
        return True


# ============================================================
# Telegram 发布器
# ============================================================

class TelegramPublisher(BasePublisher):
    """通过 Telegram Bot API 发送消息。

    需要环境变量：
    - TELEGRAM_BOT_TOKEN: Bot API Token
    - TELEGRAM_CHAT_ID: 目标群组或频道 ID
    """

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self):
        super().__init__("telegram")
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.default_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not self.token:
            logger.warning("TELEGRAM_BOT_TOKEN 未设置，Telegram 发布将不可用")

    @property
    def base_url(self) -> str:
        return self.API_BASE.format(token=self.token)

    async def send_message(
        self,
        chat_id: str | None = None,
        content: str = "",
    ) -> PublishResult:
        """发送 MarkdownV2 格式消息到 Telegram。

        Args:
            chat_id: Telegram 会话 ID，默认使用环境变量中的 CHAT_ID
            content: MarkdownV2 格式文本

        Returns:
            PublishResult 发布结果
        """
        target = chat_id or self.default_chat_id
        if not target:
            return PublishResult(
                channel="telegram", success=False, error="未配置 TELEGRAM_CHAT_ID"
            )

        payload = {
            "chat_id": target,
            "text": content,
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/sendMessage",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()

                    if data.get("ok"):
                        msg_id = str(data["result"]["message_id"])
                        logger.info(f"[Telegram] 消息发送成功: {msg_id}")
                        return PublishResult(
                            channel="telegram", success=True, message_id=msg_id
                        )
                    else:
                        error = data.get("description", "未知错误")
                        logger.error(f"[Telegram] 发送失败: {error}")
                        return PublishResult(
                            channel="telegram", success=False, error=error
                        )

        except asyncio.TimeoutError:
            return PublishResult(
                channel="telegram", success=False, error="请求超时（30s）"
            )
        except aiohttp.ClientError as e:
            return PublishResult(
                channel="telegram", success=False, error=f"网络错误: {e}"
            )

    async def send_digest(
        self,
        chat_id: str | None = None,
        digest_content: str = "",
    ) -> PublishResult:
        """发送每日简报到 Telegram。"""
        return await self.send_message(chat_id, digest_content)

    async def health_check(self) -> bool:
        """调用 getMe 接口检查 Bot 连接。"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/getMe",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    data = await resp.json()
                    return data.get("ok", False)
        except Exception:
            return False


# ============================================================
# 飞书发布器
# ============================================================

class FeishuPublisher(BasePublisher):
    """通过飞书 Webhook 发送卡片消息。

    需要环境变量：
    - FEISHU_WEBHOOK_URL: 飞书自定义机器人 Webhook 地址
    - FEISHU_APP_ID: 飞书应用 ID（用于 API 调用）
    - FEISHU_APP_SECRET: 飞书应用密钥
    """

    def __init__(self):
        super().__init__("feishu")
        self.webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
        self.app_id = os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = os.environ.get("FEISHU_APP_SECRET", "")
        if not self.webhook_url:
            logger.warning("FEISHU_WEBHOOK_URL 未设置，飞书发布将不可用")

    async def _get_tenant_token(self) -> str | None:
        """获取飞书 tenant_access_token。"""
        if not self.app_id or not self.app_secret:
            return None

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {"app_id": self.app_id, "app_secret": self.app_secret}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json()
                    if data.get("code") == 0:
                        return data["tenant_access_token"]
                    else:
                        logger.error(f"[飞书] 获取 token 失败: {data}")
                        return None
        except Exception as e:
            logger.error(f"[飞书] 获取 token 异常: {e}")
            return None

    async def send_message(
        self,
        chat_id: str | None = None,
        content: str | dict = "",
    ) -> PublishResult:
        """通过 Webhook 发送消息到飞书群组。

        Args:
            chat_id: 飞书群组 ID（Webhook 模式下忽略）
            content: 飞书卡片 JSON 或纯文本

        Returns:
            PublishResult 发布结果
        """
        if not self.webhook_url:
            return PublishResult(
                channel="feishu", success=False, error="未配置 FEISHU_WEBHOOK_URL"
            )

        # 如果是纯文本，包装为文本消息
        if isinstance(content, str):
            payload = {"msg_type": "text", "content": {"text": content}}
        else:
            payload = content

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    data = await resp.json()

                    if data.get("code") == 0 or data.get("StatusCode") == 0:
                        logger.info("[飞书] 消息发送成功")
                        return PublishResult(
                            channel="feishu",
                            success=True,
                            message_id=data.get("data", {}).get("message_id"),
                        )
                    else:
                        error = data.get("msg", data.get("StatusMessage", "未知错误"))
                        logger.error(f"[飞书] 发送失败: {error}")
                        return PublishResult(
                            channel="feishu", success=False, error=error
                        )

        except asyncio.TimeoutError:
            return PublishResult(
                channel="feishu", success=False, error="请求超时（30s）"
            )
        except aiohttp.ClientError as e:
            return PublishResult(
                channel="feishu", success=False, error=f"网络错误: {e}"
            )

    async def send_digest(
        self,
        chat_id: str | None = None,
        digest_content: str | dict = "",
    ) -> PublishResult:
        """发送每日简报卡片到飞书。"""
        return await self.send_message(chat_id, digest_content)

    async def health_check(self) -> bool:
        """检查飞书 Webhook 是否可达。"""
        if not self.webhook_url:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    self.webhook_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    return resp.status < 500
        except Exception:
            return False


# ============================================================
# 统一发布入口
# ============================================================

async def publish_daily_digest(
    knowledge_dir: str = "knowledge/articles",
    date: str | None = None,
    channels: list[str] | None = None,
) -> list[PublishResult]:
    """生成每日简报并发布到所有渠道。

    Args:
        knowledge_dir: 知识条目目录路径
        date: 目标日期，默认今天
        channels: 指定渠道列表，默认全部（telegram, feishu）

    Returns:
        各渠道的发布结果列表
    """
    enabled_channels = channels or ["telegram", "feishu"]

    # 生成三种格式的简报
    digest = generate_daily_digest(knowledge_dir=knowledge_dir, date=date)

    # 初始化发布器
    publishers: dict[str, tuple[BasePublisher, str | dict]] = {}
    if "telegram" in enabled_channels:
        publishers["telegram"] = (TelegramPublisher(), digest["telegram"])
    if "feishu" in enabled_channels:
        publishers["feishu"] = (FeishuPublisher(), digest["feishu"])

    # 并发发布到所有渠道
    tasks = []
    for channel_name, (publisher, content) in publishers.items():
        tasks.append(publisher.send_digest(digest_content=content))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 处理异常结果
    final_results: list[PublishResult] = []
    for i, result in enumerate(results):
        channel = list(publishers.keys())[i]
        if isinstance(result, Exception):
            final_results.append(
                PublishResult(channel=channel, success=False, error=str(result))
            )
        else:
            final_results.append(result)

    # 记录发布日志
    success_count = sum(1 for r in final_results if r.success)
    total = len(final_results)
    logger.info(f"[发布] 完成：{success_count}/{total} 个渠道成功")

    return final_results


# ============================================================
# CLI 入口
# ============================================================

async def _main():
    """命令行入口，发布每日简报。"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    date = sys.argv[1] if len(sys.argv) > 1 else None
    channels = sys.argv[2].split(",") if len(sys.argv) > 2 else None

    results = await publish_daily_digest(date=date, channels=channels)

    print("\n发布结果：")
    for r in results:
        status = "✅" if r.success else "❌"
        print(f"  {status} {r.channel}: {r.message_id or r.error}")


if __name__ == "__main__":
    asyncio.run(_main())
