"""Offline diagnostic: is the detector really blind, or is the input file the problem?
 
Usage:  python3 debug_detector.py [match_events.jsonl] [ground_truth.json]
"""
import collections
import json
import os
import statistics
import sys
 
from detector import OnlineShiftDetector, OTHER
 
path = sys.argv[1] if len(sys.argv) > 1 else "match_events.jsonl"
truth_path = sys.argv[2] if len(sys.argv) > 2 else "ground_truth.json"
 
events = [json.loads(l) for l in open(path)]
minutes = [e["minute"] for e in events]
per_min = collections.Counter(minutes)
print(f"File: {path}")
print(f"  events: {len(events)} | minutes {min(minutes)}..{max(minutes)} | median events/minute: {statistics.median(per_min.values())}")
print(f"  types: {dict(collections.Counter(e['event_type'] for e in events))}")
print("  (a healthy 90-minute match has ~1800 events, ~20 per minute, with Pressure/Tackle/Interception present)")
truth = json.load(open(truth_path)) if os.path.exists(truth_path) else None
print(f"  ground truth: {truth}")
if truth and truth.get("shift_type") == "None":
    print("  -> this is a CONTROL match (no pressing): silence is the CORRECT behaviour.")
 
d = OnlineShiftDetector()
rows, alarms, last = [], [], None
for e in events:
    a = d.process_event(e)
    if a:
        alarms.append(a)
    if e["minute"] != last:                       # one row per minute: what the detector 'sees'
        last = e["minute"]
        row = {"minute": last}
        for victim in ("Meteor City", "Nova FC"):
            passes, press, acc = d._facts(victim, last, d.entry_window)
            row[victim] = f"passes={len(passes)} acc={'-' if acc is None else round(acc, 2)} press={len(press)}"
        rows.append(row)
 
print("\nAlarms:", [(a["minute"], a["status"], a["team"]) for a in alarms] or "NONE")
lo = (truth["true_minute"] - 3) if truth and truth.get("true_minute", 999) < 999 else 0
hi = lo + 25 if lo else 90
print(f"\nWhat the detector sees per minute (entry needs passes>={d.min_passes}, acc<={d.entry_acc}, press>={d.min_press}):")
for r in rows:
    if lo <= r["minute"] <= hi:
        print(f"  min {r['minute']:>2} | Meteor City victim: {r['Meteor City']:<32} | Nova FC victim: {r['Nova FC']}")
