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
    build_multiaudience_views,
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
    assert "minutes 48 to 54" in s1
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



def test_19_french_mode_does_not_contaminate_english_multiaudience():
    from pipeline import build_factual_core, build_multiaudience_views
    fact_fr = build_factual_core(SAMPLE_ALARM_ENTERED, "French")
    multi = build_multiaudience_views(SAMPLE_ALARM_ENTERED, analyst_color_en="", fan_en="")
    multi["fr"]["analyst_view"] = f"{fact_fr} Le bloc resserre les lignes."
    assert "At minute 57" in multi["en"]["analyst_view"]
    assert "À la 57e minute" in multi["fr"]["analyst_view"]
    assert "Le bloc resserre" not in multi["en"]["analyst_view"]



def test_20_reject_french_role_inversion():
    p_ent = ColorCommentaryPayload(
        analyst_color="Le bloc est très haut.",
        fan_view="Nova FC étouffe complètement Meteor City !",
        cited_event_ids=["EVT-m_42-1154"]
    )
    err1 = verify_color_commentary(p_ent, SAMPLE_ALARM_ENTERED, VALID_IDS_ENTERED)
    assert any("Role inversion" in e for e in err1)

    p_ext = ColorCommentaryPayload(
        analyst_color="Bonne relance.",
        fan_view="Meteor City casse le pressing avec brio !",
        cited_event_ids=["EVT-m_42-1265"]
    )
    err2 = verify_color_commentary(p_ext, SAMPLE_ALARM_EXITED_RECOVERED, VALID_IDS_EXITED)
    assert any("Role inversion" in e for e in err2)


def test_21_unit_test_detector_custom_teams_state_machine():
    from detector import OnlineShiftDetector
    d = OnlineShiftDetector(teams=("Arsenal", "Liverpool"), min_passes=3, min_press=3, entry_acc=0.60)
    # Minute 1: Liverpool (away, defends x > 67) is pressed by Arsenal
    events = [
        {"event_id": "E1", "minute": 1, "team": "Liverpool", "event_type": "Pass", "start_x": 80.0, "outcome": "Failure"},
        {"event_id": "E2", "minute": 1, "team": "Liverpool", "event_type": "Pass", "start_x": 75.0, "outcome": "Failure"},
        {"event_id": "E3", "minute": 1, "team": "Liverpool", "event_type": "Pass", "start_x": 70.0, "outcome": "Success"},
        {"event_id": "E4", "minute": 1, "team": "Arsenal", "event_type": "Pressure", "x": 78.0},
        {"event_id": "E5", "minute": 1, "team": "Arsenal", "event_type": "Tackle", "x": 75.0},
        {"event_id": "E6", "minute": 1, "team": "Arsenal", "event_type": "Interception", "x": 72.0},
        # Minute 2 triggers evaluation of completed minute 1
        {"event_id": "E7", "minute": 2, "team": "Arsenal", "event_type": "Pass", "start_x": 50.0, "outcome": "Success"},
    ]
    alarms = [a for e in events if (a := d.process_event(e))]
    assert len(alarms) == 1
    assert alarms[0]["status"] == "ENTERED"
    assert alarms[0]["team"] == "Arsenal"
    assert alarms[0]["victim"] == "Liverpool"


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
        test_19_french_mode_does_not_contaminate_english_multiaudience,
        test_20_reject_french_role_inversion,
        test_21_unit_test_detector_custom_teams_state_machine,
    ]
    for t in all_tests:
        t()
        print(f"✅ PASS: {t.__name__}")
    print(f"\n🎯 All {len(all_tests)}/{len(all_tests)} Verifier v5.2 + Worker-to-UI + Recap tests passed flawlessly!")
    
    
def test_22_reject_exited_pressing_intensity_words():
    """Vérifie l'interdiction stricte du vocabulaire d'agression/intensité lors d'une sortie de pressing (EXITED)."""
    alarm_exited = {
        "minute": 62,
        "team": "Meteor City",
        "victim": "Nova FC",
        "status": "EXITED",
        "exit_reason": "exhausted",
        "stats": {"def_actions": 1, "pass_acc": 0.57}
    }
    valid_ids = {"EVT-m_42-1276"}

    # Cas observé dans la vidéo originale : l'IA générait "Relentless pressure across the pitch!"
    payload_bad = ColorCommentaryPayload(
        analyst_color_en="The pressing block drops off into mid-recovery.",
        fan_view_en="Relentless pressure across the pitch!",
        analyst_color_fr="Le rideau défensif recule.",
        fan_view_fr="Le danger s'éloigne.",
        cited_event_ids=["EVT-m_42-1276"]
    )
    errors = verify_color_commentary(payload_bad, alarm_exited, valid_ids)
    assert any("Tactical polarity error" in err for err in errors), f"Devrait rejeter 'relentless' en état EXITED : {errors}"


def test_23_accept_valid_exited_both_languages():
    """Valide qu'un commentaire de sortie cohérent (temporisation, décompression) passe le vérificateur sans erreur."""
    alarm_exited = {
        "minute": 62,
        "team": "Meteor City",
        "victim": "Nova FC",
        "status": "EXITED",
        "exit_reason": "exhausted",
        "stats": {"def_actions": 1, "pass_acc": 0.57}
    }
    valid_ids = {"EVT-m_42-1276"}

    payload_good = ColorCommentaryPayload(
        analyst_color_en="The pressing block drops off into mid-recovery, allowing structured distribution from the back.",
        fan_view_en="Pressure subsides as the defense regains its composure!",
        analyst_color_fr="Le rideau défensif recule et permet de réorganiser sereinement la relance courte.",
        fan_view_fr="Le danger s'éloigne, la relance retrouve enfin son calme !",
        cited_event_ids=["EVT-m_42-1276"]
    )
    errors = verify_color_commentary(payload_good, alarm_exited, valid_ids)
    assert errors == [], f"Un commentaire de sortie cohérent ne doit générer aucune erreur : {errors}"


def test_24_multiaudience_views_coverage():
    """Valide que build_multiaudience_views injecte réellement les commentaires personnalisés EN et FR."""
    alarm_entered = {
        "minute": 57,
        "team": "Meteor City",
        "victim": "Nova FC",
        "status": "ENTERED",
        "stats": {"def_actions": 3, "pass_acc": 0.50}
    }
    views = build_multiaudience_views(
        alarm_entered,
        analyst_color_en="Custom EN tactical analysis.",
        fan_en="Custom EN fan reaction!",
        analyst_color_fr="Analyse tactique FR sur mesure.",
        fan_fr="Réaction fan FR sur mesure !"
    )

    assert "Custom EN tactical analysis." in views["en"]["analyst_view"]
    assert views["en"]["fan_view"] == "Custom EN fan reaction!"
    assert "Analyse tactique FR sur mesure." in views["fr"]["analyst_view"]
    assert views["fr"]["fan_view"] == "Réaction fan FR sur mesure !"
    assert "Meteor City" in views["club_voices"]
    assert "Nova FC" in views["club_voices"]
