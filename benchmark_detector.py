"""Reproduit en une commande les métriques du détecteur sur 200 matchs mis de côté (1001..1200)."""
import os
import json
import statistics
from generator import generate_match
from detector import OnlineShiftDetector

TUNING_SEEDS = range(1, 121)
TEST_SEEDS = range(1001, 1201)

def run_benchmark():
    print("🔬 Exécution du benchmark détecteur sur 200 matchs de test (Seeds 1001..1200)...")
    detector = OnlineShiftDetector()
    
    total_matches = len(TEST_SEEDS)
    press_matches = 0
    control_matches = 0
    
    true_positive_entries = 0
    delays = []
    false_entries = 0
    false_control_entries = 0
    wrong_team_entries = 0
    early_entries = 0
    exit_accurate = 0
    exit_evaluated = 0

    for s in TEST_SEEDS:
        acc, score = generate_match(s, f"bench_{s}", "bench_events.jsonl", "bench_truth.json")
        truth = json.load(open("bench_truth.json"))
        events = [json.loads(line) for line in open("bench_events.jsonl")]
        
        d = OnlineShiftDetector()
        alarms = []
        for e in events:
            a = d.process_event(e)
            if a:
                alarms.append(a)
                
        is_press = truth["shift_type"] == "High Press"
        if is_press:
            press_matches += 1
            t_min = truth["true_minute"]
            e_min = truth.get("end_minute", t_min + 12)
            team = truth["shift_team"]
            
            entries = [a for a in alarms if a["status"] == "ENTERED"]
            if entries:
                first = entries[0]
                if first["team"] == team:
                    if first["minute"] < t_min:
                        early_entries += 1
                    elif first["minute"] <= t_min + 12:
                        true_positive_entries += 1
                        delays.append(first["minute"] - t_min)
                else:
                    wrong_team_entries += 1
            
            # Sorties
            exits = [a for a in alarms if a["status"] == "EXITED"]
            if exits and entries:
                exit_evaluated += 1
                if abs(exits[0]["minute"] - e_min) <= 8:
                    exit_accurate += 1
        else:
            control_matches += 1
            ctrl_entries = [a for a in alarms if a["status"] == "ENTERED"]
            false_control_entries += len(ctrl_entries)
            false_entries += len(ctrl_entries)

    # Nettoyage
    for f in ("bench_events.jsonl", "bench_truth.json"):
        if os.path.exists(f): os.remove(f)

    recall = (true_positive_entries / press_matches) * 100
    med_delay = statistics.median(delays) if delays else 0
    fp_per_match = false_entries / total_matches

    print("\n--- RÉSULTATS DU BENCHMARK DÉTECTEUR v4 (200 MATCHS) ---")
    print(f"Total Matchs : {total_matches} (Pressing: {press_matches}, Contrôles: {control_matches})")
    print(f"Recall (fenêtre +12 min) : {recall:.1f}% ({true_positive_entries}/{press_matches})")
    print(f"Retard médian de détection : {med_delay:.1f} minutes")
    print(f"Fausses entrées / match : {fp_per_match:.2f} (Contrôle: {false_control_entries}/{control_matches}, Mauvaise équipe: {wrong_team_entries}, Anticipées: {early_entries})")
    print(f"Sorties précises (±8 min de la vraie fin) : {exit_accurate}/{exit_evaluated}")

if __name__ == "__main__":
    run_benchmark()
