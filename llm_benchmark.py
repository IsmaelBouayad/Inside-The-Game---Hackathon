"""Benchmark LLM sur 20 épisodes réels pour mesurer pass@1, pass@2 et latence médiane."""
import asyncio
import json
import os
import time
import statistics
import argparse
from pipeline import generate_episode_narrative

BENCH_EPISODES = [
    {"minute": 57, "type": "High Press", "status": "ENTERED", "team": "Meteor City", "victim": "Nova FC", "trigger_event_ids": [f"EVT-m_42-{i:04d}" for i in range(1150, 1155)], "stats": {"pass_acc": 0.50, "def_actions": 8, "n_passes": 8}},
    {"minute": 62, "type": "High Press", "status": "EXITED", "team": "Meteor City", "victim": "Nova FC", "trigger_event_ids": [f"EVT-m_42-{i:04d}" for i in range(1260, 1265)], "stats": {"pass_acc": 0.90, "def_actions": 1, "n_passes": 10}},
    {"minute": 48, "type": "High Press", "status": "ENTERED", "team": "Nova FC", "victim": "Meteor City", "trigger_event_ids": [f"EVT-m_12-{i:04d}" for i in range(950, 955)], "stats": {"pass_acc": 0.45, "def_actions": 9, "n_passes": 7}},
    {"minute": 54, "type": "High Press", "status": "EXITED", "team": "Nova FC", "victim": "Meteor City", "trigger_event_ids": [f"EVT-m_12-{i:04d}" for i in range(1080, 1085)], "stats": {"pass_acc": 0.85, "def_actions": 2, "n_passes": 9}},
] * 5 # 20 épisodes

async def run_llm_benchmark(model: str = "llama3.2", language: str = "English"):
    print(f"🧠 Lancement du benchmark LLM sur 20 épisodes [{model} | {language}]...")
    latencies = []
    pass_at_1 = 0
    pass_at_2 = 0
    fallbacks = 0

    for i, ep in enumerate(BENCH_EPISODES):
        t0 = time.monotonic()
        res = await generate_episode_narrative(
            f"bench_{i}", ep, [], force_live=True, language=language, model_name=model
        )
        lat = round(time.monotonic() - t0, 2)
        latencies.append(lat)
        
        rejections = res.get("rejection_history", [])
        if not res.get("is_fallback"):
            if len(rejections) == 0:
                pass_at_1 += 1
                pass_at_2 += 1
            else:
                pass_at_2 += 1
        else:
            fallbacks += 1
        print(f"  Episode {i+1:02d}/20 -> {'PASS@1' if len(rejections)==0 and not res.get('is_fallback') else ('PASS@2' if not res.get('is_fallback') else 'FALLBACK')} in {lat}s")

    print(f"\n--- RÉSULTATS BENCHMARK LLM ({model} - {language}) ---")
    print(f"Pass@1 : {(pass_at_1/20)*100:.1f}% ({pass_at_1}/20)")
    print(f"Pass@2 (Taux final vérifié) : {(pass_at_2/20)*100:.1f}% ({pass_at_2}/20)")
    print(f"Replis sur gabarit : {fallbacks}/20")
    print(f"Latence médiane : {statistics.median(latencies):.2f}s (Min: {min(latencies):.2f}s, Max: {max(latencies):.2f}s)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="llama3.2")
    parser.add_argument("--lang", default="English")
    args = parser.parse_args()
    asyncio.run(run_llm_benchmark(args.model, args.lang))
