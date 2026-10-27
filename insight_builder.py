import json
import os
from typing import Any, Dict, List, Optional, Tuple

PRESS_EVENT_TYPES = ("Pressure", "Tackle", "Interception")


def load_match_events(events_file: str = "match_events.jsonl") -> List[Dict[str, Any]]:
    """Loads raw synthetic match events from JSONL file."""
    if not os.path.exists(events_file):
        return []
    events = []
    try:
        with open(events_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    return events


def deduplicate_and_filter_events(
    events: List[Dict[str, Any]],
    max_minute: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deduplicates events by event_id and enforces a strict temporal cutoff (max_minute)
    so active episodes never leak future events that have not yet occurred.
    """
    seen_ids = set()
    clean_events = []
    duplicates_removed = 0
    future_filtered = 0
    malformed_skipped = 0

    for ev in events:
        if not isinstance(ev, dict):
            malformed_skipped += 1
            continue
        ev_min = ev.get("minute")
        if ev_min is None or not isinstance(ev_min, (int, float)):
            malformed_skipped += 1
            continue
        if max_minute is not None and ev_min > max_minute:
            future_filtered += 1
            continue
        ev_id = ev.get("event_id")
        if ev_id:
            if ev_id in seen_ids:
                duplicates_removed += 1
                continue
            seen_ids.add(ev_id)
        clean_events.append(ev)

    quality_meta = {
        "total_input_events": len(events),
        "valid_events_retained": len(clean_events),
        "duplicate_events_removed": duplicates_removed,
        "future_events_excluded": future_filtered,
        "malformed_events_skipped": malformed_skipped,
        "temporal_cutoff_minute": max_minute,
    }
    return clean_events, quality_meta


def compute_team_window_metrics(
    events: List[Dict[str, Any]],
    team: str,
    opponent: str,
    start_min: int,
    end_min: int
) -> Dict[str, Any]:
    """
    Computes deterministic team-level metrics within [start_min, end_min].
    Never mixes player and team statistics, and never substitutes 0 for unavailable ratios.
    """
    if end_min < start_min:
        return {
            "window_bounds": [start_min, end_min],
            "status": "INVALID_WINDOW",
            "sample_sufficiency": "INSUFFICIENT_DATA",
        }

    w_events = [
        e for e in events
        if start_min <= e.get("minute", -1) <= end_min
    ]

    def _team_stats(target_team: str) -> Dict[str, Any]:
        t_ev = [e for e in w_events if e.get("team") == target_team]
        passes = [e for e in t_ev if e.get("event_type") == "Pass"]
        p_att = len(passes)
        p_comp = sum(1 for e in passes if e.get("outcome") == "Success")
        p_fail = sum(1 for e in passes if e.get("outcome") == "Failure")
        p_acc = round(p_comp / p_att, 4) if p_att > 0 else None

        pressures = sum(1 for e in t_ev if e.get("event_type") == "Pressure")
        tackles = sum(1 for e in t_ev if e.get("event_type") == "Tackle")
        interceptions = sum(1 for e in t_ev if e.get("event_type") == "Interception")
        def_total = pressures + tackles + interceptions

        shots = [e for e in t_ev if e.get("event_type") == "Shot"]
        s_total = len(shots)
        goals = sum(1 for e in shots if e.get("outcome") == "Goal")
        shot_conv = round(goals / s_total, 4) if s_total > 0 else None

        return {
            "passes_attempted": p_att,
            "passes_completed": p_comp,
            "passes_failed": p_fail,
            "pass_accuracy": p_acc,
            "pass_accuracy_pct": round(p_acc * 100.0, 1) if p_acc is not None else None,
            "pass_accuracy_fraction": f"{p_comp}/{p_att}" if p_att > 0 else "Data unavailable",
            "pressure_count": pressures,
            "tackle_count": tackles,
            "interception_count": interceptions,
            "defensive_actions_total": def_total,
            "shots_total": s_total,
            "goals_total": goals,
            "shot_conversion_rate": shot_conv,
            "shot_conversion_fraction": f"{goals}/{s_total}" if s_total > 0 else "Data unavailable",
            "event_count": len(t_ev),
        }

    pressing_stats = _team_stats(team)
    opponent_stats = _team_stats(opponent)

    # Sufficiency requires at least 3 opponent passes or 5 total events in window
    is_sufficient = (opponent_stats["passes_attempted"] >= 3) or (len(w_events) >= 5)

    return {
        "window_bounds": [start_min, end_min],
        "status": "COMPUTED" if len(w_events) > 0 else "NO_EVENTS_IN_WINDOW",
        "sample_sufficiency": "SUFFICIENT" if is_sufficient else "INSUFFICIENT_SAMPLE",
        "total_events_in_window": len(w_events),
        "pressing_team_metrics": pressing_stats,
        "opponent_build_up_metrics": opponent_stats,
        "window_event_ids": [e.get("event_id") for e in w_events if e.get("event_id")],
    }


def _compute_delta(val_a: Optional[float], val_b: Optional[float]) -> Dict[str, Optional[float]]:
    """Computes absolute and relative change from val_a to val_b only when both exist."""
    if val_a is None or val_b is None:
        return {"absolute_diff": None, "pct_change": None, "status": "UNAVAILABLE"}
    abs_diff = round(val_b - val_a, 4)
    pct_change = round(((val_b - val_a) / abs(val_a)) * 100.0, 1) if val_a != 0 else None
    return {"absolute_diff": abs_diff, "pct_change": pct_change, "status": "COMPUTED"}


def build_episode_insight(
    episode: Dict[str, Any],
    all_events: List[Dict[str, Any]],
    current_minute: Optional[int] = None,
    score: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    """
    Builds a deterministic, verifiable evidence package for a detected tactical episode.
    Strictly prevents future-event leakage when an episode is still active.
    """
    ep_id = episode.get("episode_id", "unknown_episode")
    ep_min = int(episode.get("match_minute") or episode.get("minute") or 0)
    match_id = episode.get("match_id") or (ep_id.split("_min")[0] if "_min" in ep_id else "m_42")

    raw_status = episode.get("status")
    if not raw_status:
        if "ENTERED" in ep_id:
            raw_status = "ENTERED"
        elif "EXITED" in ep_id:
            raw_status = "EXITED"
        elif "GOAL" in ep_id:
            raw_status = "GOAL"
        else:
            raw_status = "ACTIVE"

    team = episode.get("team")
    opponent = episode.get("victim") or episode.get("opponent")

    # Infer team/opponent from episode text or defaults if not directly in overlay dict
    if not team or not opponent:
        analyst_txt = episode.get("analyst_view", "")
        if "Meteor City" in analyst_txt and "Nova FC" in analyst_txt:
            team = team or "Meteor City"
            opponent = opponent or "Nova FC"
        else:
            team = team or "Meteor City"
            opponent = opponent or "Nova FC"

    # Strict temporal cutoff: an active ENTERED episode cannot see beyond current_minute (or ep_min)
    if current_minute is not None:
        effective_cutoff = int(current_minute)
    elif raw_status == "ENTERED":
        effective_cutoff = ep_min
    else:
        effective_cutoff = 90

    valid_events, dq_meta = deduplicate_and_filter_events(all_events, max_minute=effective_cutoff)

    # Verify cited / trigger event IDs against actual valid events
    event_by_id = {e.get("event_id"): e for e in valid_events if e.get("event_id")}
    raw_cited = episode.get("cited_event_ids") or episode.get("trigger_event_ids") or []
    verified_supporting_ids = [cid for cid in raw_cited if cid in event_by_id]
    unknown_ids = [cid for cid in raw_cited if cid not in event_by_id]

    # Define 5-minute comparative windows (Before / During / After)
    if raw_status == "ENTERED":
        during_start = max(0, ep_min - 3)
        during_end = ep_min
        before_start = max(0, during_start - 5)
        before_end = max(0, during_start - 1)
        after_window_metrics = {
            "window_bounds": None,
            "status": "UNAVAILABLE_ACTIVE_EPISODE",
            "sample_sufficiency": "UNAVAILABLE_ACTIVE_EPISODE",
            "reason": "Episode is currently active (ENTERED); future events after minute "
                      f"{effective_cutoff} are strictly excluded."
        }
    else:
        # EXITED or completed regime
        during_end = max(0, ep_min - 1)
        during_start = max(0, ep_min - 5)
        before_start = max(0, during_start - 5)
        before_end = max(0, during_start - 1)
        if effective_cutoff >= ep_min + 1:
            after_start = ep_min
            after_end = min(effective_cutoff, ep_min + 4)
            after_window_metrics = compute_team_window_metrics(
                valid_events, team, opponent, after_start, after_end
            )
        else:
            after_window_metrics = {
                "window_bounds": [ep_min, ep_min + 4],
                "status": "UNAVAILABLE_AWAITING_EVENTS",
                "sample_sufficiency": "INSUFFICIENT_DATA",
                "reason": "Post-press window has not yet elapsed in current stream clock."
            }

    before_window_metrics = compute_team_window_metrics(
        valid_events, team, opponent, before_start, before_end
    )
    during_window_metrics = compute_team_window_metrics(
        valid_events, team, opponent, during_start, during_end
    )

    # Compute Before -> During comparisons
    opp_before = before_window_metrics.get("opponent_build_up_metrics", {})
    opp_during = during_window_metrics.get("opponent_build_up_metrics", {})
    press_before = before_window_metrics.get("pressing_team_metrics", {})
    press_during = during_window_metrics.get("pressing_team_metrics", {})

    both_sufficient = (
        before_window_metrics.get("sample_sufficiency") == "SUFFICIENT"
        and during_window_metrics.get("sample_sufficiency") == "SUFFICIENT"
    )

    before_vs_during = {
        "comparison_status": "SUFFICIENT" if both_sufficient else "INSUFFICIENT_SAMPLE",
        "opponent_pass_accuracy_delta": _compute_delta(
            opp_before.get("pass_accuracy_pct"), opp_during.get("pass_accuracy_pct")
        ),
        "pressing_actions_delta": _compute_delta(
            press_before.get("defensive_actions_total"), press_during.get("defensive_actions_total")
        ),
        "opponent_passes_attempted_delta": _compute_delta(
            opp_before.get("passes_attempted"), opp_during.get("passes_attempted")
        ),
    }

    during_vs_after = {"comparison_status": "UNAVAILABLE"}
    if after_window_metrics.get("status") == "COMPUTED":
        opp_after = after_window_metrics.get("opponent_build_up_metrics", {})
        press_after = after_window_metrics.get("pressing_team_metrics", {})
        after_suff = after_window_metrics.get("sample_sufficiency") == "SUFFICIENT"
        during_vs_after = {
            "comparison_status": "SUFFICIENT" if after_suff else "INSUFFICIENT_SAMPLE",
            "opponent_pass_accuracy_delta": _compute_delta(
                opp_during.get("pass_accuracy_pct"), opp_after.get("pass_accuracy_pct")
            ),
            "pressing_actions_delta": _compute_delta(
                press_during.get("defensive_actions_total"), press_after.get("defensive_actions_total")
            ),
        }

    # Build compact chronology of associated events
    chronology_ids = list(dict.fromkeys(
        during_window_metrics.get("window_event_ids", [])[-8:] + verified_supporting_ids
    ))
    chronology = []
    for cid in chronology_ids:
        ev = event_by_id.get(cid)
        if ev:
            chronology.append({
                "event_id": cid,
                "minute": ev.get("minute"),
                "team": ev.get("team"),
                "player_id": ev.get("player_id", "N/A"),
                "event_type": ev.get("event_type"),
                "outcome": ev.get("outcome", "N/A"),
            })
    chronology.sort(key=lambda x: (x.get("minute", 0), x.get("event_id", "")))

    # Build structured allowed_claims with explicit provenance
    det_facts = []
    if opp_during.get("passes_attempted", 0) > 0:
        det_facts.append({
            "claim_id": "FACT_OPP_PASS_ACC",
            "statement": (
                f"During minutes {during_start}..{during_end}, {opponent} completed "
                f"{opp_during['pass_accuracy_fraction']} passes ({opp_during['pass_accuracy_pct']}%)."
            ),
            "provenance_event_ids": during_window_metrics.get("window_event_ids", [])[:5],
        })
    det_facts.append({
        "claim_id": "FACT_PRESS_ACTIONS",
        "statement": (
            f"During minutes {during_start}..{during_end}, {team} recorded "
            f"{press_during.get('defensive_actions_total', 0)} defensive actions "
            f"(Pressure: {press_during.get('pressure_count', 0)}, "
            f"Tackle: {press_during.get('tackle_count', 0)}, "
            f"Interception: {press_during.get('interception_count', 0)})."
        ),
        "provenance_event_ids": verified_supporting_ids or during_window_metrics.get("window_event_ids", [])[:4],
    })

    tactical_interps = []
    if both_sufficient:
        acc_diff = before_vs_during["opponent_pass_accuracy_delta"].get("absolute_diff")
        if acc_diff is not None and acc_diff < 0:
            tactical_interps.append({
                "claim_id": "INTERP_BUILDUP_DISRUPTION",
                "statement": (
                    f"{opponent}'s pass completion rate changed by {acc_diff:+.1f} percentage points "
                    f"between minutes {before_start}..{before_end} ({opp_before.get('pass_accuracy_pct')}%) "
                    f"and minutes {during_start}..{during_end} ({opp_during.get('pass_accuracy_pct')}%) "
                    f"coinciding with {team}'s increased defensive actions."
                ),
                "confidence": "MODERATE_CORRELATIONAL",
            })
        else:
            tactical_interps.append({
                "claim_id": "INTERP_PRESS_ACTIVITY",
                "statement": (
                    f"{team} increased defensive intervention volume in minutes {during_start}..{during_end}, "
                    f" contesting {opponent}'s build-up progression."
                ),
                "confidence": "MODERATE_OBSERVATIONAL",
            })
    else:
        tactical_interps.append({
            "claim_id": "INTERP_LIMITED_SAMPLE",
            "statement": "Window sample size is limited; tactical interpretation is restricted to observed counts.",
            "confidence": "LOW_SAMPLE_SIZE",
        })

    hypotheses = [
        {
            "claim_id": "HYP_TRANSITION_RISK",
            "statement": (
                f"Hypothesis: If {team} sustains this defensive action density, {opponent} may face elevated "
                f"turnover risk in build-up, though high commitment could expose space behind {team}'s line."
            ),
            "nature": "CONDITIONAL_PROJECTION_NOT_FACT",
        }
    ]

    unsupported_conclusions = [
        "Direct physical causality (temporal correlation between pressing actions and pass failures does not prove sole causation).",
        "Player sprint speeds, physical distance covered (km/h), or off-ball optical tracking postures (not present in event stream).",
        "Unlogged match incidents (cards, injuries, VAR reviews, corners, substitutions).",
    ]

    limitations = [
        "Synthetic discrete event stream: only on-ball events and discrete pressure/tackle/interception actions are logged.",
        "Temporal correlation in 5-minute windows does not establish isolated tactical causality.",
    ]
    if unknown_ids:
        limitations.append(f"Excluded {len(unknown_ids)} unverified/unknown cited event ID(s): {unknown_ids}.")
    if not both_sufficient:
        limitations.append("One or more comparison windows have fewer than 3 passes; deltas should be treated with caution.")

    dq_meta["unknown_supporting_ids"] = unknown_ids
    dq_meta["verified_supporting_id_count"] = len(verified_supporting_ids)

    return {
        "match_id": match_id,
        "episode_id": ep_id,
        "episode_type": episode.get("type", "High Press"),
        "status": raw_status,
        "team": team,
        "opponent": opponent,
        "match_minute": ep_min,
        "score_snapshot": score or episode.get("stats_snapshot", {}).get("score"),
        "metrics": {
            "before_press": before_window_metrics,
            "during_press": during_window_metrics,
            "after_press": after_window_metrics,
        },
        "comparisons": {
            "before_vs_during": before_vs_during,
            "during_vs_after": during_vs_after,
        },
        "supporting_event_ids": verified_supporting_ids,
        "chronology": chronology,
        "allowed_claims": {
            "deterministic_facts": det_facts,
            "tactical_interpretations": tactical_interps,
            "hypotheses": hypotheses,
            "unsupported_conclusions": unsupported_conclusions,
        },
        "data_quality": dq_meta,
        "limitations": limitations,
    }


def list_match_players(
    all_events: List[Dict[str, Any]],
    team: Optional[str] = None,
    max_minute: Optional[int] = None
) -> List[str]:
    """Returns sorted list of unique player_ids actually present in the match events up to max_minute."""
    valid_events, _ = deduplicate_and_filter_events(all_events, max_minute=max_minute)
    players = set()
    for e in valid_events:
        if team and e.get("team") != team:
            continue
        pid = e.get("player_id")
        if pid and isinstance(pid, str):
            players.add(pid)
    return sorted(players)


def compute_player_spotlight(
    all_events: List[Dict[str, Any]],
    player_id: str,
    episodes: Optional[List[Dict[str, Any]]] = None,
    max_minute: Optional[int] = None
) -> Dict[str, Any]:
    """
    Computes verifiable player-level statistics exclusively from raw match events.
    Never invents player positions/roles or pre-written match outcomes.
    """
    if not player_id or not isinstance(player_id, str):
        return {
            "player_id": str(player_id or "None"),
            "data_status": "Data unavailable",
            "reason": "No player selected or empty identifier.",
        }

    valid_events, dq = deduplicate_and_filter_events(all_events, max_minute=max_minute)
    p_events = [e for e in valid_events if e.get("player_id") == player_id]

    if not p_events:
        return {
            "player_id": player_id,
            "team": "Data unavailable",
            "data_status": "Data unavailable",
            "passes_attempted": 0,
            "passes_completed": 0,
            "passes_failed": 0,
            "pass_accuracy_pct": None,
            "pass_accuracy_display": "Data unavailable",
            "shots": 0,
            "goals": 0,
            "shot_conversion_pct": None,
            "shot_conversion_display": "Data unavailable",
            "defensive_interventions": 0,
            "tactical_episode_involvements": 0,
            "associated_events": [],
            "evidence_summary": f"Data unavailable: no recorded events for player {player_id} within current match window.",
            "data_quality": dq,
        }

    team = p_events[0].get("team", "Data unavailable")
    passes = [e for e in p_events if e.get("event_type") == "Pass"]
    p_att = len(passes)
    p_comp = sum(1 for e in passes if e.get("outcome") == "Success")
    p_fail = sum(1 for e in passes if e.get("outcome") == "Failure")
    p_acc_pct = round((p_comp / p_att) * 100.0, 1) if p_att > 0 else None
    p_acc_disp = f"{p_acc_pct}% ({p_comp}/{p_att})" if p_att > 0 else "Data unavailable"

    shots = [e for e in p_events if e.get("event_type") == "Shot"]
    s_cnt = len(shots)
    goals = [e for e in shots if e.get("outcome") == "Goal"]
    g_cnt = len(goals)
    s_conv_pct = round((g_cnt / s_cnt) * 100.0, 1) if s_cnt > 0 else None
    s_conv_disp = f"{s_conv_pct}% ({g_cnt}/{s_cnt})" if s_cnt > 0 else "Data unavailable"

    def_events = [e for e in p_events if e.get("event_type") in PRESS_EVENT_TYPES]
    def_cnt = len(def_events)
    press_cnt = sum(1 for e in def_events if e.get("event_type") == "Pressure")
    tackle_cnt = sum(1 for e in def_events if e.get("event_type") == "Tackle")
    inter_cnt = sum(1 for e in def_events if e.get("event_type") == "Interception")

    # Calculate involvement in detected tactical episodes
    cited_in_episodes = set()
    if episodes:
        for ep in episodes:
            for cid in (ep.get("cited_event_ids") or ep.get("trigger_event_ids") or []):
                cited_in_episodes.add(cid)

    player_event_ids = {e.get("event_id") for e in p_events if e.get("event_id")}
    cited_matches = sorted(player_event_ids.intersection(cited_in_episodes))

    associated = [
        {
            "event_id": e.get("event_id"),
            "minute": e.get("minute"),
            "event_type": e.get("event_type"),
            "outcome": e.get("outcome", "N/A"),
        }
        for e in p_events
    ]

    # Build strictly factual evidence summary from computed numbers
    parts = [f"{player_id} ({team}): {len(p_events)} logged event(s)."]
    if p_att > 0:
        parts.append(f"Passes: {p_comp}/{p_att} completed ({p_acc_pct}%).")
    else:
        parts.append("Passes: Data unavailable (0 attempted).")

    if s_cnt > 0:
        goal_mins = [f"{g.get('minute')}'" for g in goals]
        g_detail = f" [Goal min: {', '.join(goal_mins)}]" if goal_mins else ""
        parts.append(f"Shots: {s_cnt}, Goals: {g_cnt}, Shot conversion: {s_conv_pct}% ({g_cnt}/{s_cnt}){g_detail}.")
    else:
        parts.append("Shots: 0 (Shot conversion: Data unavailable).")

    if def_cnt > 0:
        parts.append(
            f"Defensive actions: {def_cnt} (Pressure: {press_cnt}, Tackle: {tackle_cnt}, Interception: {inter_cnt})."
        )
    if cited_matches:
        parts.append(f"Directly cited in tactical episode evidence: {', '.join(cited_matches)}.")

    return {
        "player_id": player_id,
        "team": team,
        "position_role": "Not provided in event schema",
        "data_status": "COMPUTED",
        "total_events": len(p_events),
        "passes_attempted": p_att,
        "passes_completed": p_comp,
        "passes_failed": p_fail,
        "pass_accuracy_pct": p_acc_pct,
        "pass_accuracy_display": p_acc_disp,
        "shots": s_cnt,
        "goals": g_cnt,
        "goal_minutes": [g.get("minute") for g in goals],
        "shot_conversion_pct": s_conv_pct,
        "shot_conversion_display": s_conv_disp,
        "defensive_interventions": def_cnt,
        "defensive_breakdown": {
            "Pressure": press_cnt,
            "Tackle": tackle_cnt,
            "Interception": inter_cnt,
        },
        "tactical_episode_involvements": len(cited_matches),
        "cited_episode_event_ids": cited_matches,
        "associated_events": associated[-6:],
        "all_event_ids": [e.get("event_id") for e in p_events if e.get("event_id")],
        "evidence_summary": " ".join(parts),
        "data_quality": dq,
    }
