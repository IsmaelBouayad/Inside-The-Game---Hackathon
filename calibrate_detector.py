import statistics
import json
import os
import sys
from generator import generate_match
from detector import OnlineShiftDetector

class HiddenPrints:
    def __enter__(self):
        self._original_stdout, sys.stdout = sys.stdout, open(os.devnull, 'w')
    def __exit__(self, *args):
        sys.stdout.close()
        sys.stdout = self._original_stdout

def run_calibration(start_seed, end_seed):
    detections, false_alarms, delays = [], 0, []
    total_shifts = 0
    
    for seed in range(start_seed, end_seed + 1):
        events_file, truth_file = f"temp_ev_{seed}.jsonl", f"temp_tr_{seed}.json"
        
        with HiddenPrints():
            generate_match(seed, f"m_{seed:03d}", events_file, truth_file)
            
        with open(truth_file, "r") as f:
            truth = json.load(f)
            
        detector = OnlineShiftDetector(window_minutes=5, cooldown_minutes=15)
        match_alarms = []
        
        with open(events_file, "r") as f:
            for line in f:
                alarm = detector.process_event(json.loads(line))
                if alarm:
                    match_alarms.append(alarm)
                    
        shift_present = truth["shift_type"] != "None"
        if shift_present:
            total_shifts += 1
            
        hit_registered = False
        for alarm in match_alarms:
            # We only model High Press for this slice to keep it scope-limited
            is_match = (alarm["type"] == truth["shift_type"] and alarm["team"] == truth["shift_team"])
            in_window = shift_present and (truth["true_minute"] <= alarm["minute"] <= truth["true_minute"] + 12)
            
            if is_match and in_window and not hit_registered:
                hit_registered = True
                delays.append(alarm["minute"] - truth["true_minute"])
            else:
                false_alarms += 1 # Any other alarm, including in control matches, is a FA episode
                
        if shift_present:
            detections.append(1 if hit_registered else 0)
            
        os.remove(events_file)
        os.remove(truth_file)
        
    num_matches = end_seed - start_seed + 1
    dr = (sum(detections) / total_shifts * 100) if total_shifts else 0
    fa_rate = false_alarms / num_matches
    md = statistics.median(delays) if delays else 0
    
    print(f"Matches: {num_matches} (Shifts: {total_shifts}, Control: {num_matches - total_shifts})")
    print(f"Recall (True Detection Rate): {dr:.1f}%")
    print(f"False Alarm Episodes/Match: {fa_rate:.2f}")
    print(f"Median Delay: {md:.1f} mins\n")

if __name__ == "__main__":
    print("🚀 Tuning on Train Set (1-50)...")
    run_calibration(1, 50)
    print("🚀 Evaluating on Held-Out Test Set (1001-1100)...")
    run_calibration(1001, 1100)
