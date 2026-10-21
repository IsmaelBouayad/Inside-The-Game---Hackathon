"""Reproduces the exact detector metrics on 200 held-out test matches (Seeds 1001..1200)."""
import os
import json
import statistics
from generator import generate_match
from detector import OnlineShiftDetector

TUNING_SEEDS = range(1, 121)
TEST_SEEDS = range(1001, 1201)

def run_benchmark():
    print(f"🔬 Detector v4 Benchmark: Tuned on {len(TUNING_SEEDS)} seeds (1..120), evaluated on {len(TEST_SEEDS)} held-out seeds (1001..1200)...")
    total_matches = len(TEST_SEEDS)
    press_matches = 0
    control_matches = 0

    true_positive_entries = 0
    delays = []
    false_control_entries = 0
    wrong_team_entries = 0
    early_entries = 0
    repeated_entries = 0
    exit_accurate = 0
    exit_evaluated = 0

    for s in TEST_SEEDS:
        generate_match(s, f"bench_{s}", "bench_events.jsonl", "bench_truth.json")
        truth = json.load(open("bench_truth.json"))
        events = [json.loads(line) for line in open("bench_events.jsonl")]

        d = OnlineShiftDetector()
        alarms = [a for e in events if (a := d.process_event(e))]
        entries = [a for a in alarms if a["status"] == "ENTERED"]

        if truth["shift_type"] == "High Press":
            press_matches += 1
            t_min = truth["true_minute"]
            e_min = truth.get("end_minute", t_min + 12)
            team = truth["shift_team"]

            matched_tp = False
            for idx, ent in enumerate(entries):
                if ent["team"] != team:
                    wrong_team_entries += 1
                elif ent["minute"] < t_min:
                    early_entries += 1
                elif not matched_tp and ent["minute"] <= t_min + 12:
                    true_positive_entries += 1
                    delays.append(ent["minute"] - t_min)
                    matched_tp = True
                elif matched_tp:
                    repeated_entries += 1

            exits = [a for a in alarms if a["status"] == "EXITED"]
            if exits and entries:
                exit_evaluated += 1
                if abs(exits[0]["minute"] - e_min) <= 8:
                    exit_accurate += 1
        else:
            control_matches += 1
            false_control_entries += len(entries)

    for f in ("bench_events.jsonl", "bench_truth.json"):
        if os.path.exists(f):
            os.remove(f)

    strict_false_entries = false_control_entries + wrong_team_entries + early_entries
    recall = (true_positive_entries / press_matches) * 100
    med_delay = statistics.median(delays) if delays else 0

    print("\n--- HELD-OUT DETECTOR BENCHMARK (200 MATCHES: SEEDS 1001..1200) ---")
    print(f"Total Matches: {total_matches} (High-Press: {press_matches}, Control No-Press: {control_matches})")
    print(f"Recall (within +12 min window): {recall:.1f}% ({true_positive_entries}/{press_matches})")
    print(f"Median Confirmation Delay: {med_delay:.1f} minutes")
    print(f"Control-Match False Entries: {false_control_entries}/{control_matches} ({false_control_entries/control_matches:.4f} per control match)")
    print(f"Strict False Entries (Control + Wrong-Team + Early) across 200 matches: {strict_false_entries}/200 ({strict_false_entries/total_matches:.2f} per match -> Control: {false_control_entries}, Wrong-Team: {wrong_team_entries}, Early: {early_entries})")
    print(f"Re-entries after exit on persistent pressing matches: {repeated_entries}")
    print(f"Exit Timing Accuracy (±8 min of true end): {exit_accurate}/{exit_evaluated} ({(exit_accurate/max(1,exit_evaluated))*100:.1f}%)")

if __name__ == "__main__":
    run_benchmark()
