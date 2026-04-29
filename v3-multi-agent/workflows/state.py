"""
LangGraph 工作流共享状态定义

遵循"报告式通信"原则：State 中的字段是结构化摘要，
而非原始数据。各 Agent 通过 State 传递分析结果而非原始素材。
"""

from typing import TypedDict


class KBState(TypedDict, total=False):
    """知识库工作流共享状态

    所有字段均为报告式摘要，各阶段节点负责聚合与提炼，
    而非传递原始数据。
    """

    sources: list[dict]
    """采集阶段输出的结构化摘要列表

    数据格式: list[{
        "source": str,      # 来源标识，如 "github-trending"
        "url": str,         # 原始链接
        "title": str,       # 标题
        "description": str, # 简短描述（≤200字）
        "stars": int | None,# 星标数（如有）
        "collected_at": str, # ISO 8601 时间
    }]

    注意：仅保留关键字段的摘要，不包含原始页面内容
    """

    analyses: list[dict]
    """分析阶段输出的结构化摘要列表

    数据格式: list[{
        "url": str,               # 对应 source 的 url
        "title": str,             # 标题
        "summary": str,           # 摘要（≥200字）
        "tags": list[str],        # 标签（英文小写，3-5个）
        "relevance_score": float, # 相关度评分（0.0-1.0）
        "highlights": list[str],  # 核心亮点（2-3条）
        "analyzed_at": str,       # ISO 8601 时间
    }]

    relevance_score < 0.6 的条目应在后续节点中被过滤
    """

    articles: list[dict]
    """整理阶段输出的最终知识条目列表（去重、格式化后）

    数据格式: list[{
        "id": str,                # 唯一标识（URL 哈希或 slug）
        "title": str,             # 标题
        "source": str,           # 来源
        "url": str,              # 原始链接
        "collected_at": str,     # 采集时间 ISO 8601
        "summary": str,          # 摘要
        "tags": list[str],       # 标签
        "relevance_score": float,# 相关度
        "highlights": list[str], # 亮点
    }]

    来源: 由 analyses 去重、规范化后生成
    """

    review_feedback: str
    """审核节点的反馈意见

    记录审核未通过的原因和改进建议，
    格式为自然语言描述。空字符串表示尚未审核或已通过。
    """

    review_passed: bool
    """审核是否通过

    - False: 需返工（通常因质量或相关性不达标）
    - True: 可进入下一阶段或结束
    """

    iteration: int
    """当前审核循环次数

    初始值为 0，每次审核不通过后 +1。
    上限为 3，达到上限后强制结束循环。
    """

    cost_tracker: dict
    """Token 用量追踪（累计）

    数据格式: {
        "prompt_tokens": int,      # 累计输入 token 数
        "completion_tokens": int,  # 累计输出 token 数
        "total_cost_yuan": float,  # 累计成本估算（元）
    }

    由 workflows/model_client.py::accumulate_usage 维护
    """
