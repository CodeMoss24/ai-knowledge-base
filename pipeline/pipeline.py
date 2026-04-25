"""Knowledge Base Automation Pipeline.

Four-step pipeline: Collect -> Analyze -> Organize -> Save
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from model_client import chat_with_retry

BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "knowledge" / "raw"
ARTICLES_DIR = BASE_DIR / "knowledge" / "articles"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Knowledge Base Pipeline")
    parser.add_argument(
        "--sources",
        type=str,
        default="github,rss",
        help="Comma-separated sources: github,rss (default: github,rss)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of items to collect per source (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without saving files or calling LLM",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Only collect data, skip analysis and organization",
    )
    return parser.parse_args()


class CollectStep:
    """Step 1: Collect AI-related content from various sources."""

    GITHUB_API = "https://api.github.com"
    RSS_FEEDS = [
        "https://hnrss.org/frontpage",
        "https://feeds.feedburner.com/oreilly/radar",
    ]

    def __init__(self, limit: int, dry_run: bool, verbose: bool):
        self.limit = limit
        self.dry_run = dry_run
        self.verbose = verbose
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def run(self, sources: list[str]) -> list[dict[str, Any]]:
        items = []
        if "github" in sources:
            items.extend(self._collect_github())
        if "rss" in sources:
            items.extend(self._collect_rss())
        logger.info("Collected %d items total", len(items))
        return items

    def _collect_github(self) -> list[dict[str, Any]]:
        query = "AI OR machine-learning OR LLM OR GPT OR neural-network"
        url = f"{self.GITHUB_API}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": min(self.limit, 100),
        }
        headers = {"Accept": "application/vnd.github.v3+json"}

        try:
            if self.dry_run:
                logger.info("[DRY RUN] Would fetch GitHub: %s %s", url, params)
                return []
            response = self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            items = []
            for repo in data.get("items", [])[: self.limit]:
                items.append({
                    "id": f"github-{repo['id']}",
                    "title": repo.get("name", ""),
                    "description": repo.get("description") or "",
                    "url": repo.get("html_url", ""),
                    "source": "github",
                    "source_url": repo.get("html_url", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language") or "unknown",
                    "collected_at": datetime.now(timezone.utc).isoformat(),
                })
            logger.info("Collected %d GitHub repos", len(items))
            return items
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error: %s", e)
            return []

    def _collect_rss(self) -> list[dict[str, Any]]:
        items = []
        for feed_url in self.RSS_FEEDS:
            try:
                if self.dry_run:
                    logger.info("[DRY RUN] Would fetch RSS: %s", feed_url)
                    continue
                response = self.client.get(feed_url)
                response.raise_for_status()
                feed_items = self._parse_rss(response.text, feed_url)
                items.extend(feed_items)
            except Exception as e:
                logger.error("RSS fetch error for %s: %s", feed_url, e)
        logger.info("Collected %d RSS items", len(items))
        return items

    def _parse_rss(self, xml_content: str, source_url: str) -> list[dict[str, Any]]:
        items = []
        item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
        title_pattern = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE)
        link_pattern = re.compile(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", re.DOTALL | re.IGNORECASE)
        desc_pattern = re.compile(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL | re.IGNORECASE)
        pubdate_pattern = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL | re.IGNORECASE)

        for match in item_pattern.finditer(xml_content):
            item_xml = match.group(1)
            title = self._extract_first(title_pattern, item_xml)
            link = self._extract_first(link_pattern, item_xml)
            description = self._extract_first(desc_pattern, item_xml)
            pubdate = self._extract_first(pubdate_pattern, item_xml)

            if not title or not link:
                continue

            description = re.sub(r"<[^>]+>", "", description or "").strip()
            description = re.sub(r"\s+", " ", description)

            items.append({
                "id": f"rss-{hash(link)}",
                "title": title.strip(),
                "description": description[:500] if description else "",
                "url": link.strip(),
                "source": "rss",
                "source_url": link.strip(),
                "published_at": pubdate.strip() if pubdate else None,
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })
        return items[: self.limit]

    def _extract_first(self, pattern: re.Pattern, text: str) -> str | None:
        match = pattern.search(text)
        return match.group(1).strip() if match else None

    def save_raw(self, items: list[dict[str, Any]], source: str) -> Path | None:
        if self.dry_run:
            return None
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = RAW_DIR / f"{source}-{date_str}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"source": source, "collected_at": datetime.now(timezone.utc).isoformat(), "items": items}, f, ensure_ascii=False, indent=2)
        logger.info("Saved raw data to %s", filepath)
        return filepath


class AnalyzeStep:
    """Step 2: Analyze content with LLM - summary, score, tags."""

    SYSTEM_PROMPT = """You are an AI content analyzer. Analyze the provided content and respond with a JSON object containing:
- summary: A concise Chinese summary (2-3 sentences)
- relevance_score: A float between 0.0 and 1.0 indicating AI/ML relevance
- tags: Array of lowercase tags (English, hyphenated)

Be critical and rate relevance_score honestly. Only rate >= 0.6 if truly AI/ML/LLM related."""

    USER_TEMPLATE = """Analyze this content:

Title: {title}
Description: {description}
URL: {url}

Respond with JSON only, no other text."""

    def __init__(self, dry_run: bool, verbose: bool):
        self.dry_run = dry_run
        self.verbose = verbose

    def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        analyzed = []
        for item in items:
            result = self._analyze_item(item)
            if result:
                analyzed.append(result)
            if self.verbose and result:
                logger.info("Analyzed: %s (score: %.2f)", item.get("title", ""), result.get("relevance_score", 0))
        logger.info("Analyzed %d items", len(analyzed))
        return analyzed

    def _analyze_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if self.dry_run:
            return {
                **item,
                "summary": "[DRY RUN] Summary would be generated here",
                "relevance_score": 0.75,
                "tags": ["dry-run", "example"],
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

        title = item.get("title", "")
        description = item.get("description", "") or item.get("text", "")
        url = item.get("url", "") or item.get("source_url", "")

        try:
            response = chat_with_retry(
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": self.USER_TEMPLATE.format(title=title, description=description, url=url)},
                ],
                max_retries=3,
            )
            content = response.content.strip()
            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                content = json_match.group(0)
            else:
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
            analysis = json.loads(content)
            return {
                **item,
                "summary": analysis.get("summary", ""),
                "relevance_score": float(analysis.get("relevance_score", 0)),
                "tags": analysis.get("tags", []),
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response for %s: %s | Response: %s", title, e, response.content[:500] if 'response' in dir() else 'N/A')
        except Exception as e:
            logger.error("Analysis error for %s: %s", title, e)
        return None


class OrganizeStep:
    """Step 3: Deduplicate, standardize format, validate."""

    MIN_SCORE = 0.6

    def __init__(self, dry_run: bool, verbose: bool):
        self.dry_run = dry_run
        self.verbose = verbose
        self._seen_urls: set[str] = set()
        self._seen_ids: set[str] = set()

    def run(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        organized = []
        for item in items:
            processed = self._process_item(item)
            if processed:
                organized.append(processed)
        logger.info("Organized %d items (passed validation)", len(organized))
        return organized

    def _process_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        item_id = item.get("id", "")
        url = item.get("url") or item.get("source_url", "")

        if item_id in self._seen_ids or url in self._seen_urls:
            if self.verbose:
                logger.info("Duplicate skipped: %s", item.get("title", ""))
            return None

        score = item.get("relevance_score", 0)
        if score < self.MIN_SCORE:
            if self.verbose:
                logger.info("Low score rejected: %s (%.2f)", item.get("title", ""), score)
            return None

        self._seen_ids.add(item_id)
        self._seen_urls.add(url)

        slug = self._generate_slug(item.get("title", item_id))
        date_str = datetime.now().strftime("%Y-%m-%d")

        return {
            "id": f"kb-{date_str}-{slug}",
            "title": item.get("title", ""),
            "source": item.get("source", "unknown"),
            "source_url": url,
            "url": url,
            "summary": item.get("summary", ""),
            "tags": item.get("tags", []),
            "relevance_score": score,
            "status": "active",
            "collected_at": item.get("collected_at", ""),
            "analyzed_at": item.get("analyzed_at", ""),
            "organized_at": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_slug(self, title: str) -> str:
        slug = re.sub(r"[^\w\s-]", "", title.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:50].strip("-")


class SaveStep:
    """Step 4: Save articles as individual JSON files."""

    def __init__(self, dry_run: bool, verbose: bool):
        self.dry_run = dry_run
        self.verbose = verbose

    def run(self, items: list[dict[str, Any]]) -> list[Path]:
        ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
        saved = []
        for item in items:
            filepath = self._save_article(item)
            if filepath:
                saved.append(filepath)
        self._update_index(saved)
        logger.info("Saved %d articles", len(saved))
        return saved

    def _save_article(self, item: dict[str, Any]) -> Path | None:
        if self.dry_run:
            logger.info("[DRY RUN] Would save: %s", item.get("id", ""))
            return None

        article_id = item.get("id", "")
        filepath = ARTICLES_DIR / f"{article_id}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False, indent=2)

        if self.verbose:
            logger.info("Saved: %s", filepath.name)
        return filepath

    def _update_index(self, saved: list[Path]):
        if self.dry_run or not saved:
            return

        index_path = ARTICLES_DIR / "index.json"
        index_data = []
        if index_path.exists():
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    index_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                index_data = []

        existing_ids = {item.get("id") for item in index_data}
        for filepath in saved:
            article_id = filepath.stem
            if article_id not in existing_ids:
                index_data.append({
                    "id": article_id,
                    "file": filepath.name,
                    "saved_at": datetime.now(timezone.utc).isoformat(),
                })

        index_data.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)


def run_pipeline(
    sources: list[str],
    limit: int,
    dry_run: bool,
    verbose: bool,
    collect_only: bool = False,
) -> None:
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Starting pipeline with sources=%s, limit=%d, dry_run=%s, collect_only=%s", sources, limit, dry_run, collect_only)

    collect = CollectStep(limit=limit, dry_run=dry_run, verbose=verbose)

    logger.info("=== Step 1: Collect ===")
    items = collect.run(sources)
    if not items:
        logger.warning("No items collected, pipeline stopped")
        return

    raw_source = sources[0] if sources else "mixed"
    collect.save_raw(items, raw_source)

    if collect_only:
        logger.info("=== Collect only mode, skipping analyze/organize/save ===")
        return

    analyze = AnalyzeStep(dry_run=dry_run, verbose=verbose)
    organize = OrganizeStep(dry_run=dry_run, verbose=verbose)
    save = SaveStep(dry_run=dry_run, verbose=verbose)

    logger.info("=== Step 2: Analyze ===")
    analyzed = analyze.run(items)
    if not analyzed:
        logger.warning("No items analyzed, pipeline stopped")
        return

    logger.info("=== Step 3: Organize ===")
    organized = organize.run(analyzed)
    if not organized:
        logger.warning("No items passed organization, pipeline stopped")
        return

    logger.info("=== Step 4: Save ===")
    saved = save.run(organized)

    logger.info("=== Pipeline Complete ===")
    logger.info("Collected: %d, Analyzed: %d, Organized: %d, Saved: %d", len(items), len(analyzed), len(organized), len(saved))


def main():
    args = parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    run_pipeline(sources, args.limit, args.dry_run, args.verbose, args.collect_only)


if __name__ == "__main__":
    main()
