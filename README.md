# Inside The Game — Edge AI Tactical Broadcast Pipeline

[![InsideTheGame CI](https://github.com/IsmaelBouayad/Inside-The-Game---Hackathon/actions/workflows/ci.yml/badge.svg)](https://github.com/IsmaelBouayad/Inside-The-Game---Hackathon/actions)

**Real-Time Tactical Momentum Shift Detection, Multi-Audience Split-Screen Overlays, and Programmatic LLM Verification with Microsoft Agent Framework & Microsoft Fabric**

---

## 1. Overview & Hackathon Track Alignment

Live football broadcasters face three strict constraints when deploying generative AI on-air: **inference latency**, **per-request cloud API cost**, and **factual hallucinations**.

**Inside The Game** solves this through a neuro-symbolic **Edge-to-Cloud hybrid architecture**:
1. **Continuous Momentum Shift Index & Causal Detector (`detector.py`):** A deterministic state machine with entry/exit hysteresis evaluates rolling spatial telemetry (`x < 33` / `x > 67`) once per completed match minute to compute a continuous Momentum Index (`[-100..+100]`), automatically pinpoint the match's **Turning Point**, and trigger **High Press** regime alarms (`ENTERED` and `EXITED`) with explicit exit cause classification (`exit_reason: "recovered"` vs `"exhausted"`).
2. **Three-Tier Broadcast Continuity (`engine.py`):**
   - **Tier 0 (Instant Goal Overlays):** 0 ms deterministic templates narrate goals live as they happen.
   - **Tier 1 (Instant Tactical DRAFT):** When a tactical alarm fires, a deterministic template is written immediately to `broadcast_ui.jsonl` so the broadcast director never waits on the LLM.
   - **Tier 2 (AI-Verified FINAL):** An asynchronous worker calls a local LLM (**Microsoft Phi-4-mini** or **Llama 3.2**) via **Microsoft Agent Framework** (`pipeline.py`). Once validated by `verify_color_commentary` (v5.1), the overlay is written to `broadcast_ui.jsonl` and upgrades the corresponding `DRAFT` in-place in the UI.
3. **Collaborative Multi-Agent Handoff (`ExplainerAgent` ──► `RecapAgent`):** At the final whistle, `generate_match_recap()` receives the structured handoff of verified live episodes from `ExplainerAgent`, constructs a dynamic factual core in Python (`build_recap_factual_core` — dynamically computing Win/Loss/Draw and actual pressing intervals without hardcoded minutes or winners), and invokes `RecapAgent` to synthesize a verified post-match tactical conclusion (`match_recap.json`).
4. **Microsoft Fabric Eventstream Sink (`fabric_sink.py`):** Streams live `ALARM`, `GOAL_TIER0`, `OVERLAY_FINAL`, `DIRECTOR_AUDIT`, `POST_MATCH_RECAP`, and `MATCH_METRICS` events to **Microsoft Fabric Eventstream** via the Azure Event Hubs SDK (`azure.eventhub.aio`), with automatic fallback to `fabric_local_fallback.jsonl` when offline or in CI.

### Official Tracks & Prize Categories Addressed
- **Track 2 — Explainable Match Intelligence (Primary):** Causal High Press regime detection (`ENTERED`/`EXITED`), continuous Momentum Shift Index, explicit `exit_reason` differentiation, and evidence-backed overlays (`cited_event_ids`).
- **Track 1 & Track 4 — Real-Time Match Narratives & Immersive Fan Experiences:** Simultaneous multi-audience split-screen rendering **English Analyst/Fan**, **French Analyste/Supporter**, and **Club-Allegiance Companion Feeds** (*Meteor City* vs *Nova FC*), plus **Human-in-the-Loop** Broadcast Director approval/hold controls audited to Microsoft Fabric.
- **Track 3 & Multi-Agent System:** Structured evidence handoff from live `ExplainerAgent` to post-match `RecapAgent`, both guarded by programmatic verification.

---

## 2. Architecture & Temporal Consistency

```text
match_events.jsonl ──► engine.py (Async Simulated Clock + Dynamic Tactical Pacing)
                          │
                          ├──► Goal Event ──► Tier-0 Goal Overlay ────────► broadcast_ui.jsonl
                          │
                          ├──► detector.py (Causal State Machine + Continuous Momentum Index)
                          │       │
                          │       └──► Alarm (ENTERED / EXITED [recovered | exhausted])
                          │               ├──► Tier-1 Instant DRAFT ──────► broadcast_ui.jsonl
                          │               ├──► fabric_sink.py ────────────► Microsoft Fabric Eventstream
                          │               └──► asyncio.Queue(maxsize=2, latest-wins)
                          │                           │
                          │                           ▼
                          │                    pipeline.py (ExplainerAgent + Verifier v5.1)
                          │                           │
                          │                           ├──► Tier-2 FINAL ──► broadcast_ui.jsonl (In-place upgrade)
                          │                           └──► Verified Episode Handoff
                          │                                       │
                          └──► Full Time ─────────────────────────┴──► RecapAgent ──► match_recap.json
```

### Handling Edge CPU Latency, Sequence Tracking & Valid ISO-8601 Timestamps
1. **Dynamic Tactical Pacing (`DYNAMIC_PACING=1`):** On a CPU-only laptop, local LLM inference takes ~9–14s. During fast-forward demos (`x60`), `engine.py` automatically slows replay to `x2` while the LLM worker is active so the verified `FINAL` overlay lands within the same tactical sequence.
2. **In-Place Sequence Upgrade (`episode_seq`):** Every episode is tracked by `episode_seq` and `episode_id`. When `llm_worker` completes verification, it writes `FINAL (AI Verified)` to `broadcast_ui.jsonl`, which `app.py` (`load_episodes()`) merges in-place over the `DRAFT` of the same `episode_id`. If a newer alarm has already fired, the older completion is marked `superseded: True` so it never overwrites a newer banner.
3. **Strict ISO-8601 Clock Arithmetic (`format_match_timestamp`):** Match minutes above 59 (e.g., minute `62`) are computed via `MATCH_KICKOFF + timedelta(minutes=minute)` (`2026-10-27T16:02:00Z`), guaranteeing strictly valid ISO-8601 timestamps across all overlays and Microsoft Fabric KQL ingestion.

---

## 3. Programmatic Verifier v5.1 (`pipeline.py` & `test_verifier.py`)

Small local models frequently hallucinate numbers, invert team roles, or invent untracked player actions. Our **"Facts by Python, Color by LLM"** architecture enforces accuracy through `build_factual_core()` and `verify_color_commentary()` (`ColorCommentaryPayload`):

1. **Deterministic Factual Core (`build_factual_core`):** Python writes the exact mathematical sentence (minute, pressing team, victim, pass accuracy percentage, singular/plural defensive action count, and `exit_reason="recovered"` vs `"exhausted"`).
2. **Event ID Whitelist & Placeholder Rejection:** Every ID in `cited_event_ids` must belong to the episode's `trigger_event_ids`. The prompt template uses `"EVT-XXXX"`, which is explicitly rejected if copied.
3. **Zero-Digit & Number-Word Rule in LLM Color:** Because Python supplies all statistics in the factual core, any digit (`\d`, including ordinals like `12th`) or number word (`fourteen`) in the LLM's `analyst_color` or `fan_view` triggers an immediate rejection and retry.
4. **Incident & Micro-Action Guardrails:** Word-boundary regex assertions reject unrecorded match incidents (`red card`, `penalty`, `injury`, `offside`, `corner`) and untracked player-position claims (`winger`, `right-back`, `clever run`, `cross`, `header`).
5. **Role-Inversion Guards:** Rejects outputs that describe the victim as the aggressor during `ENTERED` or the presser as escaping during `EXITED`.

All **16 unit and regression tests** in `test_verifier.py` (14 Verifier v5.1 stress tests + ISO-8601 timestamp validation above minute 59 + dynamic recap verification across Nova FC wins, draws, and no-press matches) run in `< 0.1s`.

---

## 4. Empirical Measurements & Benchmarks

**Hardware Environment:** Dell Latitude 5520, Intel Core i5-1145G7 (4 cores / 8 threads), 15 GB RAM, Ubuntu Linux (CPU-only local inference via Ollama).

### A. Offline Detector Calibration & Held-Out Benchmark
*Note: Thresholds are calibrated (`calibrate_detector.py`, Seeds `1..120`) and evaluated (`benchmark_detector.py`, Seeds `1001..1200`) on our synthetic match generator as a controlled non-regression benchmark.*
- **Held-Out Test Set:** 200 matches (Seeds `1001..1200`: 151 matches with High Press, 49 control matches without pressing)
- **Recall (within +12 min window):** `73.5%` (`111 / 151`), median confirmation delay: `5.0` match minutes
- **False Entries per Match (overall):** `0.04` (`1` false entry across `49` control matches)
- **Exit Timing Accuracy (within ±8 min of true end):** `103 / 111` (`92.8%`)

### B. LLM Verification Benchmark Across 60 Evaluations (`python3 llm_benchmark.py`)
20 episodes per configuration evaluated against **Verifier v5.1** (95% Wilson confidence intervals in parentheses):

| Model & Language Configuration | Pass@1 (First Try) | Pass@2 (After Rejection Retry) | Template Fallbacks | Median Latency (CPU) | Min / Max Latency |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Microsoft Phi-4-mini (English)** | `60.0%` (12/20) *(39–78%)* | **`100.0%` (20/20)** *(84–100%)* | `0 / 20` | `13.67s` | `7.19s / 24.79s` |
| **Meta Llama 3.2 (English)** | `80.0%` (16/20) *(58–92%)* | **`90.0%` (18/20)** *(70–97%)* | `2 / 20` | `9.21s` | `6.63s / 28.95s` |
| **Meta Llama 3.2 (French)** | `50.0%` (10/20) *(30–70%)* | **`75.0%` (15/20)** *(53–89%)* | `5 / 20` | `12.25s` | `6.24s / 23.71s` |

*Key Finding:* Feeding the exact programmatic rejection reason back into the retry prompt raises **Microsoft Phi-4-mini** from `60.0%` Pass@1 to **`100.0%` Pass@2** (`20/20` verified, `0` fallbacks).

### C. Deterministic Seed 42 End-to-End Trace (`python3 engine.py --start-minute 48`)
- **Ground Truth (`ground_truth.json`):** `shift_type: "High Press"`, `shift_team: "Meteor City"`, `true_minute: 52`, `end_minute: 64`. Final Score: `Meteor City 2 - 0 Nova FC` (Goals at minutes `51` and `79`).
- **Alarms Fired & Verified Overlays:**
  - `min 57 ENTERED` -> Verified in `15.01s` (`timestamp: "2026-10-27T15:57:00Z"`)
  - `min 62 EXITED [reason=exhausted]` -> Verified in `10.10s` (`timestamp: "2026-10-27T16:02:00Z"`)
- **Median Latency:** `12.55s` | **Superseded Finals:** `0` | **Fabric Delivery Mode:** `fabric_eventstream_live`

---

## 5. Known Limitations & Engineering Transparency

1. **Synthetic Telemetry Calibration:** Match events are generated by `generator.py`. Detector performance is measured on held-out seeds from this generator as a reproducible benchmark, not on proprietary optical tracking feeds.
2. **Single Tactical Regime + Continuous Momentum:** State-machine alarms target **High Press** (`ENTERED` / `EXITED`), complemented by a continuous territorial **Momentum Shift Index** (`[-100..+100]`) and **Tier-0 Goal** overlays.
3. **Scope of Programmatic Verification:** Python locks all numbers, team roles, minutes, timestamps, and `exit_reason`, and blocks digits, number words, and unrecorded incidents/positions in the LLM's color sentence. Generic team-level phrasing remains stylistic commentary.
4. **Edge CPU Latency:** On an Intel Core i5-1145G7 CPU without a discrete GPU, inference takes `9–14s`. In live `x1` broadcast time, this is near-real-time; during `x60` fast-forward demos, `DYNAMIC_PACING` slows replay to `x2` while the worker is busy.

---

## 6. Reproducible Quickstart

```bash
# 1. Install pinned dependencies
pip install -r requirements.txt

# 2. Run all 16 Verifier v5.1, ISO timestamp, and dynamic recap unit tests
python3 test_verifier.py

# 3. Generate deterministic Seed 42 match data & run offline 200-match detector benchmark
python3 generator.py --seed 42
python3 benchmark_detector.py

# 4. Launch the Broadcast Control Room UI (Terminal 1)
streamlit run app.py

# 5. Run the 75-second Demo Replay from Minute 48 (Terminal 2)
# Optional: export OLLAMA_MODEL="phi4-mini"
python3 engine.py --start-minute 48
```
