"""Preflight + smoke test for Microsoft Agent Framework with GitHub Models or local Ollama.

Usage:
  python3 check_llm.py                      # GitHub Models (default)
  LLM_PROVIDER=ollama python3 check_llm.py  # local Ollama (no internet needed)
"""
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.environ.get("LLM_PROVIDER", "github").lower()
GITHUB_BASE = "https://models.github.ai/inference"
GITHUB_MODEL = os.environ.get("GITHUB_MODEL", "openai/gpt-4o-mini")
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2026-03-10",
}
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# Avoid Azure env vars hijacking the framework
for k in ("AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_MODEL"):
    os.environ.pop(k, None)


def preflight_github(token: str) -> tuple[bool, str]:
    """Check that models.github.ai is really answered by GitHub before using it."""
    try:
        r = httpx.get(
            "https://models.github.ai/catalog/models",
            headers={"Authorization": f"Bearer {token}", **GITHUB_HEADERS},
            timeout=20,
            follow_redirects=True,
        )
    except Exception as e:  # network / proxy / DNS problem
        return False, f"Cannot reach models.github.ai: {e}"
    ctype = r.headers.get("content-type", "")
    if "x-github-request-id" not in r.headers or "json" not in ctype:
        return False, (
            "models.github.ai is being answered by something that is NOT GitHub "
            f"(status {r.status_code}, content-type {ctype!r}, body {r.text[:60]!r}, "
            "no x-github-request-id header). A filter, proxy, VPN or DNS override on this "
            "network/machine is intercepting the request. Try another network (phone hotspot) "
            "or run with LLM_PROVIDER=ollama."
        )
    if r.status_code in (401, 403):
        return False, f"GitHub answered {r.status_code}: token invalid or missing 'Models: Read' permission."
    return True, "models.github.ai answered like GitHub."


def build_client():
    from agent_framework.openai import OpenAIChatCompletionClient  # Chat Completions API

    if PROVIDER == "ollama":
        return OpenAIChatCompletionClient(api_key="ollama", base_url=OLLAMA_BASE, model=OLLAMA_MODEL)

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is missing or .env is not loading.")
    ok, msg = preflight_github(token)
    print(("[preflight OK] " if ok else "[preflight FAILED] ") + msg)
    if not ok:
        sys.exit(1)
    return OpenAIChatCompletionClient(
        api_key=token,
        base_url=GITHUB_BASE,
        model=GITHUB_MODEL,
        default_headers=GITHUB_HEADERS,
    )


async def main():
    from agent_framework import Agent

    client = build_client()
    agent = Agent(client=client, instructions="You are a helpful assistant. Reply in exactly five words.")
    result = await agent.run("Are you receiving this message?")
    print(f"[{PROVIDER}] Agent replied: {result.messages[-1].text}")


if __name__ == "__main__":
    asyncio.run(main())
