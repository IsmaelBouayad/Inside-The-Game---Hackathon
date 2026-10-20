import asyncio
import json
import os
import tempfile
from datetime import datetime
from pipeline import (
    ColorCommentaryPayload,
    MatchRecapPayload,
    verify_color_commentary,
    verify_recap_output,
    build_factual_core,
    build_recap_factual_core,
    format_match_timestamp,
    generate_fallback_overlay,
)

SAMPLE_ALARM_ENTERED = {
    "minute": 57, "type": "High Press", "status": "ENTERED",
    "team": "Meteor City", "victim": "Nova FC",
    "trigger_event_ids": ["EVT-m_42-1154", "EVT-m_42-1156"],
    "stats": {"pass_acc": 0.50, "def_actions": 8, "n_passes": 8}
}

SAMPLE_ALARM_EXITED_EXHAUSTED = {
    "minute": 62, "type": "High Press", "status": "EXITED", "exit_reason": "exhausted",
    "team": "Meteor City", "victim": "Nova FC",
    "trigger_event_ids": ["EVT-m_42-1265", "EVT-m_42-1266"],
    "stats": {"pass_acc": 0.57, "def_actions": 1, "n_passes": 14}
}

SAMPLE_ALARM_EXITED_RECOVERED = {
    "minute": 62, "type": "High Press", "status": "EXITED", "exit_reason": "recovered",
    "team": "Meteor City", "victim": "Nova FC",
    "trigger_event_ids": ["EVT-m_42-1265", "EVT-m_42-1266"],
    "stats": {"pass_acc": 0.90, "def_actions": 2, "n_passes": 10}
}

VALID_IDS_ENTERED = {"EVT-m_42-1154", "EVT-m_42-1156"}
VALID_IDS_EXITED = {"EVT-m_42-1265", "EVT-m_42-1266"}


def test_01_reject_invented_id():
    p = ColorCommentaryPayload(analyst_color="High block maintained.", fan_view="Hype!", cited_event_ids=["EVT-m_42-9999"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) != []


def test_02_reject_placeholder_id():
    p = ColorCommentaryPayload(analyst_color="High block maintained.", fan_view="Hype!", cited_event_ids=["EVT-XXXX"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) != []


def test_03_reject_digits_in_color():
    p = ColorCommentaryPayload(analyst_color="Forcing 14 misplaced passes.", fan_view="Pressure!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Digits are strictly forbidden" in e for e in err)


def test_04_reject_ordinal_minute_in_color():
    p = ColorCommentaryPayload(analyst_color="At the 12th minute they press.", fan_view="Hype!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Digits are strictly forbidden" in e for e in err)


def test_05_reject_extended_number_words():
    for word in ("fourteen", "sixteen", "thirty", "forty", "dozen", "twice", "trente"):
        p = ColorCommentaryPayload(analyst_color=f"Winning {word} duels in midfield.", fan_view="Hype!", cited_event_ids=["EVT-m_42-1154"])
        err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
        assert any("Number words are forbidden" in e for e in err), f"Failed on {word}"


def test_06_reject_hallucinated_incidents_and_var():
    for inc in ("red card", "injured keeper", "substitution", "VAR", "flurry of attacks"):
        p = ColorCommentaryPayload(analyst_color=f"Following the {inc} the rhythm changed.", fan_view="Wild!", cited_event_ids=["EVT-m_42-1154"])
        err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
        assert any("Hallucinated" in e for e in err), f"Failed on {inc}"


def test_07_reject_ellipsis_truncation_and_team_names_in_analyst_color():
    p = ColorCommentaryPayload(
        analyst_color="The Meteor City defense is scrambling... creating opportunities for Nova FC.",
        fan_view="METEOR CITY IS ALL OVER THE PLACE...",
        cited_event_ids=["EVT-m_42-1154"]
    )
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Ellipsis" in e for e in err)
    assert any("Do not repeat team names" in e for e in err)
    assert any("Role inversion" in e for e in err)


def test_08_reject_unverified_micro_action_winger_run():
    p = ColorCommentaryPayload(analyst_color="A clever run from the left winger exploits the right-back.", fan_view="Great run!", cited_event_ids=["EVT-m_42-1265"])
    err = verify_color_commentary(p, SAMPLE_ALARM_EXITED_EXHAUSTED, VALID_IDS_EXITED)
    assert any("micro-action" in e for e in err)


def test_09_reject_role_inversion_hounds():
    p = ColorCommentaryPayload(analyst_color="Aggressive defensive line.", fan_view="Nova FC hounds Meteor City relentlessly!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Role inversion" in e for e in err)


def test_10_reject_role_inversion_exited():
    p = ColorCommentaryPayload(analyst_color="Lines are stepping up.", fan_view="Meteor City escapes the press brilliantly!", cited_event_ids=["EVT-m_42-1265"])
    err = verify_color_commentary(p, SAMPLE_ALARM_EXITED_RECOVERED, VALID_IDS_EXITED)
    assert any("Role inversion" in e for e in err)


def test_11_factual_core_exhausted_vs_recovered_and_singular():
    text_exhausted = build_factual_core(SAMPLE_ALARM_EXITED_EXHAUSTED, "English")
    assert "subsides" in text_exhausted
    assert "1 recent defensive action," in text_exhausted
    assert "breaks the press" not in text_exhausted

    text_recovered = build_factual_core(SAMPLE_ALARM_EXITED_RECOVERED, "English")
    assert "cleanly breaks the press" in text_recovered
    assert "2 recent defensive actions" in text_recovered


def test_12_accept_valid_entered_english():
    p = ColorCommentaryPayload(analyst_color="The collective block squeezes passing lanes effectively.", fan_view="Meteor City is suffocating the buildup! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []


def test_13_accept_valid_exited_english():
    p = ColorCommentaryPayload(analyst_color="Composed movement across the backline restores territorial balance.", fan_view="Nova FC regains composure on the ball! ⚡", cited_event_ids=["EVT-m_42-1265"])
    assert verify_color_commentary(p, SAMPLE_ALARM_EXITED_EXHAUSTED, VALID_IDS_EXITED) == []


def test_14_accept_valid_entered_french():
    p = ColorCommentaryPayload(analyst_color="Le bloc haut étouffe complètement les relances courtes.", fan_view="Quelle intensité dans les duels ! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []


def test_15_valid_iso_timestamp_above_minute_59():
    ts = format_match_timestamp(62)
    assert ts == "2026-10-27T16:02:00Z"
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.hour == 16 and parsed.minute == 2
    fb = generate_fallback_overlay(SAMPLE_ALARM_EXITED_EXHAUSTED, "m_42_min62_EXITED")
    datetime.fromisoformat(fb["timestamp"].replace("Z", "+00:00"))


def test_16_dynamic_recap_nova_win_and_draw_and_no_press():
    eps = [
        {"episode_id": "m_1_min48_ENTERED", "match_minute": 48},
        {"episode_id": "m_1_min54_EXITED", "match_minute": 54},
    ]
    _, s1, _ = build_recap_factual_core(eps, {"Meteor City": 1, "Nova FC": 3}, language="English")
    assert "Nova FC claims a 3-1 victory" in s1
    assert "minutes 48 and 54" in s1
    assert "57" not in s1

    _, s2, _ = build_recap_factual_core([], {"Meteor City": 1, "Nova FC": 1}, language="English")
    assert "1-1 draw" in s2
    assert "No sustained high-press" in s2


def test_17_recap_verifier_validates_all_episode_ids():
    valid_set = {"m_42_min57_ENTERED", "m_42_min62_EXITED"}
    bad_recap = MatchRecapPayload(
        tactical_color="Collective spatial discipline dictated the tempo.",
        key_episode_ids=["m_42_min57_ENTERED", "INVENTED_EPISODE_99"]
    )
    errs = verify_recap_output(bad_recap, valid_set)
    assert any("INVENTED_EPISODE_99" in e for e in errs)

    good_recap = MatchRecapPayload(
        tactical_color="Collective spatial discipline dictated the tempo.",
        key_episode_ids=["m_42_min57_ENTERED", "m_42_min62_EXITED"]
    )
    assert verify_recap_output(good_recap, valid_set) == []


def test_18_end_to_end_worker_to_ui_persistence():
    import app
    import engine

    async def _run_worker_test():
        with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
            temp_ui = tf.name
        old_app_ui, old_eng_ui = app.UI_FILE, engine.UI_FILE
        try:
            app.UI_FILE = engine.UI_FILE = temp_ui
            # 1. Engine writes instant DRAFT at alarm time
            draft = engine.template_overlay(SAMPLE_ALARM_ENTERED, "m_42_min57_ENTERED", 1, "DRAFT (Live)")
            engine.append_to_ui(draft)
            assert app.load_episodes()[0]["render_status"] == "DRAFT (Live)"

            # 2. Worker runs mock verified LLM and persists FINAL
            async def mock_llm(match_id, alarm, raw_events, force_live=True, language="English", persona="General Fan"):
                out = dict(draft)
                out["is_fallback"] = False
                out["analyst_view"] = "Verified analyst view."
                return out

            q = asyncio.Queue()
            metrics = engine.Metrics()
            fabric = engine.FabricTelemetrySink()
            fabric.live_enabled = False
            state_tracker = {"latest_seq": 1, "current_minute": 57, "worker_busy": False}
            verified_list = []

            worker_task = asyncio.create_task(
                engine.llm_worker(q, "m_42", mock_llm, metrics, 5.0, fabric, state_tracker, verified_list)
            )
            await q.put((1, SAMPLE_ALARM_ENTERED, []))
            await q.join()
            worker_task.cancel()

            episodes = app.load_episodes()
            assert len(episodes) == 1
            assert episodes[0]["episode_id"] == "m_42_min57_ENTERED"
            assert episodes[0]["render_status"] == "FINAL (AI Verified)"
            assert metrics.llm_ok == 1
        finally:
            app.UI_FILE, engine.UI_FILE = old_app_ui, old_eng_ui
            if os.path.exists(temp_ui):
                os.remove(temp_ui)

    asyncio.run(_run_worker_test())


if __name__ == "__main__":
    all_tests = [
        test_01_reject_invented_id,
        test_02_reject_placeholder_id,
        test_03_reject_digits_in_color,
        test_04_reject_ordinal_minute_in_color,
        test_05_reject_extended_number_words,
        test_06_reject_hallucinated_incidents_and_var,
        test_07_reject_ellipsis_truncation_and_team_names_in_analyst_color,
        test_08_reject_unverified_micro_action_winger_run,
        test_09_reject_role_inversion_hounds,
        test_10_reject_role_inversion_exited,
        test_11_factual_core_exhausted_vs_recovered_and_singular,
        test_12_accept_valid_entered_english,
        test_13_accept_valid_exited_english,
        test_14_accept_valid_entered_french,
        test_15_valid_iso_timestamp_above_minute_59,
        test_16_dynamic_recap_nova_win_and_draw_and_no_press,
        test_17_recap_verifier_validates_all_episode_ids,
        test_18_end_to_end_worker_to_ui_persistence,
    ]
    for t in all_tests:
        t()
        print(f"✅ PASS: {t.__name__}")
    print(f"\n🎯 All {len(all_tests)}/{len(all_tests)} Verifier v5.2 + Worker-to-UI + Recap tests passed flawlessly!")
