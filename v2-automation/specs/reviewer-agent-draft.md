# 数据质量审核 Agent（Reviewer）· 毛坯设计稿

## 我想让它干什么？
在知识库流水线中，对每一步的关键产出进行质量把关。
具体检查点：
- 在 Collector 之后，检查 raw 数据的完整性和格式。
- 在 Analyzer 之后，检查分析结果的深度和评分合理性。
- 在 Organizer 之后，检查最终入库条目的规范性。

## 目前困惑的地方（用 ? 标记）
- ? 如果某一步审核不通过，是直接终止流水线，还是降级继续？
- ? 审核标准应该写死在角色文件里，还是单独放在一个配置文件中？
- ? Reviewer 应该是一个通用 Agent（通过参数指定检查哪个环节），还是拆成三个专用 Agent（RawReviewer, AnalysisReviewer, ArticleReviewer）？
- ? 审核结果应该输出到哪里？是返回给主 Agent 展示，还是写入日志文件？
- ? 权限上，Reviewer 需要 Write 权限吗？比如修正明显的格式错误？

## 我期望的协作流程
Collector → Reviewer(raw) → Analyzer → Reviewer(analysis) → Organizer → Reviewer(article) → 完成
如果任何一步审核失败，主 Agent 收到失败信号，停止后续步骤并报告原因。

## 输出格式期望
{
  "stage": "raw" | "analysis" | "article",
  "passed": true | false,
  "issues": ["问题1", "问题2"],
  "recommendation": "继续/重试/终止"
}