#!/usr/bin/env python3
"""
Knowledge Entry Quality Checker

5-dimension quality scoring for knowledge entries:
- Summary Quality (25pts)
- Technical Depth (25pts)
- Format Compliance (20pts)
- Tag Precision (15pts)
- Empty Word Detection (15pts)
"""

import json
import sys
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DimensionScore:
    name: str
    score: float
    max_score: float
    detail: str = ""


@dataclass
class QualityReport:
    file_path: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    total_score: float = 0.0
    grade: str = "C"
    missing_fields: list[str] = field(default_factory=list)

    def print_report(self) -> None:
        print(f"\n{'='*60}")
        print(f"文件: {self.file_path}")
        print(f"{'='*60}")

        for ds in self.dimension_scores:
            bar_len = int(ds.score / ds.max_score * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            pct = ds.score / ds.max_score * 100
            print(f"  [{ds.name}] {ds.score:5.1f}/{ds.max_score:.0f} ({pct:5.1f}%) {bar}")
            if ds.detail:
                print(f"      {ds.detail}")

        print(f"{'='*60}")
        print(f"  总分: {self.total_score:.1f}/100  等级: {self.grade}")
        if self.missing_fields:
            print(f"  缺失字段: {', '.join(self.missing_fields)}")


BLACKLIST_CN = {
    "赋能", "抓手", "闭环", "打通", "全链路", "底层逻辑",
    "颗粒度", "对齐", "拉通", "沉淀", "强大的", "革命性的"
}

BLACKLIST_EN = {
    "groundbreaking", "revolutionary", "game-changing",
    "cutting-edge", "next-generation", "state-of-the-art",
    "world-class", "best-in-class", "disruptive", "innovative"
}

VALID_TAGS = {
    "agent", "llm", "large-language-model", "rag", "tool-use",
    "code-generation", "agentic", "multimodal", "embedding",
    "fine-tuning", "evaluation", "dataset", "framework",
    "library", "application", "api", "cli", "gui", "open-source",
    "production", "research", "tutorial", "paper", "video",
    "cloud", "self-hosted", "privacy", "security", "performance"
}


def load_entry(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [警告] 无法读取文件: {e}", file=sys.stderr)
        return {}


def check_summary(summary: str) -> DimensionScore:
    if not summary:
        return DimensionScore("摘要质量", 0.0, 25.0, "摘要为空")

    length = len(summary.strip())
    tech_keywords = {
        "api", "model", "llm", "agent", "rag", "embedding",
        "token", "fine-tune", "inference", "training", "dataset",
        "framework", "pipeline", "benchmark", "evaluation"
    }
    has_tech = sum(1 for kw in tech_keywords if kw.lower() in summary.lower())

    if length >= 50:
        base_score = 25.0
        bonus = min(has_tech * 2, 5)
        return DimensionScore("摘要质量", base_score + bonus, 25.0, f"长度{length}字,含{has_tech}个技术词(+{bonus})")
    elif length >= 20:
        base_score = 15.0 + (length - 20) * 0.5
        bonus = min(has_tech * 2, 5)
        return DimensionScore("摘要质量", base_score + bonus, 25.0, f"长度{length}字,含{has_tech}个技术词(+{bonus})")
    else:
        return DimensionScore("摘要质量", length * 0.75, 25.0, f"长度{length}字,不足20字")


def check_technical_depth(entry: dict) -> DimensionScore:
    score_val = entry.get("score")
    if score_val is None:
        return DimensionScore("技术深度", 0.0, 25.0, "缺少score字段")

    try:
        score_norm = float(score_val)
    except (TypeError, ValueError):
        return DimensionScore("技术深度", 0.0, 25.0, "score格式错误")

    mapped = (score_norm / 10.0) * 25.0
    return DimensionScore("技术深度", mapped, 25.0, f"原始score={score_val},映射后{mapped:.1f}")


def check_format_compliance(entry: dict) -> tuple[DimensionScore, list[str]]:
    required = ["id", "title", "source_url", "status", "collected_at"]
    missing = [f for f in required if not entry.get(f)]
    score_per_field = 4.0
    score = max(0, score_per_field * (5 - len(missing)))
    detail = f"完整度{5-len(missing)}/5"
    if missing:
        detail += f",缺失:{','.join(missing)}"
    return DimensionScore("格式规范", score, 20.0, detail), missing


def check_tag_precision(entry: dict) -> DimensionScore:
    tags = entry.get("tags", [])
    if not isinstance(tags, list):
        return DimensionScore("标签精度", 0.0, 15.0, "tags不是数组")

    tag_count = len(tags)
    invalid_tags = [t for t in tags if not isinstance(t, str) or not t.strip()]

    if invalid_tags:
        return DimensionScore("标签精度", 0.0, 15.0, f"无效标签:{len(invalid_tags)}个")

    if tag_count == 0:
        return DimensionScore("标签精度", 0.0, 15.0, "无标签")
    elif 1 <= tag_count <= 3:
        unknown = [t for t in tags if t.lower() not in VALID_TAGS]
        if unknown:
            score = 10.0
            detail = f"标签{tag_count}个,含{len(unknown)}非常见标签"
        else:
            score = 15.0
            detail = f"标签{tag_count}个,全为标准标签"
    else:
        unknown = [t for t in tags if t.lower() not in VALID_TAGS]
        score = max(0, 15.0 - len(unknown) * 2 - (tag_count - 3) * 3)
        detail = f"标签{tag_count}个,超过3个上限"

    return DimensionScore("标签精度", score, 15.0, detail)


def check_empty_words(summary: str) -> DimensionScore:
    if not summary:
        return DimensionScore("空洞词检测", 15.0, 15.0, "无摘要内容")

    text_lower = summary.lower()
    found_cn = [w for w in BLACKLIST_CN if w in summary]
    found_en = [w for w in BLACKLIST_EN if w.lower() in text_lower]
    found = found_cn + found_en
    count = len(found)

    if count == 0:
        return DimensionScore("空洞词检测", 15.0, 15.0, "无空洞词")
    else:
        penalty = min(count * 3, 15)
        score = max(0, 15.0 - penalty)
        return DimensionScore("空洞词检测", score, 15.0, f"检测到{count}个:{','.join(found)}")


def score_entry(path: Path) -> QualityReport:
    entry = load_entry(path)

    report = QualityReport(file_path=str(path))

    report.dimension_scores.append(check_summary(entry.get("summary", "")))

    tech_depth = check_technical_depth(entry)
    report.dimension_scores.append(tech_depth)

    fmt_score, missing = check_format_compliance(entry)
    report.dimension_scores.append(fmt_score)
    report.missing_fields = missing

    report.dimension_scores.append(check_tag_precision(entry))

    report.dimension_scores.append(check_empty_words(entry.get("summary", "")))

    report.total_score = sum(ds.score for ds in report.dimension_scores)

    if report.total_score >= 80:
        report.grade = "A"
    elif report.total_score >= 60:
        report.grade = "B"
    else:
        report.grade = "C"

    return report


def collect_files(pattern: str) -> list[Path]:
    if Path(pattern).exists():
        return [Path(pattern)]

    import fnmatch
    base = Path("knowledge/articles")
    if not base.exists():
        base = Path(".")

    pattern_path = Path(pattern)
    if pattern_path.parent != Path("."):
        return list(pattern_path.parent.glob(pattern_path.name))

    return sorted(base.glob(pattern if "*" in pattern else f"*{pattern}*.json"))


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: check_quality.py <文件路径或通配符>", file=sys.stderr)
        print("示例: check_quality.py knowledge/articles/2026-04-20-*.json", file=sys.stderr)
        print("示例: check_quality.py knowledge/articles/test-good.json", file=sys.stderr)
        sys.exit(2)

    pattern = sys.argv[1]
    files = collect_files(pattern)

    if not files:
        print(f"错误: 未找到匹配 '{pattern}' 的文件", file=sys.stderr)
        sys.exit(2)

    print(f"找到 {len(files)} 个文件待检查")

    reports: list[QualityReport] = []
    grade_counts = {"A": 0, "B": 0, "C": 0}

    for i, path in enumerate(files, 1):
        print(f"\r[{i}/{len(files)}] 正在检查: {path.name}...", end="", flush=True)
        report = score_entry(path)
        reports.append(report)
        grade_counts[report.grade] += 1

    print(f"\r{' '*60}\r", end="")

    for report in reports:
        report.print_report()

    print(f"\n{'='*60}")
    print(f"汇总: A={grade_counts['A']}, B={grade_counts['B']}, C={grade_counts['C']}")
    print(f"平均分: {sum(r.total_score for r in reports) / len(reports):.1f}/100")

    if grade_counts["C"] > 0:
        print("\n存在 C 级条目,退出码: 1")
        return 1

    print("\n全部通过,退出码: 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
