import asyncio
import json
import re
import time
from agent_framework import Agent
from pipeline import (
    get_clients,
    generate_episode_narrative,
    generate_match_recap,
    build_factual_core,
    build_recap_factual_core,
    NUMBER_WORDS_REGEX,
    HALLUCINATION_TRIGGERS,
    DEFAULT_MODEL,
)

SAMPLE_EPISODES = [
    {
        "minute": 57, "type": "High Press", "status": "ENTERED",
        "team": "Meteor City", "victim": "Nova FC",
        "trigger_event_ids": ["EVT-m_42-1144", "EVT-m_42-1154"],
        "stats": {"pass_acc": 0.50, "def_actions": 8, "n_passes": 8}
    },
    {
        "minute": 62, "type": "High Press", "status": "EXITED", "exit_reason": "exhausted",
        "team": "Meteor City", "victim": "Nova FC",
        "trigger_event_ids": ["EVT-m_42-1265", "EVT-m_42-1270"],
        "stats": {"pass_acc": 0.57, "def_actions": 1, "n_passes": 14}
    }
]

SCORE = {"Meteor City": 2, "Nova FC": 0}


def strip_python_prefix(full_text: str, python_prefix: str) -> str:
    """Strictly isolates the LLM-generated text by removing the deterministic Python factual core."""
    if not full_text:
        return ""
    if python_prefix and full_text.startswith(python_prefix):
        return full_text[len(python_prefix):].strip()
    parts = full_text.split(". ", 1)
    return parts[1].strip() if len(parts) == 2 else full_text


def audit_llm_segment(llm_text: str, alarm: dict = None) -> list:
    """Audits ONLY the LLM-generated stylistic segment for rule violations."""
    errs = []
    t_clean = re.sub(r"EVT-[A-Za-z0-9_-]+", "", llm_text)
    digits = re.findall(r"\d+", t_clean)
    if digits:
        errs.append(f"Unverified digits in LLM color: {digits}")
    if re.search(NUMBER_WORDS_REGEX, t_clean.lower()):
        errs.append("Forbidden number words in LLM color")
    for h in HALLUCINATION_TRIGGERS:
        pattern = h if h.startswith(r"\b") else rf"\b{re.escape(h)}\b"
        if re.search(pattern, t_clean.lower()):
            errs.append(f"Unverified micro-action/incident: {h}")
    if alarm:
        victim = alarm["victim"].lower()
        if alarm.get("status") == "ENTERED" and re.search(rf"\b{re.escape(victim)}\b\s+(?:presses|pressing|hounds|dominates)", t_clean.lower()):
            errs.append("Role inversion")
    return errs


async def run_single_agent_baseline() -> dict:
    """Runs a real monolithic single-agent prompt on the exact same episodes (no hardcoded errors)."""
    t0 = time.monotonic()
    client = get_clients(DEFAULT_MODEL)
    mono_agent = Agent(
        client=client,
        instructions=(
            "You are a single monolithic football broadcast agent. "
            "Given the match episodes and score, write live commentary for each episode and a post-match recap."
        )
    )
    prompt = f"Episodes: {json.dumps(SAMPLE_EPISODES)}. Final Score: {json.dumps(SCORE)}. Write commentary and recap."
    res = await mono_agent.run(prompt)
    duration = round(time.monotonic() - t0, 2)
    raw_out = res.text or ""
    violations = audit_llm_segment(raw_out)
    return {
        "duration_sec": duration,
        "violations_count": len(violations),
        "violations_detail": violations,
        "raw_excerpt": raw_out[:160].replace("\n", " "),
    }


async def run_multi_agent_pipeline() -> dict:
    """Runs the decoupled ExplainerAgent -> Verifier -> RecapAgent pipeline and audits ONLY LLM color segments."""
    t0 = time.monotonic()
    verified_eps = []
    violations_all = []
    llm_verified_count = 0

    for ep in SAMPLE_EPISODES:
        out = await generate_episode_narrative("m_42", ep, [], force_live=True, language="English")
        verified_eps.append(out)
        if not out.get("is_fallback"):
            llm_verified_count += 1
        py_core = build_factual_core(ep, "English")
        llm_only_color = strip_python_prefix(out.get("analyst_view", ""), py_core)
        fan_txt = out.get("fan_view", "")
        violations_all.extend(audit_llm_segment(f"{llm_only_color} {fan_txt}", alarm=ep))

    recap = await generate_match_recap("m_42", verified_eps, SCORE, language="English")
    _, recap_py_core, _ = build_recap_factual_core(verified_eps, SCORE, language="English")
    recap_llm_color = strip_python_prefix(recap.get("tactical_summary", ""), recap_py_core)
    violations_all.extend(audit_llm_segment(recap_llm_color))

    duration = round(time.monotonic() - t0, 2)
    return {
        "duration_sec": duration,
        "episodes_evaluated": len(SAMPLE_EPISODES),
        "llm_verified_episodes": llm_verified_count,
        "recap_verified": bool(recap.get("recap_verified")),
        "violations_count": len(violations_all),
        "violations_detail": violations_all,
        "handoff_count": recap.get("agent_handoff_count", 0),
    }


async def main():
    print("🔬 RUNNING MEASURED COMPARISON: SINGLE-AGENT MONOLITHIC vs MULTI-AGENT PIPELINE...")
    mono = await run_single_agent_baseline()
    multi = await run_multi_agent_pipeline()

    report_md = f"""## ⚖️ Measured Architecture Comparison: Single-Agent vs Multi-Agent Pipeline (N = 2 Tactical Episodes + 1 Post-Match Recap)

Both configurations were executed live against local `{DEFAULT_MODEL}` on the exact same Seed 42 tactical episodes (`m_42_min57_ENTERED`, `m_42_min62_EXITED`). For the multi-agent pipeline, the deterministic Python factual core was stripped prior to auditing so that **only LLM-generated stylistic segments** were evaluated:

| Configuration | Execution Protocol | Measured Rule Violations | Live Episodes Validated | Recap Handoff Verified | Total Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Single-Agent Monolithic** | 1 unconstrained agent prompt (episodes + recap combined) | **{mono['violations_count']} violation(s)** ({', '.join(mono['violations_detail'][:2]) or 'none'}) | Unstructured text (no schema) | No structured ledger | `{mono['duration_sec']}s` |
| **Inside The Game Multi-Agent** | **ExplainerAgent ➔ Verifier ➔ RecapAgent** | **{multi['violations_count']} violation(s)** | **`{multi['llm_verified_episodes']} / {multi['episodes_evaluated']}`** | **`{multi['recap_verified']}` (`{multi['handoff_count']}` eps)** | `{multi['duration_sec']}s` |
"""
    print("\n" + report_md)
    with open("BENCHMARK_MULTIAGENT.md", "w", encoding="utf-8") as f:
        f.write(report_md)


if __name__ == "__main__":
    asyncio.run(main())
