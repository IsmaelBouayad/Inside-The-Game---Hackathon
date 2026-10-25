import asyncio
import json
import os
import sys
import time
import statistics
from datetime import datetime, timezone
from detector import OnlineShiftDetector
from generator import generate_match
from pipeline import (
    generate_episode_narrative,
    generate_fallback_overlay,
    generate_goal_overlay,
    generate_match_recap,
    warmup_ollama,
)
from fabric_sink import FabricTelemetrySink

UI_FILE = "broadcast_ui.jsonl"
CLOCK_FILE = "match_clock.json"
METRICS_FILE = "engine_metrics.json"
RECAP_FILE = "match_recap.json"

BROADCAST_LANG = os.environ.get("BROADCAST_LANG", "English")
BROADCAST_PERSONA = os.environ.get("BROADCAST_PERSONA", "General Fan")


def template_overlay(alarm, episode_key, seq_id, status_label):
    fb = generate_fallback_overlay(alarm, episode_key, language=BROADCAST_LANG, persona=BROADCAST_PERSONA)
    fb["episode_seq"] = seq_id
    fb["render_status"] = status_label
    return fb


def append_to_ui(payload):
    with open(UI_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def event_clock_sec(ev: dict) -> int:
    if "second" in ev:
        return int(ev["minute"]) * 60 + int(ev["second"])
    ts = str(ev.get("timestamp", ""))
    if len(ts) >= 19 and ts[17:19].isdigit():
        return int(ev["minute"]) * 60 + int(ts[17:19])
    return int(ev["minute"]) * 60


def update_clock(minute, score, tactical_state, current_speed, momentum_history=None, peak_swing=None):
    data = {
        "minute": minute,
        "score": score,
        "tactical_state": tactical_state,
        "current_speed": current_speed,
        "momentum_history": (momentum_history or [])[-30:],
        "peak_swing": peak_swing or {},
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(CLOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)


class Metrics:
    def __init__(self):
        self.events = 0
        self.alarms = 0
        self.goals = 0
        self.dropped = 0
        self.llm_ok = 0
        self.rejected_fallback = 0
        self.timeouts = 0
        self.errors = 0
        self.superseded_finals = 0
        self.fabric_mode = "local_jsonl_fallback"
        self.fabric_sent = 0
        self.fabric_fallbacks = 0
        self.latencies = []

    def dump(self, fabric=None):
        if fabric is not None:
            self.fabric_sent = getattr(fabric, "sent_live_count", 0)
            self.fabric_fallbacks = getattr(fabric, "local_fallback_count", 0)
            if getattr(fabric, "live_enabled", False):
                self.fabric_mode = "fabric_eventstream_live"
        lat = self.latencies
        data = {
            "events": self.events,
            "alarms": self.alarms,
            "goals_narrated_tier0": self.goals,
            "dropped_jobs": self.dropped,
            "llm_verified": self.llm_ok,
            "fallback_after_rejection": self.rejected_fallback,
            "timeouts": self.timeouts,
            "errors": self.errors,
            "superseded_finals": self.superseded_finals,
            "fabric_delivery_mode": self.fabric_mode,
            "fabric_live_sends_succeeded": self.fabric_sent,
            "fabric_local_fallbacks": self.fabric_fallbacks,
            "llm_latency_sec_median": round(statistics.median(lat), 2) if lat else None,
            "llm_latency_sec_max": round(max(lat), 2) if lat else None,
            "last_updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data


async def llm_worker(queue, match_id, llm_fn, metrics, timeout_s, fabric: FabricTelemetrySink, state_tracker: dict, verified_overlays: list):
    while True:
        seq_id, alarm, context_events = await queue.get()
        state_tracker["worker_busy"] = True
        ep_key = f"{match_id}_min{alarm['minute']}_{alarm.get('status', 'ENTERED')}"
        t0 = time.monotonic()
        try:
            out = await asyncio.wait_for(
                llm_fn(match_id, alarm, context_events, force_live=True, language=BROADCAST_LANG, persona=BROADCAST_PERSONA),
                timeout=timeout_s
            )
            dt = round(time.monotonic() - t0, 2)
            out["episode_seq"] = seq_id
            is_superseded = seq_id < state_tracker["latest_seq"]
            out["superseded"] = is_superseded

            if out.get("is_fallback"):
                metrics.rejected_fallback += 1
                out["render_status"] = "FINAL (Template - LLM Output Rejected)"
                out["llm_latency_sec"] = dt
                verified_overlays.append(out)
                print(f"   ✅ [Worker] {out['render_status']} en {dt}s ({ep_key})")
            else:
                metrics.llm_ok += 1
                metrics.latencies.append(dt)
                out["llm_latency_sec"] = dt
                out["completed_at_match_minute"] = state_tracker["current_minute"]
                if is_superseded:
                    metrics.superseded_finals += 1
                    out["render_status"] = "FINAL (AI Verified - Historical / Superseded)"
                else:
                    out["render_status"] = "FINAL (AI Verified)"
                verified_overlays.append(out)
                print(f"   ✅ [Worker] {out['render_status']} en {dt}s ({ep_key})")

            append_to_ui(out)
            await fabric.ingest_record("OVERLAY_FINAL", out)

        except asyncio.TimeoutError:
            metrics.timeouts += 1
            fb = template_overlay(alarm, ep_key, seq_id, "FINAL (Template - LLM Timeout)")
            fb["llm_latency_sec"] = round(time.monotonic() - t0, 2)
            verified_overlays.append(fb)
            append_to_ui(fb)
            await fabric.ingest_record("OVERLAY_TIMEOUT", fb)
            print(f"   ⚠️ [Worker] Timeout LLM ({timeout_s}s) -> gabarit conservé ({ep_key})")
        except asyncio.CancelledError:
            queue.task_done()
            raise
        except Exception as e:
            metrics.errors += 1
            err = template_overlay(alarm, ep_key, seq_id, f"FINAL (Template - {type(e).__name__})")
            verified_overlays.append(err)
            append_to_ui(err)
            print(f"   ❌ [Worker] {type(e).__name__}: {e}")
        finally:
            state_tracker["worker_busy"] = False
            metrics.dump(fabric)
            queue.task_done()


async def match_engine(
    events_file="match_events.jsonl",
    speed=None,
    llm_fn=generate_episode_narrative,
    llm_timeout=None,
    start_minute=None
):
    speed = float(speed or os.environ.get("MATCH_SPEED", 150.0))
    tactical_speed = float(os.environ.get("TACTICAL_SPEED", 2.0))
    dynamic_pacing = os.environ.get("DYNAMIC_PACING", "1") == "1"
    llm_timeout = float(llm_timeout or os.environ.get("LLM_TIMEOUT", 45.0))
    start_min = int(start_minute if start_minute is not None else os.environ.get("START_MINUTE", 0))

    # Auto-generate Seed 42 match_events.jsonl if absent (e.g. fresh clone or Docker mount)
    if not os.path.exists(events_file):
        print(f"📦 [Init] Generating deterministic Seed 42 telemetry into '{events_file}'...")
        generate_match(42, "m_42", events_file, "ground_truth.json")

    for f_path in (UI_FILE, CLOCK_FILE, RECAP_FILE, METRICS_FILE, "director_audit.jsonl"):
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
            except Exception:
                pass
    update_clock(start_min, {"Meteor City": 0, "Nova FC": 0}, "Normal", speed, [], {})

    detector = OnlineShiftDetector()
    metrics = Metrics()
    fabric = FabricTelemetrySink()
    metrics.fabric_mode = "fabric_eventstream_live" if fabric.live_enabled else "local_jsonl_fallback"
    metrics.dump(fabric)

    queue = asyncio.Queue(maxsize=2)
    state_tracker = {"latest_seq": 0, "current_minute": start_min, "worker_busy": False}
    verified_overlays = []
    pending_fabric_tasks = set()

    def schedule_fabric_send(record_type: str, payload: dict):
        t = asyncio.create_task(fabric.ingest_record(record_type, payload))
        pending_fabric_tasks.add(t)
        def _on_done(task):
            pending_fabric_tasks.discard(task)
            metrics.dump(fabric)
        t.add_done_callback(_on_done)

    await warmup_ollama()

    with open(events_file, "r", encoding="utf-8") as f:
        all_events = [json.loads(line) for line in f if line.strip()]

    if not all_events:
        return

    match_id = all_events[0].get("match_id", "m_42")
    score = {"Meteor City": 0, "Nova FC": 0}

    if start_min > 0:
        pre_events = [e for e in all_events if e["minute"] < start_min]
        events = [e for e in all_events if e["minute"] >= start_min]
        for pe in pre_events:
            if pe.get("event_type") == "Shot" and pe.get("outcome") == "Goal":
                score[pe["team"]] = score.get(pe["team"], 0) + 1
            detector.process_event(pe)
    else:
        events = all_events

    worker = asyncio.create_task(
        llm_worker(queue, match_id, llm_fn, metrics, llm_timeout, fabric, state_tracker, verified_overlays)
    )
    print(f"⚽ Match {match_id}: {len(events)} événements (min {start_min}..90), vitesse base x{speed}, ralenti tactique={'ON' if dynamic_pacing else 'OFF'}")

    prev_clock = event_clock_sec(events[0])
    last_printed_min = -1

    try:
        for event in events:
            now_clock = event_clock_sec(event)
            dt = max(0, now_clock - prev_clock)
            prev_clock = now_clock

            is_slow = dynamic_pacing and (state_tracker["worker_busy"] or not queue.empty())
            active_speed = min(speed, tactical_speed) if is_slow else speed

            if dt > 0 and active_speed > 0:
                await asyncio.sleep(dt / active_speed)

            metrics.events += 1
            state_tracker["current_minute"] = event["minute"]

            if event.get("event_type") == "Shot" and event.get("outcome") == "Goal":
                scorer = event["team"]
                score[scorer] = score.get(scorer, 0) + 1
                metrics.goals += 1
                state_tracker["latest_seq"] += 1
                goal_ov = generate_goal_overlay(event, score, match_id, language=BROADCAST_LANG)
                goal_ov["episode_seq"] = state_tracker["latest_seq"]
                append_to_ui(goal_ov)
                verified_overlays.append(goal_ov)
                schedule_fabric_send("GOAL_TIER0", goal_ov)
                metrics.dump(fabric)
                print(f"\n⚽ [TIER-0 GOAL] Minute {event['minute']} — {scorer} ({score})")

            alarm = detector.process_event(event)

            if event["minute"] != last_printed_min:
                last_printed_min = event["minute"]
                update_clock(
                    event["minute"], score, detector.state, active_speed,
                    detector.momentum_history, detector.peak_swing
                )
                metrics.dump(fabric)

            if alarm:
                metrics.alarms += 1
                state_tracker["latest_seq"] += 1
                seq_id = state_tracker["latest_seq"]
                alarm["episode_seq"] = seq_id
                alarm["timestamp"] = event.get("timestamp", "")

                ep_key = f"{match_id}_min{alarm['minute']}_{alarm.get('status', 'ENTERED')}"
                reason_str = f" [reason={alarm.get('exit_reason')}]" if alarm.get("exit_reason") else ""
                print(f"\n🚨 [DÉTECTEUR] {alarm['status']}{reason_str} minute {alarm['minute']} ({alarm['team']} vs {alarm['victim']})")

                draft = template_overlay(alarm, ep_key, seq_id, "DRAFT (Live)")
                append_to_ui(draft)
                schedule_fabric_send("ALARM", alarm)
                metrics.dump(fabric)

                if queue.full():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                        metrics.dropped += 1
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait((seq_id, alarm, list(detector.buffer)))

        print("\n🏁 Coup de sifflet final du match.")
        if not detector.momentum_history or detector.momentum_history[-1]["minute"] < 90:
            detector.compute_momentum(90)
        update_clock(90, score, "Full Time", 0.0, detector.momentum_history, detector.peak_swing)
        await queue.join()

        print("📝 [RecapAgent] Génération du résumé tactique et Turning Point de fin de match...")
        recap = await generate_match_recap(
            match_id, verified_overlays, score,
            peak_swing=detector.peak_swing, language=BROADCAST_LANG
        )
        with open(RECAP_FILE, "w", encoding="utf-8") as rf:
            json.dump(recap, rf, indent=2, ensure_ascii=False)

        if pending_fabric_tasks:
            await asyncio.gather(*pending_fabric_tasks, return_exceptions=True)

        await fabric.ingest_record("POST_MATCH_RECAP", recap)
        final_metrics = metrics.dump(fabric)
        await fabric.ingest_record("MATCH_METRICS", final_metrics)
        final_metrics = metrics.dump(fabric)

    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)
        await fabric.close()
        print(f"🎬 Moteur terminé. Métriques : {json.dumps(metrics.dump(fabric), indent=2)}")


if __name__ == "__main__":
    start_m = None
    if "--start-minute" in sys.argv:
        idx = sys.argv.index("--start-minute")
        if idx + 1 < len(sys.argv):
            start_m = int(sys.argv[idx + 1])
    asyncio.run(match_engine(start_minute=start_m))
