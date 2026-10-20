import json
import os
from pipeline import ColorCommentaryPayload, verify_color_commentary, build_factual_core

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

def test_05_reject_number_words():
    p = ColorCommentaryPayload(analyst_color="Winning fourteen tackles in midfield.", fan_view="Hype!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Number words are forbidden" in e for e in err)

def test_06_reject_hallucinated_red_card():
    p = ColorCommentaryPayload(analyst_color="Following the red card the defense collapsed.", fan_view="Unfair!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Hallucinated" in e for e in err)

def test_07_reject_hallucinated_injury():
    p = ColorCommentaryPayload(analyst_color="With the injured keeper out of position.", fan_view="Oh no!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Hallucinated" in e for e in err)

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
    p = ColorCommentaryPayload(analyst_color="The collective block squeezes passing lanes effectively.", fan_view="Meteor City is suffocating the opponent! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []

def test_13_accept_valid_exited_english():
    p = ColorCommentaryPayload(analyst_color="Composed movement across the backline restores territorial balance.", fan_view="Nova FC regains composure on the ball! ⚡", cited_event_ids=["EVT-m_42-1265"])
    assert verify_color_commentary(p, SAMPLE_ALARM_EXITED_EXHAUSTED, VALID_IDS_EXITED) == []

def test_14_accept_valid_entered_french():
    p = ColorCommentaryPayload(analyst_color="Le bloc haut étouffe complètement les relances courtes.", fan_view="Quelle intensité dans les duels ! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []


def test_17_end_to_end_draft_to_final_ui_upgrade(tmp_path=None):
    import tempfile
    import app
    with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
        temp_ui = tf.name
        draft = {"episode_id": "m_42_min57_ENTERED", "episode_seq": 1, "render_status": "DRAFT (Live)", "analyst_view": "Draft"}
        final = {"episode_id": "m_42_min57_ENTERED", "episode_seq": 1, "render_status": "FINAL (AI Verified)", "analyst_view": "Verified"}
        tf.write(json.dumps(draft) + "\n")
        tf.write(json.dumps(final) + "\n")
    old_ui = app.UI_FILE
    try:
        app.UI_FILE = temp_ui
        episodes = app.load_episodes()
        assert len(episodes) == 1
        assert episodes[0]["episode_id"] == "m_42_min57_ENTERED"
        assert episodes[0]["render_status"] == "FINAL (AI Verified)"
    finally:
        app.UI_FILE = old_ui
        if os.path.exists(temp_ui):
            os.remove(temp_ui)

if __name__ == "__main__":
    test_17_end_to_end_draft_to_final_ui_upgrade()
    print("✅ PASS: test_17_end_to_end_draft_to_final_ui_upgrade")
    tests = [
        test_01_reject_invented_id,
        test_02_reject_placeholder_id,
        test_03_reject_digits_in_color,
        test_04_reject_ordinal_minute_in_color,
        test_05_reject_number_words,
        test_06_reject_hallucinated_red_card,
        test_07_reject_hallucinated_injury,
        test_08_reject_unverified_micro_action_winger_run,
        test_09_reject_role_inversion_hounds,
        test_10_reject_role_inversion_exited,
        test_11_factual_core_exhausted_vs_recovered_and_singular,
        test_12_accept_valid_entered_english,
        test_13_accept_valid_exited_english,
        test_14_accept_valid_entered_french,
    ]
    for t in tests:
        t()
        print(f"✅ PASS: {t.__name__}")
    print(f"\n🎯 {len(tests)}/{len(tests)} Verifier v5.1 stress tests passed flawlessly.")

from datetime import datetime
from pipeline import format_match_timestamp, generate_fallback_overlay, build_recap_factual_core


def test_15_valid_iso_timestamp_above_minute_59():
    ts = format_match_timestamp(62)
    assert ts == "2026-10-27T16:02:00Z"
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed.hour == 16 and parsed.minute == 2
    fb = generate_fallback_overlay(SAMPLE_ALARM_EXITED_EXHAUSTED, "m_42_min62_EXITED")
    datetime.fromisoformat(fb["timestamp"].replace("Z", "+00:00"))


def test_16_dynamic_recap_nova_win_and_draw_and_no_press():
    # Nova FC wins, custom minutes 48 and 54
    eps = [
        {"episode_id": "m_1_min48_ENTERED", "match_minute": 48},
        {"episode_id": "m_1_min54_EXITED", "match_minute": 54},
    ]
    h1, s1, _ = build_recap_factual_core(eps, {"Meteor City": 1, "Nova FC": 3}, language="English")
    assert "Nova FC claims a 3-1 victory" in s1
    assert "minutes 48 and 54" in s1
    assert "57" not in s1

    # Draw with no pressing episodes
    h2, s2, _ = build_recap_factual_core([], {"Meteor City": 1, "Nova FC": 1}, language="English")
    assert "1-1 draw" in s2
    assert "No sustained high-press" in s2



def test_17_end_to_end_draft_to_final_ui_upgrade(tmp_path=None):
    import tempfile
    import app
    with tempfile.NamedTemporaryFile("w+", suffix=".jsonl", delete=False, encoding="utf-8") as tf:
        temp_ui = tf.name
        draft = {"episode_id": "m_42_min57_ENTERED", "episode_seq": 1, "render_status": "DRAFT (Live)", "analyst_view": "Draft"}
        final = {"episode_id": "m_42_min57_ENTERED", "episode_seq": 1, "render_status": "FINAL (AI Verified)", "analyst_view": "Verified"}
        tf.write(json.dumps(draft) + "\n")
        tf.write(json.dumps(final) + "\n")
    old_ui = app.UI_FILE
    try:
        app.UI_FILE = temp_ui
        episodes = app.load_episodes()
        assert len(episodes) == 1
        assert episodes[0]["episode_id"] == "m_42_min57_ENTERED"
        assert episodes[0]["render_status"] == "FINAL (AI Verified)"
    finally:
        app.UI_FILE = old_ui
        if os.path.exists(temp_ui):
            os.remove(temp_ui)

if __name__ == "__main__":
    test_17_end_to_end_draft_to_final_ui_upgrade()
    print("✅ PASS: test_17_end_to_end_draft_to_final_ui_upgrade")
    test_15_valid_iso_timestamp_above_minute_59()
    print("✅ PASS: test_15_valid_iso_timestamp_above_minute_59")
    test_16_dynamic_recap_nova_win_and_draw_and_no_press()
    print("✅ PASS: test_16_dynamic_recap_nova_win_and_draw_and_no_press")
    print("\n🎯 All 17/17 Verifier v5.1 + ISO Timestamp + Dynamic Recap tests passed!")
