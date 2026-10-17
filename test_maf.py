import asyncio
import os
from dotenv import load_dotenv

# 1. Load the .env file
load_dotenv()

# 2. Hard-check the GitHub token
github_token = os.environ.get("GITHUB_TOKEN")
if not github_token:
    print("❌ CRITICAL ERROR: GITHUB_TOKEN is missing or .env is not loading!")
    exit(1)

# 3. Purge ghost Azure environment variables that hijack the framework
os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
os.environ.pop("AZURE_OPENAI_API_KEY", None)
os.environ.pop("AZURE_OPENAI_MODEL", None)

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

async def main():
    print("Testing Microsoft Agent Framework connection to GitHub Models...")
    
    # 4. Initialize client natively
    client = OpenAIChatClient(
        api_key=github_token,
        base_url="https://models.github.ai/inference",
        model="gpt-4o-mini"
    )
    
    agent = Agent(
        client=client,
        instructions="You are a helpful assistant. Reply in exactly five words."
    )
    
    try:
        result = await agent.run("Are you receiving this message?")
        print(f"✅ Success! Agent replied: {result.messages[-1].text}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
