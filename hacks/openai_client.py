#!/usr/bin/env python3

import json
import time
from pathlib import Path
from openai import AsyncOpenAI
import httpx
import os


def load_copilot_credentials():
    """Load GitHub Copilot credentials from .copilot.json"""
    creds_path = Path(__file__).parent.parent / ".copilot.json"

    if not creds_path.exists():
        raise FileNotFoundError(
            f"Copilot credentials not found at {creds_path}. "
            "Run 'uv run python hacks/copilot_login.py' to authenticate."
        )

    with open(creds_path, "r") as f:
        return json.load(f)


def refresh_copilot_token(creds):
    """Refresh Copilot token if needed (within 10 minutes of expiration)"""
    refresh_threshold = time.time() + (10 * 60)

    if creds["copilot_expires_at"] > refresh_threshold:
        return creds["copilot_token"]

    print("Copilot token expired or expiring soon, refreshing...")

    response = httpx.get(
        "https://api.github.com/copilot_internal/v2/token",
        headers={
            "Authorization": f"Bearer {creds['access_token']}",
            "Editor-Version": "vscode/1.102.0",
            "Copilot-Integration-Id": "vscode-chat",
            "Accept": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()

    token_data = response.json()
    creds["copilot_token"] = token_data["token"]
    creds["copilot_expires_at"] = token_data["expires_at"]

    creds_path = Path(__file__).parent.parent / ".copilot.json"
    with open(creds_path, "w") as f:
        json.dump(creds, f, indent=2)

    print("Copilot token refreshed")
    return creds["copilot_token"]


def create_openai_copilot_client():
    """Create OpenAI client using GitHub Copilot authentication"""
    print("Using GitHub Copilot with OpenAI SDK")

    if os.getenv("BUSINESS_COPILOT") == "true":
        base_url = "https://api.business.githubcopilot.com"
    else:
        base_url = "https://api.githubcopilot.com"

    creds = load_copilot_credentials()
    copilot_token = refresh_copilot_token(creds)

    return AsyncOpenAI(
        api_key=copilot_token,
        base_url=base_url,
        default_headers={
            "User-Agent": "GithubCopilot/1.342.0",
            "Editor-Version": "vscode/1.102.0",
        },
    )
