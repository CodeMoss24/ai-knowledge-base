"""RSS feed reader for AI Knowledge Base pipeline."""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)

RSS_CONFIG = Path(__file__).parent / "rss_sources.yaml"


def load_rss_sources() -> list[dict[str, Any]]:
    """Load RSS sources from YAML config."""
    if not RSS_CONFIG.exists():
        logger.warning("RSS config not found: %s", RSS_CONFIG)
        return []

    with open(RSS_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return [s for s in config.get("sources", []) if s.get("enabled", False)]


def fetch_rss_feed(url: str, limit: int) -> list[dict[str, Any]]:
    """Fetch and parse a single RSS feed."""
    items = []

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url)
            response.raise_for_status()
            xml_content = response.text

        item_pattern = re.compile(r"<item>(.*?)</item>", re.DOTALL | re.IGNORECASE)
        title_pattern = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL | re.IGNORECASE)
        link_pattern = re.compile(r"<link>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</link>", re.DOTALL | re.IGNORECASE)
        desc_pattern = re.compile(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", re.DOTALL | re.IGNORECASE)
        pubdate_pattern = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL | re.IGNORECASE)

        for match in item_pattern.finditer(xml_content):
            item_xml = match.group(1)
            title = _extract_first(title_pattern, item_xml)
            link = _extract_first(link_pattern, item_xml)
            description = _extract_first(desc_pattern, item_xml)
            pubdate = _extract_first(pubdate_pattern, item_xml)

            if not title or not link:
                continue

            description = re.sub(r"<[^>]+>", "", description or "").strip()
            description = re.sub(r"\s+", " ", description)

            items.append({
                "id": f"rss-{abs(hash(link)) % (10**10)}",
                "title": title.strip(),
                "source": "rss",
                "source_url": link.strip(),
                "raw_description": description[:500] if description else "",
                "published_at": pubdate.strip() if pubdate else "",
                "collected_at": datetime.now(timezone.utc).isoformat(),
            })

            if len(items) >= limit:
                break

    except httpx.HTTPError as e:
        logger.error("RSS fetch error for %s: %s", url, e)
    except Exception as e:
        logger.error("RSS parse error for %s: %s", url, e)

    return items


def _extract_first(pattern: re.Pattern, text: str) -> str | None:
    """Extract first match from text."""
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def collect_rss(limit: int = 10) -> list[dict[str, Any]]:
    """
    Collect items from configured RSS feeds.

    Args:
        limit: Maximum items per feed

    Returns:
        List of RSS items
    """
    sources = load_rss_sources()
    if not sources:
        logger.warning("No RSS sources enabled")
        return []

    all_items: list[dict[str, Any]] = []

    for source in sources:
        url = source.get("url", "")
        name = source.get("name", url)
        logger.info("Fetching RSS: %s", name)
        items = fetch_rss_feed(url, limit)
        all_items.extend(items)
        logger.info("  -> Got %d items from %s", len(items), name)

    logger.info("RSS collection total: %d items", len(all_items))
    return all_items