import json
import statistics
import os
import sys
from generator import generate_match

class HiddenPrints:
    def __enter__(self):
        self._original_stdout, sys.stdout = sys.stdout, open(os.devnull, 'w')
    def __exit__(self, *args):
        sys.stdout.close()
        sys.stdout = self._original_stdout

class ShiftDetector:
    def __init__(self):
        self.buffer = []
        self.last_alarm = {} # Debounce tracking

    def process_event(self, event):
        self.buffer.append(event)
        current_min = event["minute"]
        self.buffer = [e for e in self.buffer if current_min - e["minute"] <= 5]
        
        if len(self.buffer) < 20: 
            return []
            
        alarms = []
        teams = {
            "Meteor City": {"def_zone": lambda x: x < 33, "att_zone": lambda x: x > 66},
            "Nova FC": {"def_zone": lambda x: x > 66, "att_zone": lambda x: x < 33}
        }
                 
        for team, zones in teams.items():
            opp = "Nova FC" if team == "Meteor City" else "Meteor City"
            
            # High Press applied BY opp ON team
            t_passes = [e for e in self.buffer if e["team"] == team and e["event_type"] == "Pass" and zones["def_zone"](e.get("start_x", 0))]
            o_presses = [e for e in self.buffer if e["team"] == opp and e["event_type"] == "Pressure" and zones["def_zone"](e.get("x", 0))]
            
            if len(t_passes) >= 4:
                acc = sum(1 for e in t_passes if e["outcome"] == "Success") / len(t_passes)
                if acc < 0.65 and len(o_presses) >= 4:
                    self._add_alarm(alarms, current_min, "High Press", opp)
            
            # Low Block applied BY opp ON team
            t_att_passes = [e for e in self.buffer if e["team"] == team and e["event_type"] == "Pass" and zones["att_zone"](e.get("start_x", 0))]
            o_def_actions = [e for e in self.buffer if e["team"] == opp and e["event_type"] in ["Interception", "Tackle"] and zones["att_zone"](e.get("x", 0))]
            
            if len(t_att_passes) >= 4:
                acc_att = sum(1 for e in t_att_passes if e["outcome"] == "Success") / len(t_att_passes)
                if acc_att < 0.65 and len(o_def_actions) >= 4:
                    self._add_alarm(alarms, current_min, "Low Block", opp)
                    
        return alarms

    def _add_alarm(self, alarms_list, current_min, s_type, s_team):
        key = (s_type, s_team)
        if key not in self.last_alarm or (current_min - self.last_alarm[key] > 5):
            self.last_alarm[key] = current_min
            alarms_list.append({"minute": current_min, "type": s_type, "team": s_team})

def run_harness(start_seed, end_seed):
    detections, false_alarms, delays = [], 0, []
    
    for seed in range(start_seed, end_seed + 1):
        events_file, truth_file = f"temp_ev_{seed}.jsonl", f"temp_tr_{seed}.json"
        
        with HiddenPrints():
            generate_match(seed, f"m_{seed:03d}", events_file, truth_file)
            
        with open(truth_file, "r") as f:
            truth = json.load(f)
            
        detector = ShiftDetector()
        match_alarms = []
        
        with open(events_file, "r") as f:
            for line in f:
                new_alarms = detector.process_event(json.loads(line))
                match_alarms.extend(new_alarms)
                
        # Scoring Logic
        hit_registered = False
        for alarm in match_alarms:
            is_match = (alarm["type"] == truth["shift_type"] and alarm["team"] == truth["shift_team"])
            in_window = truth["shift_type"] != "None" and (truth["true_minute"] <= alarm["minute"] <= truth["true_minute"] + 10)
            
            if is_match and in_window and not hit_registered:
                hit_registered = True
                delays.append(alarm["minute"] - truth["true_minute"])
            else:
                false_alarms += 1
                
        if truth["shift_type"] != "None":
            detections.append(1 if hit_registered else 0)
            
        os.remove(events_file)
        os.remove(truth_file)

    total_shifts = len(detections)
    dr = (sum(detections) / total_shifts * 100) if total_shifts else 0
    fa_rate = false_alarms / (end_seed - start_seed + 1)
    md = statistics.median(delays) if delays else 0
    
    print(f"Matches: {end_seed - start_seed + 1} | True Detection Rate: {dr:.1f}% | FA/Match: {fa_rate:.2f} | Median Delay: {md:.1f} mins")

if __name__ == "__main__":
    print("🚀 Tuning on Train Set (1-50)...")
    run_harness(1, 50)
    print("\n🚀 Evaluating on Held-Out Test Set (1001-1200)...")
    run_harness(1001, 1200)
