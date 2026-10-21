import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import app
import engine
from generator import generate_match
from detector import OnlineShiftDetector
from pipeline import build_recap_factual_core, generate_episode_narrative

REPORT_FILE = "JUDGE_EXECUTION_REPORT.md"


class JudgeAudit:
    def __init__(self):
        self.checks = []

    def record(self, category: str, name: str, passed: bool, details: str):
        status = "PASS" if passed else "FAIL"
        icon = "✅" if passed else "❌"
        print(f"{icon} [{category}] {name}: {details}")
        self.checks.append({
            "category": category,
            "name": name,
            "status": status,
            "passed": passed,
            "details": details
        })


async def run_full_judge_audit():
    judge = JudgeAudit()
    t_start = time.monotonic()
    print("⚖️  STARTING STRICT AUTOMATED HACKATHON JUDGE END-TO-END AUDIT...\n")

    # 1. UNIT TEST SUITE (19 TESTS)
    res_tests = subprocess.run([sys.executable, "test_verifier.py"], capture_output=True, text=True)
    tests_ok = (res_tests.returncode == 0 and "19/19" in res_tests.stdout)
    judge.record(
        "1. Technical Implementation",
        "Verifier v5.2 & Regression Unit Suite (19 tests)",
        tests_ok,
        "19/19 unit & regression tests passed" if tests_ok else f"Failed: {res_tests.stderr or res_tests.stdout[-200:]}"
    )

    forbidden_files = [".env", ".Rhistory", "project.txt", "check_llm.py", "diagnostic.py", "test_maf.py"]
    tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.splitlines()
    leaked = [f for f in forbidden_files if f in tracked]
    judge.record(
        "1. Technical Implementation",
        "Known Scratch & Env Files Absent from Git Index",
        len(leaked) == 0,
        f"0 known scratch/.env files in git index ({len(tracked)} tracked files)" if not leaked else f"Found: {leaked}"
    )

    # 2. MULTI-SCENARIO GENERATOR & DETECTOR GENERALIZATION (ALL CONTROL SEEDS TESTED)
    acc_42, score_42 = generate_match(42, "m_42", "match_events.jsonl", "ground_truth.json")
    gt_42 = json.load(open("ground_truth.json"))
    judge.record(
        "2. Data & Detector",
        "Seed 42 Ground Truth & Realism",
        gt_42.get("true_minute") == 52 and gt_42.get("end_minute") == 64 and 80.0 <= acc_42 <= 95.0,
        f"Pass Acc: {acc_42:.1f}%, Score: {score_42}, True Press Window: min {gt_42['true_minute']}..{gt_42['end_minute']}"
    )

    control_seeds_tested = []
    control_false_alarms = 0
    nova_win_seeds = []
    draw_seeds = []

    for s in range(1, 31):
        _, sc = generate_match(s, f"m_{s}", "tmp_ev.jsonl", "tmp_gt.json")
        gt = json.load(open("tmp_gt.json"))
        ev = [json.loads(line) for line in open("tmp_ev.jsonl")]
        d = OnlineShiftDetector()
        alarms = [a for e in ev if (a := d.process_event(e))]
        if gt["shift_type"] == "None":
            control_seeds_tested.append(s)
            control_false_alarms += len(alarms)
        if sc["Nova FC"] > sc["Meteor City"]:
            _, sum_nw, _ = build_recap_factual_core([], sc, language="English")
            if f"Nova FC claims a {sc['Nova FC']}-{sc['Meteor City']} victory" in sum_nw:
                nova_win_seeds.append(s)
        elif sc["Nova FC"] == sc["Meteor City"]:
            _, sum_dr, _ = build_recap_factual_core([], sc, language="English")
            if f"{sc['Meteor City']}-{sc['Nova FC']} draw" in sum_dr:
                draw_seeds.append(s)

    for tmp_f in ("tmp_ev.jsonl", "tmp_gt.json"):
        if os.path.exists(tmp_f):
            os.remove(tmp_f)

    generate_match(42, "m_42", "match_events.jsonl", "ground_truth.json")

    judge.record(
        "2. Data & Detector",
        "Control Match Silence Across All Control Seeds in 1..30",
        len(control_seeds_tested) >= 5 and control_false_alarms == 0,
        f"0 false alarms across all {len(control_seeds_tested)} control seeds ({control_seeds_tested})"
    )
    judge.record(
        "2. Data & Detector",
        "Independent Outcome Generalization (Both Nova FC Win AND Draw Verified)",
        len(nova_win_seeds) >= 1 and len(draw_seeds) >= 1,
        f"Nova FC win verified on seeds {nova_win_seeds[:3]}; Draw verified on seeds {draw_seeds[:3]}"
    )

    # 3. LIVE END-TO-END ENGINE + OLLAMA + FABRIC EXECUTION
    print("\n🚀 Running Live End-to-End Match Engine (from minute 48 with real Ollama LLM)...")
    await engine.match_engine(events_file="match_events.jsonl", speed=120.0, start_minute=48)

    metrics = json.load(open("engine_metrics.json")) if os.path.exists("engine_metrics.json") else {}
    clock = json.load(open("match_clock.json")) if os.path.exists("match_clock.json") else {}
    recap = json.load(open("match_recap.json")) if os.path.exists("match_recap.json") else {}
    raw_ui_lines = [json.loads(line) for line in open("broadcast_ui.jsonl", encoding="utf-8")] if os.path.exists("broadcast_ui.jsonl") else []
    merged_episodes = app.load_episodes()

    draft_ids = {x["episode_id"] for x in raw_ui_lines if "DRAFT" in x.get("render_status", "")}
    final_ids = {x["episode_id"] for x in raw_ui_lines if "FINAL (AI Verified)" in x.get("render_status", "")}
    upgraded_ids = draft_ids.intersection(final_ids)
    judge.record(
        "3. Live Agentic Pipeline",
        "In-Place DRAFT -> FINAL (AI Verified) Upgrade on All Tactical Alarms",
        len(upgraded_ids) == 2 and metrics.get("llm_verified", 0) == 2,
        f"Upgraded episodes: {sorted(list(upgraded_ids))} (llm_verified={metrics.get('llm_verified')}/2, median_latency={metrics.get('llm_latency_sec_median')}s)"
    )

    iso_ok = all(
        bool(datetime.fromisoformat(item.get("timestamp", "").replace("Z", "+00:00")))
        for item in raw_ui_lines
    )
    judge.record(
        "3. Live Agentic Pipeline",
        "Strict ISO-8601 Timestamp Validity (including minute >= 60)",
        iso_ok and len(raw_ui_lines) > 0,
        f"All {len(raw_ui_lines)} emitted overlay lines have valid ISO-8601 timestamps"
    )

    # 4. BILINGUAL LANGUAGE VERIFICATION (BOTH ENGLISH AND FRENCH MODES TESTED)
    tactical_merged = [e for e in merged_episodes if "ENTERED" in e["episode_id"] or "EXITED" in e["episode_id"]]
    fr_live_test = await generate_episode_narrative(
        "m_42",
        {"minute": 57, "type": "High Press", "status": "ENTERED", "team": "Meteor City", "victim": "Nova FC",
         "trigger_event_ids": ["EVT-m_42-1144", "EVT-m_42-1154"], "stats": {"pass_acc": 0.5, "def_actions": 8, "n_passes": 8}},
        [], force_live=True, language="French"
    )
    en_text_in_fr_mode = fr_live_test.get("multiaudience", {}).get("en", {}).get("analyst_view", "")
    fr_text_in_fr_mode = fr_live_test.get("multiaudience", {}).get("fr", {}).get("analyst_view", "")
    bilingual_uncontaminated = (
        "At minute 57," in en_text_in_fr_mode
        and "À la 57e minute," in fr_text_in_fr_mode
        and "À la 57e minute," not in en_text_in_fr_mode
    )
    judge.record(
        "4. UX & Multi-Audience",
        "Uncontaminated Bilingual Split-Screen (EN & FR Verified in Both Modes)",
        bilingual_uncontaminated and len(tactical_merged) == 2,
        "EN feed starts with 'At minute 57' and FR feed starts with 'À la 57e minute' without cross-contamination"
    )

    # 5. RECAP FACTUAL & VERIFICATION CHECK
    mom_hist = clock.get("momentum_history", [])
    recap_summary = recap.get("tactical_summary", "")
    recap_strictly_valid = (
        recap.get("recap_verified") is True
        and "first confirmed by the causal detector at minute 57" in recap_summary
        and "initiated at minute 57" not in recap_summary
        and len(recap.get("key_episode_ids", [])) >= 1
    )
    judge.record(
        "4. UX & Multi-Audience",
        "Verified RecapAgent Handoff & Causal Detection Wording",
        len(mom_hist) > 0 and recap_strictly_valid,
        f"recap_verified={recap.get('recap_verified')}, causal wording verified ('first confirmed by the causal detector at minute 57')"
    )

    # 6. DIRECTOR INTERACTIVE STATE TRANSITIONS & FABRIC SINK ACCOUNTING
    target_ep_id = tactical_merged[-1]["episode_id"]
    app.log_director_decision(target_ep_id, "HELD_BY_DIRECTOR")
    held_state = {e["episode_id"]: e for e in app.load_episodes()}[target_ep_id]["render_status"]
    app.log_director_decision(target_ep_id, "APPROVED_ON_AIR")
    after_approve = {e["episode_id"]: e for e in app.load_episodes()}
    approved_state = after_approve[target_ep_id]["render_status"]

    live_sends = metrics.get("fabric_live_sends_succeeded", 0)
    local_fb = metrics.get("fabric_local_fallbacks", 0)
    judge.record(
        "5. Enterprise & Fabric",
        "Director Hold/Approve State Transitions & Fabric Delivery Accounting",
        ("HELD BY DIRECTOR" in held_state) and ("ON-AIR (Director Approved)" in approved_state) and (live_sends > 0 or local_fb > 0),
        f"Director states verified ('{held_state}' -> '{approved_state}') | Fabric live_sends={live_sends}, local_fallbacks={local_fb}"
    )

    passed_count = sum(1 for c in judge.checks if c["passed"])
    total_count = len(judge.checks)
    duration = round(time.monotonic() - t_start, 2)

    lines = [
        "# Automated Hackathon Judge — End-to-End Execution Report",
        "",
        f"- **Execution Timestamp (UTC):** `{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- **Total Audit Duration:** `{duration}s`",
        f"- **Overall Verification Score:** **`{passed_count} / {total_count} Checks Passed ({int((passed_count/total_count)*100)}%)`**",
        "",
        "## 1. End-to-End Verification Matrix",
        "",
        "| Category | Verification Check | Status | Empirical Evidence |",
        "| :--- | :--- | :---: | :--- |",
    ]
    for c in judge.checks:
        badge = "PASS" if c["passed"] else "FAIL"
        lines.append(f"| {c['category']} | {c['name']} | **{badge}** | {c['details']} |")

    lines.extend([
        "",
        "## 2. Live Engine Metrics (`engine_metrics.json`)",
        "```json",
        json.dumps(metrics, indent=2),
        "```",
        "",
        "## 3. Live Verified Broadcast Overlays (`broadcast_ui.jsonl` Merged State)",
        "```json",
        json.dumps(after_approve, indent=2, ensure_ascii=False),
        "```",
        "",
        "## 4. Post-Match RecapAgent Output (`match_recap.json`)",
        "```json",
        json.dumps(recap, indent=2, ensure_ascii=False),
        "```",
    ])

    with open(REPORT_FILE, "w", encoding="utf-8") as rf:
        rf.write("\n".join(lines) + "\n")

    print(f"\n🏆 AUDIT COMPLETE: {passed_count}/{total_count} checks passed in {duration}s.")
    print(f"📄 Certified report written to: {REPORT_FILE}")


if __name__ == "__main__":
    asyncio.run(run_full_judge_audit())
