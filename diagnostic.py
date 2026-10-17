import os
import httpx
from dotenv import load_dotenv

load_dotenv()
token = os.environ["GITHUB_TOKEN"]

body = {"model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": "Say hi in three words."}]}
h = {"Authorization": f"Bearer {token}",
     "Content-Type": "application/json",
     "Accept": "application/vnd.github+json",
     "X-GitHub-Api-Version": "2026-03-10"}

def show(label, r):
    print(f"--- {label}")
    print("status:", r.status_code, "| final url:", r.url)
    print("server:", r.headers.get("server"), "| x-github-request-id:", r.headers.get("x-github-request-id"))
    print("content-type:", r.headers.get("content-type"))
    print("body:", r.text[:300])

show("A: completion with docs headers",
     httpx.post("https://models.github.ai/inference/chat/completions", headers=h, json=body,
                timeout=30, follow_redirects=True))
show("B: model catalog",
     httpx.get("https://models.github.ai/catalog/models", headers=h, timeout=30, follow_redirects=True))
