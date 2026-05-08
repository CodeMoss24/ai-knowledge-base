"""daily_digest.py — 每日简报独立推送入口

本脚本只做一件事：把知识库里最新的文章按简报格式发出去。

与 pipeline.pipeline 的区别：
- pipeline.pipeline: 完整流水线（采集→分析→整理→审核→保存→发布）
- daily_digest.py:   只做发布（读现有 articles，生成简报，推送）

使用场景：
- 今天已经跑过 pipeline 但想重发一次
- 想只测试分发层，不动知识库
- 定时任务想和采集解耦
"""

import asyncio
import logging
import os
import sys

# 确保可以 import distribution / workflows
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print("=" * 50)
    print("  AI 知识库 — 每日简报推送")
    print("=" * 50)

    from distribution.publisher import publish_daily_digest

    # 调用统一发布入口：formatter 生成简报 + 并发推送到所有渠道
    results = await publish_daily_digest()

    if not results:
        print("\n⚠️  没有可发布的内容（knowledge/articles/ 为空或全部低于阈值）")
        return

    success = sum(1 for r in results if r.success)
    print(f"\n推送结果: {success}/{len(results)} 个渠道成功")
    for r in results:
        status = "✅" if r.success else "❌"
        detail = r.message_id if r.success else r.error
        print(f"  {status} {r.channel}: {detail}")


if __name__ == "__main__":
    asyncio.run(main())
