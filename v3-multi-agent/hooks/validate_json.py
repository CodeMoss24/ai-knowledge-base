#!/usr/bin/env python3
"""
Knowledge Entry JSON Validator

Validates knowledge article JSON files against schema requirements.
Supports single file, multiple files, or wildcard patterns (*.json).

Usage:
    python hooks/validate_json.py <json_file> [json_file2 ...]
    python hooks/validate_json.py "knowledge/articles/*.json"
"""

import json
import sys
import re
from pathlib import Path
from typing import Any


REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
}

OPTIONAL_FIELDS: dict[str, type] = {
    "url": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
    "relevance_score": (int, float),
}

UUID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
ID_PATTERN_KBN = re.compile(r"^kb-\d{4}-\d{2}-\d{2}-\d{3}$")
ID_PATTERN_KBS = re.compile(r"^kb-\d{4}-\d{2}-\d{2}-[a-z0-9-]+$")
ID_PATTERN_OLD = re.compile(r"^[a-z]+-\d{8}-\d{3}$")
URL_PATTERN = re.compile(r"^https?://")
MIN_SUMMARY_LENGTH = 10
MIN_SCORE = 0
MAX_SCORE = 1
MAX_SCORE_OLD = 10


def validate_id(article: dict[str, Any], errors: list[str]) -> None:
    id_value = article.get("id", "")
    if not isinstance(id_value, str):
        errors.append(f"  - id must be string, got {type(id_value).__name__}")
        return
    if not any(p.match(id_value) for p in [UUID_PATTERN, ID_PATTERN_KBN, ID_PATTERN_KBS, ID_PATTERN_OLD]):
        errors.append(
            f"  - id '{id_value}' must be UUID or kb-YYYY-MM-DD-NNN or kb-YYYY-MM-DD-name format"
        )


def validate_url(article: dict[str, Any], errors: list[str]) -> None:
    url = article.get("url") or article.get("source_url", "")
    if url and not isinstance(url, str):
        errors.append(f"  - url/source_url must be string, got {type(url).__name__}")
        return
    if url and not URL_PATTERN.match(url):
        errors.append(f"  - url '{url}' must start with http:// or https://")


def validate_summary(article: dict[str, Any], errors: list[str]) -> None:
    summary = article.get("summary", "")
    if summary and not isinstance(summary, str):
        errors.append(f"  - summary must be string, got {type(summary).__name__}")
        return
    if summary and len(summary) < MIN_SUMMARY_LENGTH:
        errors.append(
            f"  - summary must be at least {MIN_SUMMARY_LENGTH} characters, got {len(summary)}"
        )


def validate_tags(article: dict[str, Any], errors: list[str]) -> None:
    tags = article.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append(f"  - tags must be list, got {type(tags).__name__}")


def validate_optional_fields(article: dict[str, Any], errors: list[str]) -> None:
    score = article.get("relevance_score") or article.get("score")
    if score is not None:
        if not isinstance(score, (int, float)):
            errors.append(f"  - score must be number, got {type(score).__name__}")
        elif not (MIN_SCORE <= score <= MAX_SCORE) and not (1 <= score <= MAX_SCORE_OLD):
            errors.append(
                f"  - score must be between {MIN_SCORE} and {MAX_SCORE} (or 1-{MAX_SCORE_OLD} for legacy), got {score}"
            )


def validate_article(path: Path) -> tuple[bool, list[str]]:
    skip_names = {"index.json", "test-good.json", "test-bad.json"}
    if path.name in skip_names:
        return True, []

    errors: list[str] = []

    try:
        content = path.read_text(encoding="utf-8")
        article = json.loads(content)
    except json.JSONDecodeError as e:
        return False, [f"  - JSON parse error: {e}"]
    except Exception as e:
        return False, [f"  - Read error: {e}"]

    if not isinstance(article, dict):
        return False, ["  - Root must be JSON object, not array or other type"]

    if "items" in article:
        return True, []

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in article:
            errors.append(f"  - Missing required field: {field}")
        elif not isinstance(article[field], expected_type):
            errors.append(
                f"  - Field '{field}' must be {expected_type.__name__}, "
                f"got {type(article[field]).__name__}"
            )

    if "id" in article and isinstance(article["id"], str):
        validate_id(article, errors)

    if article.get("url") or article.get("source_url"):
        validate_url(article, errors)

    if "summary" in article:
        validate_summary(article, errors)

    if "tags" in article:
        validate_tags(article, errors)

    validate_optional_fields(article, errors)

    return len(errors) == 0, errors


def expand_paths(paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for p in paths:
        path = Path(p)
        if "*" in p:
            result.extend(sorted(path.parent.glob(path.name)) if path.is_dir() else sorted(Path(".").glob(p)))
        elif path.exists():
            result.append(path)
    return [p for p in result if p.is_file() and p.suffix == ".json"]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python hooks/validate_json.py <json_file> [json_file2 ...]")
        print("       python hooks/validate_json.py 'knowledge/articles/*.json'")
        sys.exit(1)

    paths = expand_paths(sys.argv[1:])

    if not paths:
        print("No JSON files found.")
        sys.exit(1)

    total = 0
    passed = 0
    failed = 0
    all_errors: dict[str, list[str]] = {}

    for path in paths:
        total += 1
        valid, errors = validate_article(path)
        if valid:
            passed += 1
            print(f"  OK  {path}")
        else:
            failed += 1
            all_errors[str(path)] = errors
            print(f"FAIL {path}")

    print()
    print("=" * 60)

    if failed > 0:
        print(f"\nValidation FAILED: {failed}/{total} file(s) had errors\n")
        for path_str, errors in all_errors.items():
            print(f"\n{path_str}:")
            for err in errors:
                print(err)
        print()
        print(f"Summary: {passed} passed, {failed} failed, {total} total")
        sys.exit(1)
    else:
        print(f"\nValidation PASSED: all {total} file(s) are valid")
        sys.exit(0)


if __name__ == "__main__":
    main()
