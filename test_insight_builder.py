import asyncio
from detector import OnlineShiftDetector
import insight_builder
import app
import pipeline


CONTROLLED_EVENTS = [
    {"event_id": "E-01", "match_id": "m_test", "minute": 5, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 75.0, "outcome": "Success"},
    {"event_id": "E-02", "match_id": "m_test", "minute": 6, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 72.0, "outcome": "Success"},
    {"event_id": "E-03", "match_id": "m_test", "minute": 7, "team": "Nova FC", "player_id": "N-04", "event_type": "Pass", "start_x": 70.0, "outcome": "Success"},
    {"event_id": "E-04", "match_id": "m_test", "minute": 8, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 74.0, "outcome": "Success"},
    {"event_id": "E-05", "match_id": "m_test", "minute": 9, "team": "Nova FC", "player_id": "N-04", "event_type": "Pass", "start_x": 78.0, "outcome": "Failure"},
    {"event_id": "E-06", "match_id": "m_test", "minute": 9, "team": "Meteor City", "player_id": "M-11", "event_type": "Pressure", "x": 76.0, "outcome": "Won"},
    {"event_id": "E-07", "match_id": "m_test", "minute": 10, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 80.0, "outcome": "Failure"},
    {"event_id": "E-08", "match_id": "m_test", "minute": 10, "team": "Nova FC", "player_id": "N-04", "event_type": "Pass", "start_x": 79.0, "outcome": "Failure"},
    {"event_id": "E-09", "match_id": "m_test", "minute": 11, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 75.0, "outcome": "Failure"},
    {"event_id": "E-10", "match_id": "m_test", "minute": 12, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 72.0, "outcome": "Success"},
    {"event_id": "E-11", "match_id": "m_test", "minute": 10, "team": "Meteor City", "player_id": "M-11", "event_type": "Pressure", "x": 80.0, "outcome": "Won"},
    {"event_id": "E-12", "match_id": "m_test", "minute": 10, "team": "Meteor City", "player_id": "M-02", "event_type": "Tackle", "x": 79.0, "outcome": "Won"},
    {"event_id": "E-13", "match_id": "m_test", "minute": 11, "team": "Meteor City", "player_id": "M-11", "event_type": "Interception", "x": 75.0, "outcome": "Won"},
    {"event_id": "E-14", "match_id": "m_test", "minute": 11, "team": "Meteor City", "player_id": "M-02", "event_type": "Pressure", "x": 74.0, "outcome": "Won"},
    {"event_id": "E-15", "match_id": "m_test", "minute": 11, "team": "Meteor City", "player_id": "M-05", "event_type": "Pressure", "x": 73.0, "outcome": "Won"},
    {"event_id": "E-16", "match_id": "m_test", "minute": 12, "team": "Meteor City", "player_id": "M-05", "event_type": "Tackle", "x": 71.0, "outcome": "Won"},
    {"event_id": "E-17", "match_id": "m_test", "minute": 12, "team": "Meteor City", "player_id": "M-11", "event_type": "Pressure", "x": 70.0, "outcome": "Won"},
    {"event_id": "E-18", "match_id": "m_test", "minute": 12, "team": "Meteor City", "player_id": "M-11", "event_type": "Shot", "x": 88.0, "outcome": "Goal"},
    {"event_id": "E-19", "match_id": "m_test", "minute": 14, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 70.0, "outcome": "Success"},
    {"event_id": "E-20", "match_id": "m_test", "minute": 15, "team": "Nova FC", "player_id": "N-08", "event_type": "Pass", "start_x": 68.0, "outcome": "Success"},
    {"event_id": "E-21", "match_id": "m_test", "minute": 16, "team": "Nova FC", "player_id": "N-04", "event_type": "Pass", "start_x": 65.0, "outcome": "Success"},
]


def test_ib_01_pass_accuracy_numerator_denominator():
    w = insight_builder.compute_team_window_metrics(CONTROLLED_EVENTS, "Meteor City", "Nova FC", 5, 9)
    opp = w["opponent_build_up_metrics"]
    assert opp["passes_attempted"] == 5
    assert opp["passes_completed"] == 4
    assert opp["passes_failed"] == 1
    assert opp["pass_accuracy"] == 0.80
    assert opp["pass_accuracy_pct"] == 80.0
    assert opp["pass_accuracy_fraction"] == "4/5"


def test_ib_02_player_stats_from_source_events():
    sp_m11 = insight_builder.compute_player_spotlight(CONTROLLED_EVENTS, "M-11")
    assert sp_m11["data_status"] == "COMPUTED"
    assert sp_m11["team"] == "Meteor City"
    assert sp_m11["shots"] == 1
    assert sp_m11["goals"] == 1
    assert sp_m11["shot_conversion_pct"] == 100.0
    assert sp_m11["defensive_interventions"] == 4
    assert sp_m11["defensive_breakdown"] == {"Pressure": 3, "Tackle": 0, "Interception": 1}

    sp_n08 = insight_builder.compute_player_spotlight(CONTROLLED_EVENTS, "N-08")
    assert sp_n08["passes_attempted"] == 8
    assert sp_n08["passes_completed"] == 6
    assert sp_n08["pass_accuracy_pct"] == 75.0
    assert sp_n08["shots"] == 0
    assert sp_n08["shot_conversion_pct"] is None
    assert sp_n08["shot_conversion_display"] == "Data unavailable"


def test_ib_03_missing_player_returns_data_unavailable():
    sp_missing = insight_builder.compute_player_spotlight(CONTROLLED_EVENTS, "UNKNOWN-99")
    assert sp_missing["data_status"] == "Data unavailable"
    assert sp_missing["pass_accuracy_pct"] is None
    assert sp_missing["shot_conversion_pct"] is None
    assert "Data unavailable" in sp_missing["evidence_summary"]


def test_ib_04_team_with_zero_shots_or_zero_passes():
    w = insight_builder.compute_team_window_metrics(CONTROLLED_EVENTS, "Meteor City", "Nova FC", 5, 9)
    prs = w["pressing_team_metrics"]
    assert prs["passes_attempted"] == 0
    assert prs["pass_accuracy"] is None
    assert prs["pass_accuracy_fraction"] == "Data unavailable"
    assert prs["shots_total"] == 0
    assert prs["shot_conversion_rate"] is None
    assert prs["shot_conversion_fraction"] == "Data unavailable"


def test_ib_05_duplicate_events_deduplicated():
    dup_stream = CONTROLLED_EVENTS + [CONTROLLED_EVENTS[0], CONTROLLED_EVENTS[1]]
    clean, dq = insight_builder.deduplicate_and_filter_events(dup_stream)
    assert len(clean) == len(CONTROLLED_EVENTS)
    assert dq["duplicate_events_removed"] == 2


def test_ib_06_unknown_supporting_ids_flagged():
    ep = {
        "episode_id": "m_test_min13_ENTERED",
        "match_minute": 13,
        "status": "ENTERED",
        "team": "Meteor City",
        "victim": "Nova FC",
        "cited_event_ids": ["E-11", "EVT-INVENTED-999"],
    }
    ins = insight_builder.build_episode_insight(ep, CONTROLLED_EVENTS, current_minute=13)
    assert ins["supporting_event_ids"] == ["E-11"]
    assert ins["data_quality"]["unknown_supporting_ids"] == ["EVT-INVENTED-999"]
    assert any("EVT-INVENTED-999" in lim for lim in ins["limitations"])


def test_ib_07_before_during_after_comparison_and_no_future_leakage():
    ep_active = {
        "episode_id": "m_test_min13_ENTERED",
        "match_minute": 13,
        "status": "ENTERED",
        "team": "Meteor City",
        "victim": "Nova FC",
        "cited_event_ids": ["E-11", "E-12"],
    }
    ins_active = insight_builder.build_episode_insight(ep_active, CONTROLLED_EVENTS, current_minute=13)
    assert ins_active["metrics"]["after_press"]["status"] == "UNAVAILABLE_ACTIVE_EPISODE"
    assert ins_active["data_quality"]["future_events_excluded"] == 3
    delta_acc = ins_active["comparisons"]["before_vs_during"]["opponent_pass_accuracy_delta"]["absolute_diff"]
    assert delta_acc == -55.0

    ep_exited = {
        "episode_id": "m_test_min13_EXITED",
        "match_minute": 13,
        "status": "EXITED",
        "team": "Meteor City",
        "victim": "Nova FC",
        "cited_event_ids": ["E-10"],
    }
    ins_exited = insight_builder.build_episode_insight(ep_exited, CONTROLLED_EVENTS, current_minute=18)
    assert ins_exited["metrics"]["after_press"]["status"] == "COMPUTED"
    assert ins_exited["metrics"]["after_press"]["opponent_build_up_metrics"]["passes_completed"] == 3


def test_ib_08_recap_rejects_invalid_ids_and_marks_fallback_honestly():
    async def _run():
        recap = await pipeline.generate_match_recap(
            "m_test",
            [{"episode_id": "m_test_min13_ENTERED", "match_minute": 13}],
            {"Meteor City": 1, "Nova FC": 0},
            use_llm=False
        )
        assert recap["recap_verified"] is False
        assert recap["verification_mode"] == "deterministic_fallback"
    asyncio.run(_run())


def test_ib_09_seed42_player_spotlight_matches_actual_goal_scorers():
    events_42 = insight_builder.load_match_events("match_events.jsonl")
    if events_42:
        sp_m11 = insight_builder.compute_player_spotlight(events_42, "M-11")
        sp_m02 = insight_builder.compute_player_spotlight(events_42, "M-02")
        assert sp_m11["goals"] == 1 and 51 in sp_m11["goal_minutes"]
        assert sp_m02["goals"] == 1 and 79 in sp_m02["goal_minutes"]
        html_m02 = app.render_player_spotlight("Meteor City", "M-02", all_events=events_42)
        assert "51', 79'" not in html_m02


def test_ib_10_e2e_synthetic_events_to_detector_to_insight_to_ui_html():
    det = OnlineShiftDetector(min_passes=3, min_press=5, entry_acc=0.60)
    alarms = []
    for ev in CONTROLLED_EVENTS:
        if ev["minute"] <= 13:
            a = det.process_event(ev)
            if a:
                alarms.append(a)
    a_end = det.process_event({"event_id": "E-18B", "minute": 13, "team": "Meteor City", "event_type": "Pass", "start_x": 50.0, "outcome": "Success"})
    if a_end:
        alarms.append(a_end)
    assert len(alarms) >= 1
    alarm = alarms[0]
    overlay = pipeline.generate_fallback_overlay(alarm, f"m_test_min{alarm['minute']}_{alarm['status']}")
    insight = insight_builder.build_episode_insight(overlay, CONTROLLED_EVENTS, current_minute=alarm["minute"])
    explorer_html = app.render_tactical_impact_explorer_html(insight)
    assert "TACTICAL IMPACT EXPLORER" in explorer_html
    assert insight["episode_id"] in explorer_html
    assert "BEFORE PRESS" in explorer_html
    assert "DURING PRESS" in explorer_html


ALL_INSIGHT_TESTS = [
    test_ib_01_pass_accuracy_numerator_denominator,
    test_ib_02_player_stats_from_source_events,
    test_ib_03_missing_player_returns_data_unavailable,
    test_ib_04_team_with_zero_shots_or_zero_passes,
    test_ib_05_duplicate_events_deduplicated,
    test_ib_06_unknown_supporting_ids_flagged,
    test_ib_07_before_during_after_comparison_and_no_future_leakage,
    test_ib_08_recap_rejects_invalid_ids_and_marks_fallback_honestly,
    test_ib_09_seed42_player_spotlight_matches_actual_goal_scorers,
    test_ib_10_e2e_synthetic_events_to_detector_to_insight_to_ui_html,
]

if __name__ == "__main__":
    for fn in ALL_INSIGHT_TESTS:
        fn()
        print(f"✅ PASS: {fn.__name__}")
    print(f"\n🎯 All {len(ALL_INSIGHT_TESTS)}/{len(ALL_INSIGHT_TESTS)} Tactical Impact Explorer & Player Spotlight tests passed!")
