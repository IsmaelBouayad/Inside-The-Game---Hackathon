import asyncio
import json
import os
import statistics
import time
import argparse
from collections import deque
from datetime import datetime

from detector import OnlineShiftDetector
from pipeline import (
    generate_episode_narrative,
    generate_fallback_overlay,
    generate_goal_overlay,
    generate_match_recap,
    warmup_ollama,
)
from fabric_sink import FabricTelemetrySink

# CONFIGURATION
SPEED = float(os.environ.get("MATCH_SPEED", 60))
TACTICAL_SLOWDOWN_SPEED = float(os.environ.get("TACTICAL_SPEED", 2.0))
DYNAMIC_PACING = os.environ.get("DYNAMIC_PACING", "1") == "1"
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", 45))
EVENTS_FILE = os.environ.get("EVENTS_FILE", "match_events.jsonl")
LANGUAGE = os.environ.get("BROADCAST_LANG", "English")
PERSONA = os.environ.get("BROADCAST_PERSONA", "General Fan")

UI_FILE = "broadcast_ui.jsonl"
CLOCK_FILE = "match_clock.json"
METRICS_FILE = "engine_metrics.json"
RECAP_FILE = "match_recap.json"
QUEUE_SIZE = 2

pending_fabric_tasks: set = set()


def append_to_ui(data: dict) -> None:
    with open(UI_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def update_clock(minute: int, score: dict, state: str, current_speed: float, momentum_history: list, peak_swing: dict) -> None:
    with open(CLOCK_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "minute": minute,
            "score": score,
            "tactical_state": state,
            "current_speed": current_speed,
            "momentum_history": momentum_history[-30:],
            "peak_swing": peak_swing
        }, f)


class Metrics:
    def __init__(self):
        self.events = self.alarms = self.goals = self.dropped = 0
        self.llm_ok = self.rejected_fallback = self.timeouts = self.errors = 0
        self.superseded_finals = 0
        self.fabric_mode = "local_jsonl_fallback"
        self.latencies: list[float] = []

    def dump(self):
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
            "llm_latency_sec_median": round(statistics.median(lat), 2) if lat else None,
            "llm_latency_sec_max": round(max(lat), 2) if lat else None
        }
        with open(METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data


def schedule_fabric_send(fabric: FabricTelemetrySink, record_type: str, payload: dict):
    """Envoi Fabric non-bloquant suivi dans pending_fabric_tasks pour garantir la livraison finale."""
    async def _send():
        try:
            await asyncio.wait_for(fabric.ingest_record(record_type, payload), timeout=5.0)
        except Exception:
            pass
    task = asyncio.create_task(_send())
    pending_fabric_tasks.add(task)
    task.add_done_callback(pending_fabric_tasks.discard)


def template_overlay(alarm: dict, key: str, seq: int, status: str, reason: str = "", latency=None) -> dict:
    o = generate_fallback_overlay(alarm, key, language=LANGUAGE, persona=PERSONA)
    o["episode_seq"] = seq
    o["render_status"] = status
    if reason:
        o["reason"] = reason
    if latency is not None:
        o["llm_latency_sec"] = latency
    return o


async def llm_worker(
    queue: asyncio.Queue,
    match_id: str,
    llm,
    metrics: Metrics,
    llm_timeout: float,
    fabric: FabricTelemetrySink,
    state_tracker: dict,
    verified_overlays: list
):
    while True:
        seq, alarm, raw_events = await queue.get()
        state_tracker["worker_busy"] = True
        key = f"{match_id}_min{alarm['minute']}_{alarm['status']}"
        t0 = time.monotonic()
        try:
            out = await asyncio.wait_for(
                llm(match_id, alarm, raw_events, force_live=True, language=LANGUAGE, persona=PERSONA),
                timeout=llm_timeout
            )
            latency = round(time.monotonic() - t0, 2)
            is_superseded = seq < state_tracker["latest_seq"]

            if out and not out.get("is_fallback"):
                out["episode_seq"] = seq
                out["superseded"] = is_superseded
                out["llm_latency_sec"] = latency
                out["completed_at_match_minute"] = state_tracker["current_minute"]
                out["render_status"] = "FINAL (AI Verified - Historical / Superseded)" if is_superseded else "FINAL (AI Verified)"
                metrics.llm_ok += 1
                metrics.latencies.append(latency)
                verified_overlays.append(out)
            else:
                out = template_overlay(alarm, key, seq, "FINAL (Template - LLM Output Rejected)", latency=latency)
                out["superseded"] = is_superseded
                metrics.rejected_fallback += 1
                verified_overlays.append(out)

            append_to_ui(out)
            schedule_fabric_send(fabric, "OVERLAY_FINAL", out)
            print(f"   ✅ [Worker] {out['render_status']} en {latency}s ({key})")

        except asyncio.TimeoutError:
            metrics.timeouts += 1
            latency = round(time.monotonic() - t0, 2)
            fb = template_overlay(alarm, key, seq, "FINAL (Template - LLM Timeout)",
                                  reason=f"Timeout {llm_timeout}s", latency=latency)
            fb["superseded"] = seq < state_tracker["latest_seq"]
            append_to_ui(fb)
            schedule_fabric_send(fabric, "OVERLAY_TIMEOUT", fb)
            print(f"   ⏱️ [Worker] TIMEOUT après {llm_timeout}s ({key}) - Gabarit conservé")
        except Exception as e:
            metrics.errors += 1
            err = template_overlay(alarm, key, seq, "FINAL (Template - LLM Error)", reason=type(e).__name__)
            append_to_ui(err)
            print(f"   ❌ [Worker] {type(e).__name__}: {e}")
        finally:
            state_tracker["worker_busy"] = False
            queue.task_done()


async def match_engine(events_file: str = EVENTS_FILE, speed: float = SPEED, start_minute: int = 0, llm=None,
                       llm_timeout: float = LLM_TIMEOUT):
    llm = llm or generate_episode_narrative
    if not os.path.exists(events_file):
        print(f"❌ {events_file} introuvable. Lancez 'python3 generator.py --seed 42' d'abord.")
        return

    for f_path in (UI_FILE, CLOCK_FILE, RECAP_FILE):
        if os.path.exists(f_path):
            os.remove(f_path)

    await warmup_ollama()

    with open(events_file, "r", encoding="utf-8") as f:
        events = [json.loads(line) for line in f]

    match_id = events[0]["event_id"].split("-")[1]
    detector = OnlineShiftDetector()

    # Pré-alimentation causale du détecteur si start_minute > 0 pour garder l'historique exact du Momentum
    score = {"Meteor City": 0, "Nova FC": 0}
    for e in events:
        if e["minute"] < start_minute:
            detector.process_event(e)
            if e.get("event_type") == "Shot" and e.get("outcome") == "Goal":
                score[e["team"]] += 1

    filtered_events = [e for e in events if e["minute"] >= start_minute]
    print(f"⚽ Match {match_id}: {len(filtered_events)} événements (min {start_minute}..89), vitesse base x{speed}, ralenti tactique={'ON' if DYNAMIC_PACING else 'OFF'}")

    metrics = Metrics()
    fabric = FabricTelemetrySink()
    metrics.fabric_mode = "fabric_eventstream_live" if fabric.live_enabled else "local_jsonl_fallback"
    queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_SIZE)

    state_tracker = {"latest_seq": 0, "current_minute": start_minute, "worker_busy": False}
    verified_overlays = []

    worker = asyncio.create_task(
        llm_worker(queue, match_id, llm, metrics, llm_timeout, fabric, state_tracker, verified_overlays)
    )
    recent: deque = deque(maxlen=150)
    last_ts = None
    last_clock_min = -1

    try:
        for event in filtered_events:
            ts = datetime.fromisoformat(event["timestamp"])
            active_speed = TACTICAL_SLOWDOWN_SPEED if (DYNAMIC_PACING and (state_tracker["worker_busy"] or not queue.empty())) else speed

            if last_ts is not None and active_speed > 0:
                await asyncio.sleep(max(0.0, (ts - last_ts).total_seconds()) / active_speed)
            last_ts = ts

            metrics.events += 1
            recent.append(event)
            state_tracker["current_minute"] = event["minute"]

            if event.get("event_type") == "Shot" and event.get("outcome") == "Goal":
                score[event["team"]] += 1
                metrics.goals += 1
                state_tracker["latest_seq"] += 1
                goal_ov = generate_goal_overlay(event, score, match_id, language=LANGUAGE)
                goal_ov["episode_seq"] = state_tracker["latest_seq"]
                append_to_ui(goal_ov)
                verified_overlays.append(goal_ov)
                schedule_fabric_send(fabric, "GOAL_TIER0", goal_ov)
                print(f"\n⚽ [TIER-0 GOAL] Minute {event['minute']} — {event['team']} ({score})")

            alarm = detector.process_event(event)

            if event["minute"] != last_clock_min:
                last_clock_min = event["minute"]
                update_clock(
                    event["minute"], score, detector.state, active_speed,
                    detector.momentum_history, detector.peak_swing
                )

            if alarm:
                metrics.alarms += 1
                state_tracker["latest_seq"] += 1
                seq = state_tracker["latest_seq"]
                key = f"{match_id}_min{alarm['minute']}_{alarm['status']}"
                reason_tag = f" [reason={alarm.get('exit_reason')}]" if alarm.get("exit_reason") else ""
                print(f"\n🚨 [DÉTECTEUR] {alarm['status']}{reason_tag} minute {alarm['minute']} ({alarm['team']} vs {alarm['victim']})")

                draft = template_overlay(alarm, key, seq, "DRAFT (Live)")
                append_to_ui(draft)
                schedule_fabric_send(fabric, "ALARM", alarm)

                job = (seq, alarm, list(recent))
                if queue.full():
                    queue.get_nowait()
                    queue.task_done()
                    metrics.dropped += 1
                queue.put_nowait(job)

            await asyncio.sleep(0)

        print("\n🏁 Coup de sifflet final du match.")
        try:
            await asyncio.wait_for(queue.join(), timeout=llm_timeout * (QUEUE_SIZE + 1))
        except asyncio.TimeoutError:
            print("   ⚠️ Abandon de l'attente des jobs résiduels.")

        print("📝 [RecapAgent] Génération du résumé tactique et Turning Point de fin de match...")
        recap = await generate_match_recap(
            match_id, verified_overlays, score,
            peak_swing=detector.peak_swing, language=LANGUAGE
        )
        with open(RECAP_FILE, "w", encoding="utf-8") as f:
            json.dump(recap, f, indent=2, ensure_ascii=False)

        final_metrics = metrics.dump()

        # Envoi synchrone final garanti vers Fabric pour POST_MATCH_RECAP et MATCH_METRICS
        await fabric.ingest_record("POST_MATCH_RECAP", recap)
        await fabric.ingest_record("MATCH_METRICS", final_metrics)
        if pending_fabric_tasks:
            await asyncio.gather(*pending_fabric_tasks, return_exceptions=True)

    finally:
        worker.cancel()
        await fabric.close()

    print("🎬 Moteur terminé. Métriques :", json.dumps(final_metrics, indent=2))


if __name__ == "__main__":
    import logging
    logging.getLogger("agent_framework").setLevel(logging.ERROR)
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-minute", type=int, default=0, help="Minute de départ pour vidéo accélérée (<2 min)")
    args = parser.parse_args()
    asyncio.run(match_engine(start_minute=args.start_minute))
