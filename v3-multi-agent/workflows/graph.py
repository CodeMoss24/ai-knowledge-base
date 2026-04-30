"""
LangGraph 工作流定义

线性流程: collect → analyze → organize → review
条件分支: review 后根据 review_passed 判断
    - True → save → END
    - False → organize (修正后重审)
"""

from langgraph.graph import StateGraph, END

from nodes import collect_node, analyze_node, organize_node, review_node, save_node
from state import KBState


def review_router(state: KBState) -> str:
    """根据审核结果路由到不同分支"""
    if state.get("review_passed", False):
        return "save"
    return "organize"


def build_graph() -> StateGraph:
    graph = StateGraph(KBState)

    graph.add_node("collect", collect_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("organize", organize_node)
    graph.add_node("review", review_node)
    graph.add_node("save", save_node)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "organize")
    graph.add_edge("organize", "review")

    graph.add_conditional_edges(
        "review",
        review_router,
        {
            "save": "save",
            "organize": "organize",
        },
    )

    graph.add_edge("save", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    initial_state: KBState = {
        "sources": [],
        "analyses": [],
        "articles": [],
        "review_feedback": "",
        "review_passed": False,
        "iteration": 0,
        "cost_tracker": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_cost_yuan": 0.0,
        },
    }

    for event in app.stream(initial_state, stream_mode="values"):
        node_name = next(iter(event.keys()))
        node_state = event[node_name]
        print(f"\n=== {node_name} ===")
        if node_name == "collect":
            print(f"  sources count: {len(node_state.get('sources', []))}")
        elif node_name == "analyze":
            print(f"  analyses count: {len(node_state.get('analyses', []))}")
        elif node_name == "organize":
            print(f"  articles count: {len(node_state.get('articles', []))}")
        elif node_name == "review":
            print(f"  review_passed: {node_state.get('review_passed')}")
            print(f"  feedback: {node_state.get('review_feedback', '')[:100]}")
        elif node_name == "save":
            print(f"  saved articles count: {len(node_state.get('articles', []))}")
            print(f"  cost: {node_state.get('cost_tracker', {}).get('total_cost_yuan', 0)}")