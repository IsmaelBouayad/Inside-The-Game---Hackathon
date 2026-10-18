"""Calibration script compatible with OnlineShiftDetector v4 API."""
import json
import os
from generator import generate_match
from detector import OnlineShiftDetector

def evaluate_config(entry_acc=0.60, min_press=7, seeds=range(1, 31)):
    tp, fp_ctrl, total_press, total_ctrl = 0, 0, 0, 0
    for s in seeds:
        generate_match(s, f"cal_{s}", "cal_events.jsonl", "cal_truth.json")
        truth = json.load(open("cal_truth.json"))
        events = [json.loads(line) for line in open("cal_events.jsonl")]
        detector = OnlineShiftDetector(entry_acc=entry_acc, min_press=min_press)
        alarms = [a for e in events if (a := detector.process_event(e))]
        entries = [a for a in alarms if a["status"] == "ENTERED"]
        if truth["shift_type"] == "High Press":
            total_press += 1
            if any(a["team"] == truth["shift_team"] and truth["true_minute"] <= a["minute"] <= truth["true_minute"] + 12 for a in entries):
                tp += 1
        else:
            total_ctrl += 1
            fp_ctrl += len(entries)
    for f in ("cal_events.jsonl", "cal_truth.json"):
        if os.path.exists(f):
            os.remove(f)
    print(f"Config(entry_acc={entry_acc}, min_press={min_press}) -> Recall: {tp}/{total_press} ({tp/max(1,total_press)*100:.1f}%), Control FP: {fp_ctrl}/{total_ctrl}")

if __name__ == "__main__":
    print("Running Detector v4 Grid Calibration (Seeds 1..30)...")
    for acc in (0.55, 0.60, 0.65):
        for press in (6, 7, 8):
            evaluate_config(entry_acc=acc, min_press=press)
