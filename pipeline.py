import os
import json
import asyncio
import re
import time
from datetime import datetime, timedelta
from openai import AsyncOpenAI
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient
from pydantic import BaseModel, Field
from typing import List

CACHE_FILE = "demo_cache.json"
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
MATCH_KICKOFF = datetime(2026, 10, 27, 15, 0, 0)


class ColorCommentaryPayload(BaseModel):
    analyst_color: str
    fan_view: str
    cited_event_ids: List[str] = Field(min_length=1)


class MatchRecapPayload(BaseModel):
    tactical_color: str
    key_episode_ids: List[str] = Field(min_length=1)


def format_match_timestamp(minute: int) -> str:
    """Produces a strictly valid ISO-8601 timestamp (e.g. minute 62 -> 2026-10-27T16:02:00Z)."""
    dt = MATCH_KICKOFF + timedelta(minutes=int(minute))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache_data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)


def get_clients(model_name: str = None):
    model = model_name or DEFAULT_MODEL
    native_client = AsyncOpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
    return OpenAIChatCompletionClient(model=model, async_client=native_client)


async def warmup_ollama(model_name: str = None):
    model = model_name or DEFAULT_MODEL
    try:
        t0 = time.monotonic()
        native_client = AsyncOpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
        await native_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=2
        )
        print(f"🔥 [Warmup] Model '{model}' ready in RAM ({round(time.monotonic() - t0, 2)}s)")
    except Exception as e:
        print(f"⚠️ [Warmup] Note: '{model}' will initialize on first request ({e})")


def extract_json(text: str) -> str:
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end+1]
    return text


def build_factual_core(alarm: dict, language: str = "English") -> str:
    """
    100% Python-generated mathematical ground truth with explicit distinction
    between 'recovered' (victim pass acc >75%) and 'exhausted' (pressing actions <=1),
    and strict singular/plural grammar.
    """
    minute = alarm["minute"]
    team = alarm["team"]
    victim = alarm["victim"]
    status = alarm.get("status", "ENTERED")
    exit_reason = alarm.get("exit_reason")
    stats = alarm.get("stats", {})
    def_actions = stats.get("def_actions", 0)
    pass_acc = stats.get("pass_acc")
    acc_pct = int(round(pass_acc * 100)) if pass_acc is not None else None

    if status == "EXITED" and not exit_reason:
        exit_reason = "recovered" if (acc_pct is not None and acc_pct > 75) else "exhausted"

    if language.lower() in ("french", "français"):
        act_word = "action défensive" if def_actions == 1 else "actions défensives"
        if status == "ENTERED":
            acc_str = f", réduisant la précision de relance adverse à {acc_pct}%" if acc_pct is not None else ""
            return (
                f"À la {minute}e minute, {team} enclenche un pressing haut avec {def_actions} {act_word} "
                f"dans le tiers défensif de {victim}{acc_str}."
            )
        else:
            if exit_reason == "recovered":
                acc_str = f" grâce à {acc_pct}% de passes réussies" if acc_pct is not None else ""
                return (
                    f"À la {minute}e minute, {victim} parvient à casser le pressing de {team}{acc_str} "
                    f"({def_actions} {act_word} sur la fenêtre récente)."
                )
            else:
                acc_str = f" (précision de passes de {acc_pct}% sur la période)" if acc_pct is not None else ""
                return (
                    f"À la {minute}e minute, le pressing haut de {team} retombe avec seulement {def_actions} {act_word} "
                    f"récente, permettant à {victim} de se réorganiser{acc_str}."
                )
    else:
        act_word = "defensive action" if def_actions == 1 else "defensive actions"
        if status == "ENTERED":
            acc_str = f", reducing build-up accuracy to {acc_pct}%" if acc_pct is not None else ""
            return (
                f"At minute {minute}, {team} initiates a high press with {def_actions} {act_word} "
                f"against {victim}{acc_str}."
            )
        else:
            if exit_reason == "recovered":
                acc_str = f" with {acc_pct}% pass accuracy" if acc_pct is not None else ""
                return (
                    f"At minute {minute}, {victim} cleanly breaks the press of {team}{acc_str} "
                    f"following {def_actions} recent {act_word}."
                )
            else:
                acc_str = f" ({acc_pct}% pass accuracy over the window)" if acc_pct is not None else ""
                return (
                    f"At minute {minute}, {team}'s high press subsides with only {def_actions} recent {act_word}, "
                    f"allowing {victim} to stabilize possession{acc_str}."
                )


def verify_color_commentary(payload: ColorCommentaryPayload, alarm: dict, valid_event_ids: set) -> list:
    """
    Verifier v5.1:
    1. Real cited event IDs from the episode window required (rejects 'EVT-XXXX').
    2. Strictly forbids digits and number words in LLM color text.
    3. Forbids unrecorded match incidents (cards, injuries, penalties) and untracked player micro-actions.
    4. Prevents role inversion between pressing team and victim.
    """
    errors = []

    if not payload.cited_event_ids:
        errors.append("No event IDs cited.")
    else:
        invalid = [eid for eid in payload.cited_event_ids if eid not in valid_event_ids or "XXXX" in eid]
        if invalid:
            errors.append(f"Invalid cited IDs: {invalid}. Allowed: {sorted(list(valid_event_ids))}")

    combined = f"{payload.analyst_color} {payload.fan_view}".strip()
    combined_lower = combined.lower()

    text_no_ids = re.sub(r"EVT-[A-Za-z0-9_-]+", "", combined)
    if re.search(r"\d", text_no_ids):
        found = re.findall(r"\d+", text_no_ids)
        errors.append(f"Digits are strictly forbidden in LLM color text: {found}. Python supplies all metrics.")

    number_words = r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|fifty|ninety|dix|douze|quatorze)\b"
    if re.search(number_words, combined_lower):
        errors.append("Number words are forbidden in LLM color text. Python supplies all metrics.")

    hallucination_triggers = [
        r"red card", r"yellow card", r"carton rouge", r"carton jaune",
        r"penalty", r"pénalty", r"injury", r"injured", r"blessé", r"blessure",
        r"sent off", r"expulsé", r"handball", r"offside", r"hors-jeu",
        r"corner", r"free kick", r"coup franc", r"\bheader\b",
        r"\bwinger\b", r"\bailier\b", r"right-back", r"right back", r"left-back", r"left back",
        r"full-back", r"fullback", r"clever run", r"through ball", r"\bcross\b"
    ]
    for h in hallucination_triggers:
        pattern = h if h.startswith(r"\b") else rf"\b{re.escape(h)}\b"
        if re.search(pattern, combined_lower):
            errors.append(f"Hallucinated match incident or unverified micro-action detected: '{h}'.")

    victim = alarm["victim"].lower()
    team = alarm["team"].lower()
    status = alarm.get("status", "ENTERED")
    if status == "ENTERED":
        if re.search(rf"\b{re.escape(victim)}\b\s+(?:presses|pressing|suffocates|hounds|destroys|dominates)", combined_lower):
            errors.append(f"Role inversion: {alarm['victim']} cannot be described as the aggressor during ENTERED state.")
    elif status == "EXITED":
        if re.search(rf"\b{re.escape(team)}\b\s+(?:escapes|breaks\s+the\s+press|breaks\s+free)", combined_lower):
            errors.append(f"Role inversion: {alarm['team']} cannot be described as escaping the press during EXITED state.")

    return errors


def build_multiaudience_views(alarm: dict, analyst_color_en: str = "", fan_en: str = "") -> dict:
    fact_en = build_factual_core(alarm, "English")
    fact_fr = build_factual_core(alarm, "French")
    status = alarm.get("status", "ENTERED")
    exit_reason = alarm.get("exit_reason") or ("recovered" if (alarm.get("stats", {}).get("pass_acc") or 0) > 0.75 else "exhausted")
    team = alarm["team"]
    victim = alarm["victim"]

    if status == "ENTERED":
        default_color_en = "The collective block compresses space and disrupts passing options."
        color_fr = "Le bloc collectif resserre les lignes et verrouille la relance courte."
        fan_fr = f"Quel pressing étouffant de {team} ! La défense de {victim} panique ! 🔥"
        club_meteor = f"💙 Meteor City imposes total territorial control!" if team == "Meteor City" else f"⚠️ Meteor City must stay calm under {team}'s press!"
        club_nova = f"💛 Nova FC hunting in packs high up the pitch!" if team == "Nova FC" else f"⚠️ Nova FC under heavy pressure in their own third!"
    else:
        if exit_reason == "recovered":
            default_color_en = "Composed ball circulation neutralizes the high block."
            color_fr = "Une circulation de balle maîtrisée permet de franchir le premier rideau."
            fan_fr = f"Superbe sortie de balle de {victim} sous pression ! 🏃‍♂️💨"
        else:
            default_color_en = "The pressing intensity drops off, restoring normal build-up phases."
            color_fr = "L'intensité du pressing adverse baisse, permettant de temporiser."
            fan_fr = f"Le pressing de {team} s'essouffle, {victim} reprend le contrôle du ballon ! ⚖️"
        club_meteor = "💙 Meteor City breathes again and resets the tempo!"
        club_nova = "💛 Nova FC stabilizes possession and looks forward!"

    use_color_en = analyst_color_en if analyst_color_en else default_color_en
    use_fan_en = fan_en if fan_en else (f"{team} turns up the heat! 🔥" if status == "ENTERED" else f"{victim} regains control of the tempo! ⚡")

    return {
        "en": {
            "analyst_view": f"{fact_en} {use_color_en}".strip(),
            "fan_view": use_fan_en
        },
        "fr": {
            "analyst_view": f"{fact_fr} {color_fr}".strip(),
            "fan_view": fan_fr
        },
        "club_voices": {
            "Meteor City": club_meteor,
            "Nova FC": club_nova
        }
    }


def generate_fallback_overlay(alarm: dict, episode_key: str, language: str = "English", persona: str = "General Fan") -> dict:
    multi = build_multiaudience_views(alarm)
    lang_key = "fr" if language.lower() in ("french", "français") else "en"
    trigger_ids = alarm.get("trigger_event_ids", [])

    return {
        "analyst_view": multi[lang_key]["analyst_view"],
        "fan_view": multi[lang_key]["fan_view"],
        "multiaudience": multi,
        "cited_event_ids": trigger_ids[:2],
        "language_used": language,
        "target_persona": persona,
        "exit_reason": alarm.get("exit_reason"),
        "timestamp": alarm.get("timestamp") or format_match_timestamp(alarm["minute"]),
        "match_minute": alarm["minute"],
        "episode_id": episode_key,
        "stats_snapshot": alarm.get("stats", {}),
        "is_fallback": True
    }


def generate_goal_overlay(event: dict, score: dict, match_id: str, language: str = "English") -> dict:
    minute = event["minute"]
    scorer_team = event["team"]
    player = event.get("player_id", "Player")
    episode_key = f"{match_id}_min{minute}_GOAL_{event['event_id']}"

    en_analyst = f"GOAL at minute {minute}! {player} ({scorer_team}) scores. Score is now Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
    en_fan = f"GOOOAAAL! Clinical finish by {player} for {scorer_team}! ⚽🔥"
    fr_analyst = f"BUT à la {minute}e minute ! {player} ({scorer_team}) marque. Score : Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
    fr_fan = f"BUUUT ! Finition décisive de {player} pour {scorer_team} ! ⚽🔥"

    is_fr = language.lower() in ("french", "français")
    raw_ts = event.get("timestamp", "")
    valid_ts = raw_ts + "Z" if (raw_ts and not raw_ts.endswith("Z")) else (raw_ts or format_match_timestamp(minute))

    return {
        "analyst_view": fr_analyst if is_fr else en_analyst,
        "fan_view": fr_fan if is_fr else en_fan,
        "multiaudience": {
            "en": {"analyst_view": en_analyst, "fan_view": en_fan},
            "fr": {"analyst_view": fr_analyst, "fan_view": fr_fan},
            "club_voices": {
                "Meteor City": f"💙 Goal update ({score['Meteor City']}-{score['Nova FC']}): {scorer_team} strikes at minute {minute}!",
                "Nova FC": f"💛 Score update at minute {minute}: Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
            }
        },
        "cited_event_ids": [event["event_id"]],
        "language_used": language,
        "target_persona": "General Fan",
        "timestamp": valid_ts,
        "match_minute": minute,
        "episode_id": episode_key,
        "stats_snapshot": {"score": dict(score)},
        "render_status": "TIER-0 (Live Goal Event)",
        "is_fallback": False
    }


async def generate_episode_narrative(
    match_id: str,
    alarm: dict,
    raw_events: list,
    force_live: bool = False,
    language: str = "English",
    persona: str = "General Fan",
    model_name: str = None
):
    model = model_name or DEFAULT_MODEL
    status = alarm.get("status", "ENTERED")
    episode_key = f"{match_id}_min{alarm['minute']}_{status}"
    cache_key = f"{episode_key}_{model}_{language}_{persona}"
    cache = load_cache()

    if not force_live and cache_key in cache and cache[cache_key].get("verified"):
        return cache[cache_key]["final_output"]

    factual_core = build_factual_core(alarm, language)
    trigger_ids = alarm.get("trigger_event_ids", [])
    valid_ids_set = set(trigger_ids)

    client = get_clients(model)
    agent = Agent(
        client=client,
        instructions=f"""You are a live football broadcast co-commentator (ExplainerAgent).
Language: {language}. Persona for fan_view: {persona}.
FACTS ALREADY FIXED BY PYTHON:
"{factual_core}"

YOUR TASK:
Provide general team-level stylistic commentary that builds upon the fixed facts.
STRICT RULES:
1. Write 1 short sentence for 'analyst_color' about collective spacing, tempo, or territorial control.
2. Write 1 hype sentence for 'fan_view'.
3. DO NOT write any numbers, digits, or number words. Python supplies all metrics.
4. DO NOT invent specific player positions or actions (NEVER mention winger, right-back, left-back, clever run, cross, header, corner, free kick, card, penalty, or injury).
5. In 'cited_event_ids', pick 1 or 2 real IDs from: {json.dumps(trigger_ids)}. Never use 'EVT-XXXX'.

Reply with ONLY valid JSON:
{{
  "analyst_color": "...",
  "fan_view": "...",
  "cited_event_ids": ["EVT-XXXX"]
}}"""
    )

    attempts = 0
    payload_obj = None
    errors = ["Initial"]
    rejection_history = []
    prompt = f"Add team-level color commentary for {episode_key}."

    while attempts < 2:
        try:
            t0 = time.monotonic()
            res = await agent.run(prompt)
            duration = round(time.monotonic() - t0, 1)

            clean_str = extract_json(res.text)
            payload_obj = ColorCommentaryPayload.model_validate_json(clean_str)
            errors = verify_color_commentary(payload_obj, alarm, valid_ids_set)

            if not errors:
                print(f"   ✅ [Verifier v5.1] Style validated in {duration}s")
                break
            else:
                err_msg = " | ".join(errors)
                rejection_history.append(err_msg)
                print(f"   ⚠️ [Verifier v5.1 Rejected]: {err_msg}")
                prompt = (
                    f"REJECTED: {err_msg}. "
                    f"Write general team-level commentary ONLY. No digits, no player positions (no winger/fullback/run). "
                    f"Pick IDs from {json.dumps(trigger_ids)}."
                )
        except Exception as e:
            err_msg = f"Format Error: {type(e).__name__}"
            rejection_history.append(err_msg)
            print(f"   ⚠️ [Format Error]: {err_msg}")
            prompt = f"Invalid JSON. Return only raw JSON matching the schema. Allowed IDs: {json.dumps(trigger_ids)}."
        attempts += 1

    if not payload_obj or errors:
        fb = generate_fallback_overlay(alarm, episode_key, language=language, persona=persona)
        fb["rejection_history"] = rejection_history
        return fb

    multi = build_multiaudience_views(alarm, analyst_color_en=payload_obj.analyst_color, fan_en=payload_obj.fan_view)
    if language.lower() in ("french", "français"):
        final_analyst = f"{factual_core} {payload_obj.analyst_color}".strip()
        multi["fr"]["analyst_view"] = final_analyst
        multi["fr"]["fan_view"] = payload_obj.fan_view
    else:
        final_analyst = multi["en"]["analyst_view"]

    final_json = {
        "analyst_view": final_analyst,
        "fan_view": payload_obj.fan_view,
        "multiaudience": multi,
        "cited_event_ids": payload_obj.cited_event_ids,
        "language_used": language,
        "target_persona": persona,
        "exit_reason": alarm.get("exit_reason"),
        "model_used": model,
        "timestamp": alarm.get("timestamp") or format_match_timestamp(alarm["minute"]),
        "match_minute": alarm["minute"],
        "episode_id": episode_key,
        "stats_snapshot": alarm.get("stats", {}),
        "rejection_history": rejection_history,
        "is_fallback": False
    }

    cache[cache_key] = {
        "verified": True,
        "attempts": attempts + 1,
        "rejection_history": rejection_history,
        "final_output": final_json
    }
    save_cache(cache)
    return final_json


def build_recap_factual_core(verified_overlays: list, score: dict, peak_swing: dict = None, language: str = "English") -> tuple[str, str, list]:
    """
    Dynamically derives the true match winner/draw and true pressing intervals
    from actual match score and verified episodes (zero hardcoded minutes or teams).
    """
    m_score = score.get("Meteor City", 0)
    n_score = score.get("Nova FC", 0)
    is_fr = language.lower() in ("french", "français")

    # 1. Dynamic outcome wording (Win / Loss / Draw)
    if m_score > n_score:
        outcome_en = f"Meteor City secures a {m_score}-{n_score} victory over Nova FC."
        outcome_fr = f"Meteor City s'impose {m_score}-{n_score} face à Nova FC."
    elif n_score > m_score:
        outcome_en = f"Nova FC claims a {n_score}-{m_score} victory against Meteor City."
        outcome_fr = f"Nova FC remporte le match {n_score}-{m_score} contre Meteor City."
    else:
        outcome_en = f"Meteor City and Nova FC share the spoils in a {m_score}-{n_score} draw."
        outcome_fr = f"Meteor City et Nova FC se quittent sur un match nul {m_score}-{n_score}."

    headline = (
        f"Score final : Meteor City {m_score} - {n_score} Nova FC"
        if is_fr else f"Full Time: Meteor City {m_score} - {n_score} Nova FC"
    )

    # 2. Dynamic pressing episodes extraction
    tactical_eps = [o for o in verified_overlays if "ENTERED" in o.get("episode_id", "") or "EXITED" in o.get("episode_id", "")]
    episode_ids = [o.get("episode_id", "ep") for o in verified_overlays]

    if tactical_eps:
        minutes = sorted(list({o.get("match_minute", 0) for o in tactical_eps}))
        if len(minutes) >= 2:
            press_en = f"Verified high-press tactical shifts occurred between minutes {minutes[0]} and {minutes[-1]}."
            press_fr = f"Des phases de pressing haut vérifiées ont rythmé la rencontre entre les minutes {minutes[0]} et {minutes[-1]}."
        else:
            press_en = f"A verified high-press tactical shift was recorded at minute {minutes[0]}."
            press_fr = f"Un changement de régime de pressing haut a été vérifié à la {minutes[0]}e minute."
    else:
        press_en = "No sustained high-press tactical regime shifts were triggered during this match."
        press_fr = "Aucun changement de régime de pressing haut prolongé n'a été déclenché durant ce match."

    # 3. Dynamic Turning Point
    tp_str_en, tp_str_fr = "", ""
    if peak_swing and peak_swing.get("minute", 0) > 0:
        tp_min = peak_swing["minute"]
        tp_team = peak_swing["team"]
        tp_val = peak_swing.get("value", 0.0)
        tp_str_en = f" The peak Momentum Index swing ({tp_val:+.1f} for {tp_team}) occurred at minute {tp_min}."
        tp_str_fr = f" Le pic de Momentum ({tp_val:+.1f} pour {tp_team}) a été mesuré à la {tp_min}e minute."

    factual_summary = f"{outcome_fr} {press_fr}{tp_str_fr}" if is_fr else f"{outcome_en} {press_en}{tp_str_en}"
    return headline, factual_summary, episode_ids


async def generate_match_recap(
    match_id: str,
    verified_overlays: list,
    score: dict,
    peak_swing: dict = None,
    language: str = "English",
    model_name: str = None,
    use_llm: bool = True
) -> dict:
    """
    Second Collaborative Agent (RecapAgent — Track 3):
    Receives structured handoff of verified_overlays from ExplainerAgent, builds dynamic
    factual core in Python, and asks RecapAgent for a verified 1-sentence tactical synthesis.
    """
    model = model_name or DEFAULT_MODEL
    headline, factual_summary, episode_ids = build_recap_factual_core(verified_overlays, score, peak_swing, language)

    default_closing = (
        "La discipline collective aura dicté le tempo jusqu'au coup de sifflet final."
        if language.lower() in ("french", "français")
        else "Collective spatial discipline ultimately dictated the tempo of the fixture."
    )

    if not use_llm or not episode_ids:
        return {
            "headline": headline,
            "tactical_summary": f"{factual_summary} {default_closing}".strip(),
            "turning_point": peak_swing or {},
            "key_episode_ids": episode_ids,
            "agent_handoff_count": len(verified_overlays),
            "recap_verified": True
        }

    client = get_clients(model)
    valid_ep_set = set(episode_ids)
    recap_agent = Agent(
        client=client,
        instructions=f"""You are the Post-Match Tactical Editor (RecapAgent).
You receive the verified episode handoff from the live ExplainerAgent:
FIXED MATCH FACTS: "{factual_summary}"
VERIFIED EPISODE IDS: {json.dumps(episode_ids)}

YOUR TASK:
Write 1 concluding sentence ('tactical_color') synthesizing the overall tactical flow in {language}.
STRICT RULES:
1. DO NOT write any numbers, digits, or number words.
2. DO NOT invent cards, injuries, penalties, corners, or player positions.
3. Cite 1 or 2 real IDs from VERIFIED EPISODE IDS in 'key_episode_ids'.

Reply with ONLY valid JSON:
{{
  "tactical_color": "...",
  "key_episode_ids": {json.dumps(episode_ids[:2])}
}}"""
    )

    try:
        res = await asyncio.wait_for(recap_agent.run("Synthesize post-match tactical color from ExplainerAgent handoff."), timeout=15.0)
        parsed = MatchRecapPayload.model_validate_json(extract_json(res.text))
        dummy_alarm = {"team": "Meteor City", "victim": "Nova FC", "status": "ENTERED", "minute": 90}
        color_check = ColorCommentaryPayload(
            analyst_color=parsed.tactical_color,
            fan_view="ok",
            cited_event_ids=[ parsed.key_episode_ids[0] ] if parsed.key_episode_ids else ["INVALID"]
        )
        errs = verify_color_commentary(color_check, dummy_alarm, valid_ep_set)
        if not errs:
            return {
                "headline": headline,
                "tactical_summary": f"{factual_summary} {parsed.tactical_color}".strip(),
                "turning_point": peak_swing or {},
                "key_episode_ids": parsed.key_episode_ids,
                "agent_handoff_count": len(verified_overlays),
                "recap_verified": True
            }
    except Exception:
        pass

    return {
        "headline": headline,
        "tactical_summary": f"{factual_summary} {default_closing}".strip(),
        "turning_point": peak_swing or {},
        "key_episode_ids": episode_ids,
        "agent_handoff_count": len(verified_overlays),
        "recap_verified": False
    }
