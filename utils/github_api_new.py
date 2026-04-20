"""GitHub API utilities for fetching repository information."""

import logging
import os

import requests

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

logger = logging.getLogger(__name__)


def get_repo_basic_info(owner: str, repo: str) -> dict | None:
    """Fetch basic information for a GitHub repository.

    Args:
        owner: The repository owner (user or organization).
        repo: The repository name.

    Returns:
        A dictionary containing stars, forks, description,
        or None if the request fails.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    logger.info("Fetching repository info: %s/%s", owner, repo)

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    result = {
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "description": data.get("description") or "",
    }

    logger.info(
        "Successfully fetched repo info: %s (stars=%d, forks=%d)",
        data.get("full_name", f"{owner}/{repo}"),
        result["stars"],
        result["forks"],
    )

    return result