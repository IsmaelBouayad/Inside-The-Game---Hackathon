import asyncio
from agent_framework import Agent, Message
from agent_framework.openai import OpenAIChatCompletionClient
from openai import AsyncOpenAI

async def main():
    print("🚀 Initializing Microsoft Agent Framework with Local Ollama...")
    
    # 1. Native OpenAI client pointed at Ollama's local server
    # Ollama requires a dummy api_key (e.g., "ollama") to satisfy the OpenAI SDK
    native_client = AsyncOpenAI(
        api_key="ollama",
        base_url="http://localhost:11434/v1"
    )
    
    # 2. MAF Wrapper targeting the local model
    # Change "llama3.2" to "phi" if you are using Microsoft's Phi model
    client = OpenAIChatCompletionClient(
        model="llama3.2", 
        async_client=native_client
    )
    
    print("\n--- TEST : Agent Framework Wrapper ---")
    try:
        agent = Agent(
            client=client,
            instructions="You are a helpful assistant. Reply in exactly five words."
        )
        res = await agent.run("Are you receiving this message?")
        print("✅ Success! Agent replied:", res.text)
    except Exception as e:
        print("❌ Connection Failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
