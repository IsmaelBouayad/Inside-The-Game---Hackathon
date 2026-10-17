from pipeline import ColorCommentaryPayload, verify_color_commentary

SAMPLE_ALARM_ENTERED = {
    "minute": 57, "type": "High Press", "status": "ENTERED",
    "team": "Meteor City", "victim": "Nova FC",
    "trigger_event_ids": ["EVT-m_42-1154", "EVT-m_42-1156"],
    "stats": {"pass_acc": 0.50, "def_actions": 8, "n_passes": 8}
}

SAMPLE_ALARM_EXITED = {
    "minute": 62, "type": "High Press", "status": "EXITED",
    "team": "Meteor City", "victim": "Nova FC",
    "trigger_event_ids": ["EVT-m_42-1265", "EVT-m_42-1266"],
    "stats": {"pass_acc": 0.90, "def_actions": 1, "n_passes": 10}
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

def test_04_reject_minute_in_color():
    p = ColorCommentaryPayload(analyst_color="At the 12th minute they press.", fan_view="Hype!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Digits are strictly forbidden" in e for e in err)

def test_05_reject_number_words():
    p = ColorCommentaryPayload(analyst_color="Winning fourteen tackles in midfield.", fan_view="Hype!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Number words are forbidden" in e for e in err)

def test_06_reject_hallucinated_red_card():
    p = ColorCommentaryPayload(analyst_color="Following the red card the defense collapsed.", fan_view="Unfair card!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Hallucinated match incident" in e for e in err)

def test_07_reject_hallucinated_injury():
    p = ColorCommentaryPayload(analyst_color="With the injured keeper out of position.", fan_view="Oh no!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Hallucinated match incident" in e for e in err)

def test_08_reject_role_inversion_hounds():
    p = ColorCommentaryPayload(analyst_color="Aggressive defensive line.", fan_view="Nova FC hounds Meteor City relentlessly!", cited_event_ids=["EVT-m_42-1154"])
    err = verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Role inversion" in e for e in err)

def test_09_reject_role_inversion_exited():
    p = ColorCommentaryPayload(analyst_color="Lines are stepping up.", fan_view="Meteor City escapes the press brilliantly!", cited_event_ids=["EVT-m_42-1265"])
    err = verify_color_commentary(p, SAMPLE_ALARM_EXITED, VALID_IDS_EXITED)
    assert any("Role inversion" in e for e in err)

def test_10_accept_valid_entered_english():
    p = ColorCommentaryPayload(analyst_color="The defensive shape squeezes passing lanes effectively.", fan_view="Meteor City is suffocating the opponent! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []

def test_11_accept_valid_exited_english():
    p = ColorCommentaryPayload(analyst_color="Composed movement from the backline breaks the initial wave.", fan_view="Nova FC breaks free with style! 🏃‍♂️💨", cited_event_ids=["EVT-m_42-1265"])
    assert verify_color_commentary(p, SAMPLE_ALARM_EXITED, VALID_IDS_EXITED) == []

def test_12_accept_valid_entered_french():
    p = ColorCommentaryPayload(analyst_color="Le bloc haut étouffe complètement les relances courtes.", fan_view="Quelle intensité dans les duels ! 🔥", cited_event_ids=["EVT-m_42-1154"])
    assert verify_color_commentary(p, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED) == []

if __name__ == "__main__":
    tests = [
        test_01_reject_invented_id,
        test_02_reject_placeholder_id,
        test_03_reject_digits_in_color,
        test_04_reject_minute_in_color,
        test_05_reject_number_words,
        test_06_reject_hallucinated_red_card,
        test_07_reject_hallucinated_injury,
        test_08_reject_role_inversion_hounds,
        test_09_reject_role_inversion_exited,
        test_10_accept_valid_entered_english,
        test_11_accept_valid_exited_english,
        test_12_accept_valid_french := test_12_accept_valid_entered_french,
    ]
    for t in tests:
        t()
        print(f"✅ PASS: {t.__name__}")
    print("\n🎯 12/12 Verifier v5 stress tests passed flawlessly.")
