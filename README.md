# Inside The Game — Edge AI Tactical Broadcast Pipeline

**Real-Time Tactical Momentum Shift Detection, Multi-Tier Broadcast Overlays, and Programmatic LLM Verification**

---

## 1. Overview & Hackathon Track Alignment

Live football broadcasters face three constraints when deploying generative AI during a match: **inference latency**, **per-request cloud cost**, and **on-air hallucinations**.

**Inside The Game** solves this with an **Edge-to-Cloud hybrid pipeline**:
1. **Causal Spatial Detection (`detector.py`):** A deterministic state machine with entry/exit hysteresis evaluates rolling spatial telemetry (`x < 33` / `x > 67`) once per completed match minute to detect sustained **High Press** regimes (`ENTERED` and `EXITED`).
2. **Three-Tier Broadcast Delivery (`engine.py`):**
   - **Tier 0 (Instant Goal Overlays):** 0 ms deterministic templates narrate goals live as they happen.
   - **Tier 1 (Instant Tactical DRAFT):** When a tactical alarm fires, a deterministic template is written immediately to `broadcast_ui.jsonl` so the broadcast director never waits on the LLM.
   - **Tier 2 (AI-Verified FINAL):** An asynchronous worker calls a local LLM via **Microsoft Agent Framework** (`pipeline.py`). Once verified by `verify_broadcast` (v4), the overlay upgrades in-place in the UI.
3. **Post-Match Smart Summary (`RecapAgent`):** At the final whistle, a second agent synthesizes all verified episodes and goals into `match_recap.json`.
4. **Microsoft Fabric Eventstream Sink (`fabric_sink.py`):** Streams live alarms, verified overlays, and match metrics to Microsoft Fabric Eventstream via the Azure Event Hubs SDK (`azure.eventhub.aio`), with automatic fallback to `fabric_local_fallback.jsonl` when running offline or in CI.

### Official Tracks Covered
- **Track 2 — Explainable Match Intelligence (Primary):** Causal detection of High Press entry and exit regimes backed by explicit event citations (`cited_event_ids`), pass accuracy drops, and defensive action counts.
- **Track 1 — Real-Time Match Narratives:** Dual-tone output (`analyst_view` and `fan_view`) with configurable language (`BROADCAST_LANG`) and fan persona (`BROADCAST_PERSONA`).
- **Track 3 — Automated Recaps and Smart Summaries:** End-of-match structured tactical recap (`match_recap.json`) generated exclusively from verified match episodes.

---

## 2. Architecture & Temporal Consistency

```text
match_events.jsonl ──► engine.py (Async Simulated Clock + Dynamic Tactical Pacing)
                          │
                          ├──► Goal Event ──► Tier-0 Goal Overlay ──► broadcast_ui.jsonl
                          │
                          ├──► detector.py (Causal State Machine, Window + Hysteresis)
                          │       │
                          │       └──► Alarm (ENTERED / EXITED)
                          │               ├──► Tier-1 Instant DRAFT ──► broadcast_ui.jsonl
                          │               ├──► fabric_sink.py ────────► Microsoft Fabric Eventstream
                          │               └──► asyncio.Queue(maxsize=2, latest-wins)
                          │                           │
                          │                           ▼
                          │                    pipeline.py (ExplainerAgent + Verifier v4)
                          │                           │
                          │                           └──► Tier-2 FINAL (AI Verified)
                          │
                          └──► Full Time ───► RecapAgent ─────────────► match_recap.json
```

### Handling Edge CPU Latency vs. Replay Speed
On a laptop CPU without a dedicated GPU, local LLM inference takes ~13 seconds per episode. At a `x60` replay speed (1 match minute = 1 real second), an unthrottled stream would advance 13 match minutes before the LLM finishes.
To prevent stale overlays from overwriting newer match states:
1. **Dynamic Tactical Pacing (`DYNAMIC_PACING=1`):** The engine streams normal play at `x60`, and automatically slows down to `x2` while the LLM worker processes a tactical alarm, ensuring the verified `FINAL` overlay lands within the same tactical sequence.
2. **Sequence Tracking (`episode_seq`):** Every episode is indexed by sequence ID. In `app.py`, a `FINAL` overlay updates its corresponding `DRAFT` in-place. If a newer alarm has already occurred, the older completion is flagged as `superseded: True` (`FINAL (AI Verified - Historical / Superseded)`) and never overwrites the active banner.

---

## 3. Programmatic Verifier v4 (`pipeline.py` & `test_verifier.py`)

Small local models frequently hallucinate statistics, invert team roles, or copy prompt examples. Instead of using a second LLM to verify the first, Python enforces deterministic facts before calling the LLM and validates the output with four checks in `verify_broadcast`:

1. **Event ID Whitelist & Placeholder Rejection:** Every ID in `cited_event_ids` must belong to the alarm's `trigger_event_ids`. The prompt template uses a placeholder (`"EVT-XXXX"`), which is explicitly rejected if copied.
2. **Dual-Team Presence:** `analyst_view` must explicitly name both the pressing team (`alarm["team"]`) and the victim (`alarm["victim"]`).
3. **Role-Inversion & State-Contradiction Guards:** Regex assertions reject narratives that credit the victim with pressing during `ENTERED`, credit the presser with escaping during `EXITED`, or mix entry/exit semantics.
4. **Strict Numeric Whitelist:** Every number written in `analyst_view` and `fan_view` (excluding event IDs) is extracted and checked against the episode's computed statistics (`minute`, `def_actions`, `n_passes`, and `pass_acc` percentage). Any invented number triggers a rejection and retry with the exact error reason injected into the prompt.

All 10 fault-injection and acceptance cases are tested in `test_verifier.py` (8 rejected hallucination cases, 2 valid cases).

---

## 4. Empirical Measurements & Benchmarks

**Hardware Environment:** Dell Latitude 5520, Intel Core i5-1145G7 (4 cores / 8 threads), 15 GB RAM, Ubuntu Linux (CPU-only inference via Ollama).

### A. Offline Detector Calibration Benchmark (Synthetic Generator)
*Note: Thresholds are calibrated and evaluated on our synthetic match generator as a controlled non-regression benchmark.*
- **Tuning Set:** Seeds `1..120`
- **Held-Out Test Set:** 200 matches (Seeds `1001..1200`: 151 matches with High Press, 49 control matches without pressing)
- **Held-Out Results (Detector v4):**
  - **Recall (within window):** `73.5%` (median detection delay: `5.0` match minutes)
  - **False Entries per Match (overall):** `0.04` (only `1` false entry across the `49` control matches)
  - **Exit Accuracy (within ±8 min of true end):** `103 / 111`

### B. Deterministic Seed 42 End-to-End Trace (`engine_metrics.json`)
- **Ground Truth (`ground_truth.json`):** `shift_type: "High Press"`, `shift_team: "Meteor City"`, `true_minute: 52`, `end_minute: 64`.
- **Simulated Match Totals:** `1,833` events, `89.7%` pass accuracy, Final Score: `Meteor City 2 - 0 Nova FC` (Goals at minutes `51` and `79`).
- **Detector Alarms Fired:**
  - `ENTERED` at minute `57` (Meteor City pressing Nova FC)
  - `EXITED` at minute `62` (Nova FC escaping Meteor City's press)
- **Live Edge LLM Execution (`llama3.2` via Microsoft Agent Framework):**
  - **Model Warmup Time:** `4.07s`
  - **Alarms Processed:** `2 / 2` verified on Attempt 1 (`llm_verified: 2`, `fallback_after_rejection: 0`, `timeouts: 0`)
  - **Episode 1 Latency (`m_42_min57_ENTERED`):** `12.62s`
  - **Episode 2 Latency (`m_42_min62_EXITED`):** `13.16s`
  - **Mean / Median Episode Latency (Seed 42):** `12.89s`
  - **Superseded Finals:** `0`
  - **Fabric Delivery Mode:** `fabric_eventstream_live`

---

## 5. Microsoft Ecosystem Integration

- **Microsoft Agent Framework (`agent-framework`):** Orchestrates `explainer_agent` and `recap_agent` over an OpenAI-compatible client (`OpenAIChatCompletionClient`).
- **Microsoft Fabric Eventstream (`fabric_sink.py`):** Live asynchronous event streaming via `azure-eventhub` when `EVENTHUB_CONNECTION_STRING` is present in `.env`, with automatic local fallback (`fabric_local_fallback.jsonl`) for offline reproducibility.
- **Model Flexibility (Llama 3.2 / Microsoft Phi-4-mini):** Configurable via environment variable (`OLLAMA_MODEL=phi4-mini` or `OLLAMA_MODEL=llama3.2`).
- **GitHub Actions CI (`.github/workflows/ci.yml`):** Automated test workflow executing `pytest test_verifier.py`, deterministic match generation, and detector diagnostics.

---

## 6. Reproducible Quickstart

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the 10 Verifier v4 unit tests (no LLM or network required)
python3 test_verifier.py

# 3. Generate deterministic Seed 42 match data and inspect ground truth
python3 generator.py --seed 42
cat ground_truth.json

# 4. Run offline detector diagnostic on Seed 42
python3 debug_detector.py match_events.jsonl ground_truth.json

# 5. Launch the Streamlit Broadcast Control UI (Terminal 1)
streamlit run app.py

# 6. Run the real-time asynchronous engine (Terminal 2)
# Optional: export OLLAMA_MODEL="phi4-mini" broadcasts in "French" or custom persona
python3 engine.py
```
