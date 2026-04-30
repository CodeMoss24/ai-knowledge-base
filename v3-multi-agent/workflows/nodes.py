"""
LangGraph 工作流节点定义

五个核心节点实现采集 → 分析 → 整理 → 审核 → 保存的完整流水线。
"""

import json
import os
import urllib.request
from datetime import datetime, timezone
from typing import Any

from model_client import accumulate_usage, chat, chat_json
from state import KBState


def collect_node(state: KBState) -> dict:
    """采集节点：调用 GitHub Search API 采集 AI 相关仓库"""
    print("[collect_node] 开始采集 GitHub AI 相关仓库...")

    query = "AI OR machine-learning OR LLM OR agent AI"
    sort = "stars"
    order = "desc"
    per_page = 30

    api_url = (
        "https://api.github.com/search/repositories"
        f"?q={urllib.request.quote(query)}&sort={sort}&order={order}&per_page={per_page}"
    )

    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[collect_node] API 请求失败: {e}")
        return {"sources": [], "cost_tracker": state.get("cost_tracker", {})}

    items = data.get("items", [])
    sources = []
    for item in items:
        sources.append({
            "source": "github-trending",
            "url": item.get("html_url", ""),
            "title": item.get("name", ""),
            "description": item.get("description", "") or "",
            "stars": item.get("stargazers_count", 0),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })

    print(f"[collect_node] 采集完成，共获取 {len(sources)} 条数据")
    return {"sources": sources}


def analyze_node(state: KBState) -> dict:
    """分析节点：使用 LLM 对每条数据生成中文摘要、标签、评分"""
    print("[analyze_node] 开始分析数据...")

    sources = state.get("sources", [])
    if not sources:
        print("[analyze_node] 无待分析数据")
        return {"analyses": [], "cost_tracker": state.get("cost_tracker", {})}

    analyses = []
    total_usage = {}

    system_prompt = (
        "你是一个专业的 AI 技术分析师，擅长从技术项目中提取关键信息并生成结构化摘要。"
        "你的输出必须严格遵循 JSON 格式，不要包含任何额外文本。"
    )

    for src in sources:
        prompt = f"""请分析以下 GitHub 项目，生成结构化的技术摘要。

项目信息：
- 标题：{src['title']}
- URL：{src['url']}
- 描述：{src['description']}
- 星标数：{src['stars']}

请生成一个 JSON 对象，包含以下字段：
{{
    "url": "项目 URL",
    "title": "项目标题",
    "summary": "技术摘要（≥200字，详细描述项目核心功能、技术架构、独特之处）",
    "tags": ["标签1", "标签2", "标签3"]（英文小写，3-5个标签）,
    "relevance_score": 0.0-1.0（与 AI/LLM/Agent 领域的相关程度）,
    "highlights": ["亮点1", "亮点2", "亮点3"]（2-3条核心亮点）,
    "analyzed_at": "ISO 8601 时间戳"
}}

只返回 JSON 对象，不要包含任何解释性文字。"""

        try:
            parsed, usage = chat_json(prompt, system=system_prompt, temperature=0.3, max_tokens=1500)
            total_usage = accumulate_usage(total_usage, usage)

            if isinstance(parsed, dict):
                analyses.append(parsed)
            else:
                print(f"[analyze_node] 解析失败，跳过: {src['url']}")
        except Exception as e:
            print(f"[analyze_node] 分析失败 {src['url']}: {e}")

    print(f"[analyze_node] 分析完成，共处理 {len(analyses)} 条数据")
    return {"analyses": analyses, "cost_tracker": total_usage}


def organize_node(state: KBState) -> dict:
    """整理节点：过滤低分条目、去重、审核反馈修正"""
    print("[organize_node] 开始整理数据...")

    analyses = state.get("analyses", [])
    iteration = state.get("iteration", 0)
    review_feedback = state.get("review_feedback", "")

    articles = []
    seen_urls = set()

    for item in analyses:
        if item.get("relevance_score", 0) < 0.6:
            continue
        url = item.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        articles.append({
            "id": str(hash(url)),
            "title": item.get("title", ""),
            "source": item.get("source", "unknown"),
            "url": url,
            "collected_at": item.get("collected_at", datetime.now(timezone.utc).isoformat()),
            "summary": item.get("summary", ""),
            "tags": item.get("tags", []),
            "relevance_score": item.get("relevance_score", 0),
            "highlights": item.get("highlights", []),
        })

    if iteration > 0 and review_feedback:
        print(f"[organize_node] 检测到审核反馈，进行修正 (iteration={iteration})...")
        articles = _correct_with_feedback(articles, review_feedback, state.get("cost_tracker", {}))

    print(f"[organize_node] 整理完成，保留 {len(articles)} 条数据")
    return {"articles": articles}


def _correct_with_feedback(articles: list[dict], feedback: str, cost_tracker: dict) -> list[dict]:
    """根据审核反馈修正文章列表"""
    system_prompt = (
        "你是一个专业的 AI 技术编辑，擅长根据反馈意见修正文章内容。"
        "你的输出必须严格遵循 JSON 格式。"
    )

    prompt = f"""以下是当前的知识条目列表和审核反馈，请根据反馈进行修正。

审核反馈：
{feedback}

当前知识条目（JSON 数组）：
{json.dumps(articles, ensure_ascii=False, indent=2)}

请对每一条目进行检查和修正，返回修正后的 JSON 数组。
修正要求：
1. 摘要质量不高的请重写
2. 标签不准确的请调整
3. 分类不合理的请重新分类
4. 保持原有 URL 和采集时间不变

只返回 JSON 数组，不要包含任何解释性文字。"""

    try:
        corrected, usage = chat_json(prompt, system=system_prompt, temperature=0.3, max_tokens=3000)
        cost_tracker = accumulate_usage(cost_tracker, usage)
        if isinstance(corrected, list):
            return corrected
    except Exception as e:
        print(f"[organize_node] 修正失败: {e}")

    return articles


def review_node(state: KBState) -> dict:
    """审核节点：四维度评分，iteration >= 2 强制通过"""
    print("[review_node] 开始审核...")

    articles = state.get("articles", [])
    iteration = state.get("iteration", 0)

    if not articles:
        print("[review_node] 无待审核数据")
        return {
            "review_passed": True,
            "review_feedback": "",
            "cost_tracker": state.get("cost_tracker", {}),
        }

    if iteration >= 2:
        print("[review_node] iteration >= 2，强制通过")
        return {
            "review_passed": True,
            "review_feedback": "",
            "cost_tracker": state.get("cost_tracker", {}),
        }

    system_prompt = (
        "你是一个严格的质量审核员，从四个维度评估知识条目的质量："
        "摘要质量、标签准确、分类合理、内容一致性。"
        "你的输出必须严格遵循 JSON 格式。"
    )

    prompt = f"""请审核以下知识条目，从四个维度进行评分：

1. 摘要质量（summary_quality）：摘要是否详尽、准确、有价值
2. 标签准确（tag_accuracy）：标签是否准确反映内容
3. 分类合理（classification）：分类是否合理，条目归属是否正确
4. 一致性（consistency）：整体信息是否一致、无矛盾

知识条目：
{json.dumps(articles, ensure_ascii=False, indent=2)}

请返回以下 JSON 格式的审核结果：
{{
    "passed": true/false（综合评分 >= 0.7 视为通过）,
    "overall_score": 0.0-1.0（综合评分）,
    "feedback": "审核意见（如果未通过，说明问题和改进建议）",
    "scores": {{
        "summary_quality": 0.0-1.0,
        "tag_accuracy": 0.0-1.0,
        "classification": 0.0-1.0,
        "consistency": 0.0-1.0
    }}
}}

只返回 JSON 对象，不要包含任何解释性文字。"""

    try:
        parsed, usage = chat_json(prompt, system=system_prompt, temperature=0.3, max_tokens=2000)
        cost_tracker = accumulate_usage(state.get("cost_tracker", {}), usage)

        passed = parsed.get("passed", False)
        feedback = parsed.get("feedback", "")
        overall_score = parsed.get("overall_score", 0.0)

        print(f"[review_node] 审核完成: passed={passed}, score={overall_score:.2f}")
        return {
            "review_passed": passed,
            "review_feedback": feedback,
            "cost_tracker": cost_tracker,
        }
    except Exception as e:
        print(f"[review_node] 审核失败: {e}")
        return {
            "review_passed": False,
            "review_feedback": f"审核过程出错: {str(e)}",
            "cost_tracker": state.get("cost_tracker", {}),
        }


def save_node(state: KBState) -> dict:
    """保存节点：将 articles 写入 JSON 文件，同时更新 index.json"""
    print("[save_node] 开始保存数据...")

    articles = state.get("articles", [])
    if not articles:
        print("[save_node] 无待保存数据")
        return {"cost_tracker": state.get("cost_tracker", {})}

    base_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge", "articles")
    os.makedirs(base_dir, exist_ok=True)

    saved_ids = []
    cost_tracker = state.get("cost_tracker", {})

    for article in articles:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        slug = article.get("title", "unknown")[:50].replace(" ", "-").replace("/", "-")
        filename = f"{date_str}-{slug}.json"
        filepath = os.path.join(base_dir, filename)

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)
            saved_ids.append(article.get("id", filename))
            print(f"[save_node] 保存: {filename}")
        except Exception as e:
            print(f"[save_node] 保存失败 {filename}: {e}")

    index_path = os.path.join(base_dir, "index.json")
    index_data = {"articles": [], "updated_at": datetime.now(timezone.utc).isoformat()}

    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception:
            pass

    existing_ids = {a.get("id") for a in index_data.get("articles", [])}
    for article in articles:
        if article.get("id") not in existing_ids:
            index_data["articles"].append({
                "id": article.get("id"),
                "title": article.get("title"),
                "url": article.get("url"),
                "source": article.get("source"),
                "saved_at": datetime.now(timezone.utc).isoformat(),
            })

    index_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        print(f"[save_node] 索引更新完成，共 {len(index_data['articles'])} 条记录")
    except Exception as e:
        print(f"[save_node] 索引更新失败: {e}")

    return {"cost_tracker": cost_tracker}