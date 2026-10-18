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

if __name__ == "__main__":
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
