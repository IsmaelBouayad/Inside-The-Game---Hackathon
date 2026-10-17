import json
import random
import math
import argparse
from datetime import datetime, timedelta

ROSTERS = {
    "Meteor City": [f"M-{i:02d}" for i in range(1, 12)],
    "Nova FC": [f"N-{i:02d}" for i in range(1, 12)]
}

def generate_match(seed, match_id, out_events, out_truth):
    random.seed(seed)
    clock = datetime(2026, 10, 27, 15, 0, 0)
    possession = "Meteor City"
    ball_x, ball_y = 50.0, 50.0
    sequence_num = 1
    events = []
    
    # Premier tirage conservé pour préserver l'alignement exact des seeds de calibration (1..1200)
    _legacy_roll = random.random()
    if _legacy_roll >= 0.3:
        _ = random.choice(["Meteor City", "Nova FC"])

    # Tirage effectif du régime tactique avec end_minute
    shift_roll = random.random()
    if shift_roll < 0.3:
        shift_type, shift_team = "None", "None"
        shift_minute = 999
        end_minute = 999
    else:
        shift_type = "High Press"
        shift_team = random.choice(["Meteor City", "Nova FC"])
        shift_minute = random.randint(45, 60)
        end_minute = shift_minute + random.randint(10, 20)
        
    if out_truth:
        with open(out_truth, "w", encoding="utf-8") as f:
            json.dump({
                "match_id": match_id,
                "seed": seed,
                "shift_type": shift_type,
                "shift_team": shift_team,
                "true_minute": shift_minute,
                "end_minute": end_minute
            }, f, indent=2)
        
    passes_attempted, passes_completed = 0, 0
    score = {"Meteor City": 0, "Nova FC": 0}

    for minute in range(90):
        seconds_simulated = 0
        while seconds_simulated < 60:
            dt = random.randint(2, 5)
            seconds_simulated += dt
            clock += timedelta(seconds=dt)
            
            player = random.choice(ROSTERS[possession])
            direction = 1 if possession == "Meteor City" else -1
            
            goal_x = 100.0 if possession == "Meteor City" else 0.0
            dist_to_goal = abs(goal_x - ball_x)
            defense_team = "Nova FC" if possession == "Meteor City" else "Meteor City"
            
            pressing_intensity = 0.1 
            hidden_pass_penalty = 0.0
            
            active_shift = shift_type if (shift_minute <= minute <= end_minute) else "None"
            
            if active_shift == "High Press" and shift_team == defense_team:
                if dist_to_goal > 66:
                    pressing_intensity = 0.6
                    hidden_pass_penalty = 0.25
            
            if random.random() < pressing_intensity:
                events.append({
                    "event_id": f"EVT-{match_id}-{sequence_num:04d}",
                    "timestamp": clock.isoformat(),
                    "minute": minute, "team": defense_team,
                    "player_id": random.choice(ROSTERS[defense_team]),
                    "event_type": "Pressure",
                    "x": round(ball_x, 2), "y": round(ball_y, 2)
                })
                sequence_num += 1
                clock += timedelta(seconds=1)
                seconds_simulated += 1

            if dist_to_goal < 25 and random.random() < 0.05:
                shot_success = random.random() < 0.10
                events.append({
                    "event_id": f"EVT-{match_id}-{sequence_num:04d}",
                    "timestamp": clock.isoformat(),
                    "minute": minute, "team": possession, "player_id": player,
                    "event_type": "Shot", "x": round(ball_x, 2), "y": round(ball_y, 2),
                    "outcome": "Goal" if shot_success else "Miss"
                })
                sequence_num += 1
                if shot_success:
                    score[possession] += 1
                    ball_x, ball_y = 50.0, 50.0
                else:
                    ball_x, ball_y = goal_x, 50.0
                possession = defense_team
                continue
            
            dx = random.uniform(-15, 25) * direction
            dy = random.uniform(-20, 20)
            target_x = max(0.0, min(100.0, ball_x + dx))
            target_y = max(0.0, min(100.0, ball_y + dy))
            
            dist = math.hypot(target_x - ball_x, target_y - ball_y)
            displayed_diff = min(0.95, max(0.05, dist * 0.008))
            
            actual_diff = min(0.95, displayed_diff + hidden_pass_penalty)
            is_success = random.random() > actual_diff
            
            passes_attempted += 1
            if is_success:
                passes_completed += 1
            
            events.append({
                "event_id": f"EVT-{match_id}-{sequence_num:04d}",
                "timestamp": clock.isoformat(),
                "minute": minute, "team": possession, "player_id": player,
                "event_type": "Pass",
                "start_x": round(ball_x, 2), "start_y": round(ball_y, 2),
                "end_x": round(target_x, 2), "end_y": round(target_y, 2),
                "outcome": "Success" if is_success else "Failure",
                "pass_difficulty": round(displayed_diff, 2) 
            })
            sequence_num += 1
            
            if is_success:
                ball_x, ball_y = target_x, target_y
            else:
                clock += timedelta(seconds=1)
                seconds_simulated += 1
                events.append({
                    "event_id": f"EVT-{match_id}-{sequence_num:04d}",
                    "timestamp": clock.isoformat(),
                    "minute": minute, "team": defense_team,
                    "player_id": random.choice(ROSTERS[defense_team]),
                    "event_type": random.choice(["Interception", "Tackle"]),
                    "x": round(target_x, 2), "y": round(target_y, 2),
                    "outcome": "Success"
                })
                sequence_num += 1
                possession, ball_x, ball_y = defense_team, target_x, target_y

    pass_acc = (passes_completed / max(1, passes_attempted)) * 100
    
    if out_events:
        with open(out_events, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
            
    return pass_acc, score

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    acc, score = generate_match(args.seed, f"m_{args.seed}", "match_events.jsonl", "ground_truth.json")
    print(f"Seed: {args.seed} | Pass Accuracy: {acc:.1f}% | Score: {score}")
