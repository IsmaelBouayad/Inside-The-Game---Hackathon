from collections import deque

PRESS_TYPES = ("Interception", "Tackle", "Pressure")
DEFAULT_TEAMS = ("Meteor City", "Nova FC")
OTHER = {DEFAULT_TEAMS[0]: DEFAULT_TEAMS[1], DEFAULT_TEAMS[1]: DEFAULT_TEAMS[0]}


def in_own_third(team: str, x: float, home_team: str = "Meteor City") -> bool:
    """Home team defends x < 33, Away team defends x > 67."""
    return x < 33.0 if team == home_team else x > 67.0


class OnlineShiftDetector:
    """
    Config-driven Causal High-Press detector + Continuous Momentum Shift Index (Track 2).
    Supports arbitrary team pairings via `teams=(home_team, away_team)`.
    """

    def __init__(self, entry_window=3, exit_window=8, entry_acc=0.60, min_passes=3, min_press=7,
                 exit_acc=0.75, exit_min_passes=5, exit_press_max=1,
                 confirm_entry=1, confirm_exit=2, min_duration=5,
                 teams: tuple[str, str] = DEFAULT_TEAMS):
        self.teams = (teams[0], teams[1])
        self.home_team, self.away_team = self.teams[0], self.teams[1]
        self.other = {self.home_team: self.away_team, self.away_team: self.home_team}
        self.entry_window, self.exit_window = entry_window, exit_window
        self.entry_acc, self.min_passes, self.min_press = entry_acc, min_passes, min_press
        self.exit_acc, self.exit_min_passes, self.exit_press_max = exit_acc, exit_min_passes, exit_press_max
        self.confirm_entry, self.confirm_exit, self.min_duration = confirm_entry, confirm_exit, min_duration
        self.keep = max(entry_window, exit_window)
        self.buffer = deque()
        self.state, self.press_team, self.entry_minute = "Normal", None, None
        self._last_minute = None
        self._entry_streak = {self.home_team: 0, self.away_team: 0}
        self._exit_streak = 0
        self.momentum_history: list[dict] = []
        self.peak_swing: dict = {"minute": 0, "delta": 0.0, "team": self.home_team, "value": 0.0}

    def _window(self, minute, width):
        return [e for e in self.buffer if minute - width <= e["minute"] <= minute - 1]

    def _facts(self, victim, minute, width):
        presser = self.other[victim]
        w = self._window(minute, width)
        passes = [e for e in w if e["team"] == victim and e["event_type"] == "Pass"
                  and in_own_third(victim, e.get("start_x", 50), self.home_team)]
        press = [e for e in w if e["team"] == presser and e["event_type"] in PRESS_TYPES
                 and in_own_third(victim, e.get("x", e.get("start_x", 50)), self.home_team)]
        acc = (sum(e["outcome"] == "Success" for e in passes) / len(passes)) if passes else None
        return passes, press, acc

    def compute_momentum(self, minute: int) -> dict:
        w = [e for e in self.buffer if max(0, minute - 4) <= e["minute"] <= minute]
        score_home, score_away = 0.0, 0.0
        for e in w:
            etype = e["event_type"]
            team = e["team"]
            weight = 0.0
            if etype == "Pass" and e.get("outcome") == "Success":
                end_x = e.get("end_x", 50.0)
                in_att_third = (end_x > 67.0) if team == self.home_team else (end_x < 33.0)
                weight = 2.5 if in_att_third else 1.0
            elif etype in PRESS_TYPES:
                weight = 3.0
            elif etype == "Shot":
                weight = 18.0 if e.get("outcome") == "Goal" else 6.0

            if team == self.home_team:
                score_home += weight
            elif team == self.away_team:
                score_away += weight

        total = score_home + score_away
        raw_index = round(((score_home - score_away) / total) * 100.0, 1) if total > 0 else 0.0
        prev_val = self.momentum_history[-1]["momentum_index"] if self.momentum_history else 0.0
        delta = round(raw_index - prev_val, 1)

        point = {
            "minute": minute,
            "momentum_index": raw_index,
            "delta": delta,
            "dominant_team": self.home_team if raw_index >= 0 else self.away_team,
            "regime": self.state
        }
        self.momentum_history.append(point)

        if abs(delta) > abs(self.peak_swing["delta"]) and minute >= 5:
            self.peak_swing = {
                "minute": minute,
                "delta": delta,
                "team": self.home_team if delta > 0 else self.away_team,
                "value": raw_index
            }
        return point

    def process_event(self, event):
        minute = event["minute"]
        self.buffer.append(event)
        while self.buffer and self.buffer[0]["minute"] < minute - self.keep:
            self.buffer.popleft()
        if minute == self._last_minute:
            return None
        self._last_minute = minute
        self.compute_momentum(minute)
        return self._entry(minute) if self.state == "Normal" else self._exit(minute)

    def _entry(self, minute):
        fired = None
        for victim in self.teams:
            passes, press, acc = self._facts(victim, minute, self.entry_window)
            ok = (len(passes) >= self.min_passes and acc is not None and acc <= self.entry_acc and len(press) >= self.min_press)
            self._entry_streak[victim] = self._entry_streak[victim] + 1 if ok else 0
            if self._entry_streak[victim] >= self.confirm_entry and fired is None:
                fired = (victim, passes, press, acc)
        if not fired:
            return None
        victim, passes, press, acc = fired
        self.state, self.press_team, self.entry_minute = "High Press", self.other[victim], minute
        self._exit_streak = 0
        self._entry_streak = {self.home_team: 0, self.away_team: 0}
        failed = [e for e in passes if e["outcome"] == "Failure"]
        return {
            "minute": minute, "type": "High Press", "status": "ENTERED",
            "exit_reason": None,
            "team": self.press_team, "victim": victim,
            "trigger_event_ids": [e["event_id"] for e in press[-3:]] + [e["event_id"] for e in failed[-3:]],
            "stats": {"pass_acc": round(acc, 2), "def_actions": len(press), "n_passes": len(passes)}
        }

    def _exit(self, minute):
        victim = self.other[self.press_team]
        passes, press, acc = self._facts(victim, minute, self.exit_window)
        recent_press = [e for e in press if e["minute"] >= minute - self.entry_window]
        recovered = (len(passes) >= self.exit_min_passes and acc is not None and acc > self.exit_acc)
        exhausted = len(recent_press) <= self.exit_press_max
        self._exit_streak = self._exit_streak + 1 if (recovered or exhausted) else 0
        if self._exit_streak < self.confirm_exit or (minute - self.entry_minute) < self.min_duration:
            return None
        team = self.press_team
        self.state, self.press_team, self.entry_minute = "Normal", None, None
        exit_reason = "recovered" if recovered else "exhausted"
        ok_passes = [e for e in passes if e["outcome"] == "Success"]
        return {
            "minute": minute, "type": "High Press", "status": "EXITED",
            "exit_reason": exit_reason,
            "team": team, "victim": victim,
            "trigger_event_ids": [e["event_id"] for e in ok_passes[-3:]],
            "stats": {
                "pass_acc": None if acc is None else round(acc, 2),
                "def_actions": len(recent_press),
                "n_passes": len(passes)
            }
        }
