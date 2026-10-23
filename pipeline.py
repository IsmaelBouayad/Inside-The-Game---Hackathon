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
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
MATCH_KICKOFF = datetime(2026, 10, 27, 15, 0, 0)

NUMBER_WORDS_REGEX = (
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|dozen|twice|thrice|"
    r"zéro|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|"
    r"treize|quatorze|quinze|seize|vingt|trente|quarante|cinquante|soixante|cent|douzaine)\b"
)

HALLUCINATION_TRIGGERS = [
    r"red card", r"yellow card", r"carton rouge", r"carton jaune",
    r"penalty", r"pénalty", r"injury", r"injured", r"blessé", r"blessure",
    r"sent off", r"expulsé", r"handball", r"offside", r"hors-jeu",
    r"corner", r"free kick", r"coup franc", r"\bheader\b",
    r"\bwinger\b", r"\bailier\b", r"right-back", r"right back", r"left-back", r"left back",
    r"full-back", r"fullback", r"clever run", r"through ball", r"\bcross\b",
    r"substitution", r"\bsub\b", r"\bvar\b", r"under siege", r"flurry of attacks"
]


class ColorCommentaryPayload(BaseModel):
    analyst_color: str
    fan_view: str
    cited_event_ids: List[str] = Field(min_length=1)


class MatchRecapPayload(BaseModel):
    tactical_color: str
    key_episode_ids: List[str] = Field(min_length=1)


def format_match_timestamp(minute: int) -> str:
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
    native_client = AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    return OpenAIChatCompletionClient(model=model, async_client=native_client)


async def warmup_ollama(model_name: str = None):
    model = model_name or DEFAULT_MODEL
    try:
        t0 = time.monotonic()
        native_client = AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
        await native_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=2
        )
        print(f"🔥 [Warmup] Model '{model}' ready in RAM ({round(time.monotonic() - t0, 2)}s)")
    except Exception as e:
        print(f"⚠️ [Warmup] Note: '{model}' will initialize on first request ({e})")


def extract_json(text: str) -> str:
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        candidate = text[start:end + 1]
        candidate = re.sub(r",\s*}", "}", candidate)
        candidate = re.sub(r",\s*]", "]", candidate)
        return candidate
    return text


def coerce_color_payload(raw_text: str, trigger_ids: list) -> ColorCommentaryPayload:
    """
    Structural JSON parser (normalizes key aliases and string-vs-list for cited_event_ids).
    Does NOT rewrite or strip forbidden numbers/words from the LLM text: all content
    violations are strictly evaluated and rejected by verify_color_commentary().
    """
    clean_str = extract_json(raw_text)
    data = json.loads(clean_str)
    if not isinstance(data, dict):
        raise ValueError("JSON root is not an object")

    analyst_color = (
        data.get("analyst_color")
        or data.get("analyst_view")
        or data.get("tactical_color")
        or data.get("commentary")
    )
    fan_view = (
        data.get("fan_view")
        or data.get("supporter_view")
        or data.get("fan_reaction")
    )
    if not isinstance(analyst_color, str) or not analyst_color.strip():
        raise ValueError("Missing analyst_color string")
    if not isinstance(fan_view, str) or not fan_view.strip():
        raise ValueError("Missing fan_view string")

    raw_ids = data.get("cited_event_ids") or data.get("event_ids") or data.get("key_episode_ids")
    if isinstance(raw_ids, str):
        cited_ids = [raw_ids]
    elif isinstance(raw_ids, list) and len(raw_ids) > 0:
        cited_ids = [str(x) for x in raw_ids]
    else:
        cited_ids = [trigger_ids[0]] if trigger_ids else ["EVT-01"]

    return ColorCommentaryPayload(
        analyst_color=analyst_color.strip(),
        fan_view=fan_view.strip(),
        cited_event_ids=cited_ids
    )


def coerce_recap_payload(raw_text: str, episode_ids: list) -> MatchRecapPayload:
    clean_str = extract_json(raw_text)
    data = json.loads(clean_str)
    tc = data.get("tactical_color") or data.get("tactical_summary") or data.get("summary")
    if not isinstance(tc, str) or not tc.strip():
        raise ValueError("Missing tactical_color string")

    raw_eps = data.get("key_episode_ids") or data.get("cited_event_ids")
    if isinstance(raw_eps, str):
        clean_eps = [raw_eps]
    elif isinstance(raw_eps, list) and len(raw_eps) > 0:
        clean_eps = [str(x) for x in raw_eps]
    else:
        clean_eps = episode_ids[:2]

    return MatchRecapPayload(tactical_color=tc.strip(), key_episode_ids=clean_eps)


def build_factual_core(alarm: dict, language: str = "English") -> str:
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
    errors = []

    if not payload.cited_event_ids:
        errors.append("No event IDs cited.")
    else:
        normalized_map = {re.sub(r"[_\-]", "-", v.upper()): v for v in valid_event_ids}
        cleaned_ids = []
        invalid = []
        for eid in payload.cited_event_ids:
            norm_key = re.sub(r"[_\-]", "-", eid.strip().upper())
            if "XXXX" not in norm_key and norm_key in normalized_map:
                cleaned_ids.append(normalized_map[norm_key])
            else:
                invalid.append(eid)
        if invalid:
            errors.append(f"Invalid cited IDs: {invalid}. Allowed: {sorted(list(valid_event_ids))}")
        else:
            payload.cited_event_ids = cleaned_ids

    ac = payload.analyst_color.strip()
    fv = payload.fan_view.strip()
    combined = f"{ac} {fv}".strip()
    combined_lower = combined.lower()
    ac_lower = ac.lower()

    if "..." in combined or "…" in combined:
        errors.append("Ellipsis ('...') is forbidden: write complete, self-contained sentences.")

    text_no_ids = re.sub(r"EVT-[A-Za-z0-9_-]+", "", combined)
    if re.search(r"\d", text_no_ids):
        found = re.findall(r"\d+", text_no_ids)
        errors.append(f"Digits are strictly forbidden in LLM color text: {found}. Python supplies all metrics.")

    if re.search(NUMBER_WORDS_REGEX, combined_lower):
        errors.append("Number words are forbidden in LLM color text. Python supplies all metrics.")

    for h in HALLUCINATION_TRIGGERS:
        pattern = h if h.startswith(r"\b") else rf"\b{re.escape(h)}\b"
        if re.search(pattern, combined_lower):
            errors.append(f"Hallucinated match incident or unverified micro-action detected: '{h}'.")

    victim = alarm["victim"].lower()
    team = alarm["team"].lower()
    status = alarm.get("status", "ENTERED")

    if status == "ENTERED" and re.search(rf"\b{re.escape(team)}\b.*(?:scrambling|all over the place|panics|collapses|struggling|pinned|panique|subit)", ac_lower):
        errors.append(f"Role inversion: {alarm['team']} is the pressing aggressor, not scrambling on defense.")

    if status == "ENTERED":
        if re.search(rf"\b{re.escape(victim)}\b\s+(?:presses|pressing|suffocates|hounds|destroys|dominates|locks|traps|exploits|attacking|presse|étouffe|harcèle|domine|accule)", combined_lower):
            errors.append(f"Role inversion: {alarm['victim']} cannot be described as the aggressor during ENTERED state.")
        if re.search(rf"\b{re.escape(team)}\b.*(?:scrambling|all over the place|panics|collapses|struggling|pinned|panique|subit|accule)", combined_lower):
            errors.append(f"Role inversion: {alarm['team']} is the pressing aggressor, not scrambling on defense.")
    elif status == "EXITED":
        if re.search(rf"\b{re.escape(team)}\b\s+(?:escapes|breaks\s+the\s+press|breaks\s+free|s'échappe|casse\s+le\s+pressing|sort\s+du\s+pressing)", combined_lower):
            errors.append(f"Role inversion: {alarm['team']} cannot be described as escaping the press during EXITED state.")

    return errors


def verify_recap_output(payload: MatchRecapPayload, valid_episode_ids: set) -> list:
    errors = []
    if not payload.key_episode_ids:
        errors.append("No key_episode_ids cited in recap.")
    else:
        invalid_eps = [eid for eid in payload.key_episode_ids if eid not in valid_episode_ids]
        if invalid_eps:
            errors.append(f"Invalid key_episode_ids in recap: {invalid_eps}. Allowed: {sorted(list(valid_episode_ids))}")

    tc = payload.tactical_color.strip()
    tc_lower = tc.lower()

    if "..." in tc or "…" in tc:
        errors.append("Ellipsis ('...') is forbidden in recap tactical_color.")

    if re.search(r"\d", tc):
        errors.append("Digits are forbidden in recap tactical_color (Python factual core supplies all numbers).")

    if re.search(NUMBER_WORDS_REGEX, tc_lower):
        errors.append("Number words are forbidden in recap tactical_color.")

    for h in HALLUCINATION_TRIGGERS:
        pattern = h if h.startswith(r"\b") else rf"\b{re.escape(h)}\b"
        if re.search(pattern, tc_lower):
            errors.append(f"Unverified incident in recap tactical_color: '{h}'.")

    return errors


def build_multiaudience_views(alarm: dict, analyst_color_en: str = "", fan_en: str = "") -> dict:
    fact_en = build_factual_core(alarm, "English")
    fact_fr = build_factual_core(alarm, "French")
    status = alarm.get("status", "ENTERED")
    exit_reason = alarm.get("exit_reason") or ("recovered" if (alarm.get("stats", {}).get("pass_acc") or 0) > 0.75 else "exhausted")
    team = alarm["team"]
    victim = alarm["victim"]

    if status == "ENTERED":
        default_color_en = "The collective block compresses space and disrupts short passing options."
        color_fr = "Le bloc collectif resserre les lignes et verrouille la relance courte."
        fan_fr = f"Quel pressing étouffant de {team} ! La relance adverse est bloquée !"
        club_meteor = f"Meteor City imposes total territorial control!" if team == "Meteor City" else f"Meteor City must stay composed under {team}'s press!"
        club_nova = f"Nova FC hunting in packs high up the pitch!" if team == "Nova FC" else f"Nova FC under heavy pressure in their own third!"
    else:
        if exit_reason == "recovered":
            default_color_en = "Composed ball circulation neutralizes the high block."
            color_fr = "Une circulation de balle maîtrisée permet de franchir le premier rideau."
            fan_fr = f"Superbe sortie de balle de {victim} sous pression !"
        else:
            default_color_en = "The pressing intensity drops off, restoring normal build-up phases."
            color_fr = "L'intensité du pressing adverse baisse, permettant de temporiser."
            fan_fr = f"Le pressing de {team} s'essouffle, {victim} reprend le contrôle du ballon !"
        club_meteor = "Meteor City resets the tempo and organizes the midfield!"
        club_nova = "Nova FC stabilizes possession and looks forward!"

    use_color_en = analyst_color_en if analyst_color_en else default_color_en
    use_fan_en = fan_en if fan_en else (f"{team} turns up the heat!" if status == "ENTERED" else f"{victim} regains control of the tempo!")

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
    en_fan = f"GOOOAAAL! Clinical finish by {player} for {scorer_team}!"
    fr_analyst = f"BUT à la {minute}e minute ! {player} ({scorer_team}) marque. Score : Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
    fr_fan = f"BUUUT ! Finition décisive de {player} pour {scorer_team} !"

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
                "Meteor City": f"Goal update ({score['Meteor City']}-{score['Nova FC']}): {scorer_team} strikes at minute {minute}!",
                "Nova FC": f"Score update at minute {minute}: Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
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
    first_valid_id = trigger_ids[0] if trigger_ids else "EVT-01"

    # Qualitative context prevents the small LLM from echoing raw digits from the Python factual core
    qualitative_ctx = (
        f"Regime: High Press {status}. Pressing team: {alarm['team']}. Build-up team: {alarm['victim']}. "
        f"Exit cause: {alarm.get('exit_reason') or 'active press'}."
    )

    client = get_clients(model)
    agent = Agent(
        client=client,
        instructions=f"""You are a football broadcast co-commentator (ExplainerAgent).
Language: {language}. Persona: {persona}.
TACTICAL CONTEXT: {qualitative_ctx}
(Note: Python automatically prepends the exact minute and statistics sentence before your sentence.)

STRICT RULES:
1. Write 1 complete sentence for 'analyst_color' describing collective spacing, tempo, or passing lanes.
2. Write 1 short hype sentence for 'fan_view'.
3. NEVER write any digits (0-9) or number words (two, three, ten, etc.) anywhere in 'analyst_color' or 'fan_view'.
4. NEVER use '...' ellipses, and NEVER mention cards, injuries, penalties, corners, substitutions, VAR, or winger/full-back runs.
5. In 'cited_event_ids', output a JSON list containing "{first_valid_id}".

Reply with ONLY raw valid JSON:
{{
  "analyst_color": "The compact midfield block closes central passing lanes and forces hurried clearances.",
  "fan_view": "Relentless pressure across the pitch!",
  "cited_event_ids": ["{first_valid_id}"]
}}"""
    )

    attempts = 0
    payload_obj = None
    errors = ["Initial"]
    rejection_history = []
    prompt = f"Generate JSON commentary in {language} for {qualitative_ctx}. Use Zero digits."

    while attempts < 2:
        try:
            t0 = time.monotonic()
            res = await agent.run(prompt)
            duration = round(time.monotonic() - t0, 1)

            payload_obj = coerce_color_payload(res.text, trigger_ids)
            errors = verify_color_commentary(payload_obj, alarm, valid_ids_set)

            if not errors:
                print(f"   ✅ [Verifier v5.2] Style validated in {duration}s")
                break
            else:
                err_msg = " | ".join(errors)
                rejection_history.append(err_msg)
                print(f"   ⚠️ [Verifier v5.2 Rejected]: {err_msg}")
                prompt = (
                    f"REJECTED: {err_msg}\n"
                    f"Write ZERO digits and ZERO number words. Reply with ONLY valid JSON:\n"
                    f'{{"analyst_color": "The collective block compresses space and disrupts short passing lanes.", '
                    f'"fan_view": "Huge tactical intensity on the pitch!", '
                    f'"cited_event_ids": ["{first_valid_id}"]}}'
                )
        except Exception as e:
            err_msg = f"Format Error: {type(e).__name__}"
            rejection_history.append(err_msg)
            print(f"   ⚠️ [Format Error]: {err_msg}")
            prompt = (
                f"Invalid JSON. Reply with ONLY raw JSON matching these exact 3 keys:\n"
                f'{{"analyst_color": "Collective spacing narrows passing lanes across the pitch.", '
                f'"fan_view": "High intensity from the pressing unit!", '
                f'"cited_event_ids": ["{first_valid_id}"]}}'
            )
        attempts += 1

    if not payload_obj or errors:
        fb = generate_fallback_overlay(alarm, episode_key, language=language, persona=persona)
        fb["rejection_history"] = rejection_history
        return fb

    if language.lower() in ("french", "français"):
        multi = build_multiaudience_views(alarm, analyst_color_en="", fan_en="")
        final_analyst = f"{factual_core} {payload_obj.analyst_color}".strip()
        multi["fr"]["analyst_view"] = final_analyst
        multi["fr"]["fan_view"] = payload_obj.fan_view
    else:
        multi = build_multiaudience_views(alarm, analyst_color_en=payload_obj.analyst_color, fan_en=payload_obj.fan_view)
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
    m_score = score.get("Meteor City", 0)
    n_score = score.get("Nova FC", 0)
    is_fr = language.lower() in ("french", "français")

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

    tactical_eps = [o for o in verified_overlays if "ENTERED" in o.get("episode_id", "") or "EXITED" in o.get("episode_id", "")]
    episode_ids = [o.get("episode_id", "ep") for o in verified_overlays]

    if tactical_eps:
        minutes = sorted(list({o.get("match_minute", 0) for o in tactical_eps}))
        if len(minutes) >= 2:
            press_en = f"Observed high-press regime spanned minutes {minutes[0]} to {minutes[-1]} (first confirmed by the causal detector at minute {minutes[0]})."
            press_fr = f"La phase de pressing haut observée s'est étendue des minutes {minutes[0]} à {minutes[-1]} (confirmée par le détecteur causal à la {minutes[0]}e minute)."
        else:
            press_en = f"A verified high-press tactical shift was recorded at minute {minutes[0]}."
            press_fr = f"Un changement de régime de pressing haut a été vérifié à la {minutes[0]}e minute."
    else:
        press_en = "No sustained high-press tactical regime shifts were triggered during this match."
        press_fr = "Aucun changement de régime de pressing haut prolongé n'a été déclenché durant ce match."

    factual_summary = f"{outcome_fr} {press_fr}" if is_fr else f"{outcome_en} {press_en}"
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
    model = model_name or DEFAULT_MODEL
    headline, factual_summary, episode_ids = build_recap_factual_core(verified_overlays, score, peak_swing, language)

    tactical_eps = [o for o in verified_overlays if "ENTERED" in o.get("episode_id", "")]
    turning_point_info = (
        {"minute": tactical_eps[0].get("match_minute"), "episode_id": tactical_eps[0].get("episode_id")}
        if tactical_eps else (peak_swing or {})
    )

    default_closing = (
        "La maîtrise collective des transitions aura dicté le rythme jusqu'au coup de sifflet final."
        if language.lower() in ("french", "français")
        else "Collective spatial discipline across transition phases ultimately dictated the tempo of the fixture."
    )

    if not use_llm or not episode_ids:
        return {
            "headline": headline,
            "tactical_summary": f"{factual_summary} {default_closing}".strip(),
            "turning_point": turning_point_info,
            "key_episode_ids": episode_ids,
            "agent_handoff_count": len(verified_overlays),
            "recap_verified": False,
            "verification_mode": "deterministic_fallback"
        }

    client = get_clients(model)
    valid_ep_set = set(episode_ids)
    allowed_sample = episode_ids[:2]
    recap_agent = Agent(
        client=client,
        instructions=f"""You are the Post-Match Tactical Editor (RecapAgent).
Write 1 concluding sentence ('tactical_color') in {language} synthesizing how collective spatial discipline shaped the match tempo.
STRICT RULES:
1. Write ZERO digits (0-9) and ZERO number words.
2. NEVER use '...' ellipses or mention cards, injuries, penalties, corners, substitutions, or VAR.
3. In 'key_episode_ids', copy this exact list: {json.dumps(allowed_sample)}

Reply with ONLY raw valid JSON:
{{
  "tactical_color": "Sustained territorial compactness in the second half decisive shifted the balance of play.",
  "key_episode_ids": {json.dumps(allowed_sample)}
}}"""
    )

    recap_prompt = "Synthesize post-match tactical color without any numbers. Output ONLY valid JSON."
    for attempt in range(2):
        try:
            res = await asyncio.wait_for(recap_agent.run(recap_prompt), timeout=25.0)
            parsed = coerce_recap_payload(res.text, episode_ids)
            errs = verify_recap_output(parsed, valid_ep_set)
            if not errs:
                return {
                    "headline": headline,
                    "tactical_summary": f"{factual_summary} {parsed.tactical_color}".strip(),
                    "turning_point": turning_point_info,
                    "key_episode_ids": parsed.key_episode_ids,
                    "agent_handoff_count": len(verified_overlays),
                    "recap_verified": True,
                    "verification_mode": "llm_verified"
                }
            recap_prompt = (
                f"REJECTED: {' | '.join(errs)}. Write ZERO digits and ZERO number words. Reply ONLY with JSON:\n"
                f'{{"tactical_color": "Collective spatial discipline across transition phases dictated the tempo.", '
                f'"key_episode_ids": {json.dumps(allowed_sample)}}}'
            )
        except Exception as e:
            recap_prompt = (
                f"Format error ({type(e).__name__}). Reply ONLY with valid JSON:\n"
                f'{{"tactical_color": "Collective spatial discipline across transition phases dictated the tempo.", '
                f'"key_episode_ids": {json.dumps(allowed_sample)}}}'
            )

    return {
        "headline": headline,
        "tactical_summary": f"{factual_summary} {default_closing}".strip(),
        "turning_point": turning_point_info,
        "key_episode_ids": episode_ids,
        "agent_handoff_count": len(verified_overlays),
        "recap_verified": False,
        "verification_mode": "deterministic_fallback"
    }
