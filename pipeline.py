import os
import json
import asyncio
import re
import time
from openai import AsyncOpenAI
from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient
from pydantic import BaseModel, Field
from typing import List

CACHE_FILE = "demo_cache.json"
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

class ColorCommentaryPayload(BaseModel):
    analyst_color: str
    fan_view: str
    cited_event_ids: List[str] = Field(min_length=1)

class MatchRecapPayload(BaseModel):
    headline: str
    tactical_summary: str
    key_episode_ids: List[str] = Field(min_length=1)

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
        print(f"🔥 [Warmup] Modèle '{model}' prêt en RAM ({round(time.monotonic() - t0, 2)}s)")
    except Exception as e:
        print(f"⚠️ [Warmup] Note: '{model}' démarrera à la première requête ({e})")

def extract_json(text: str) -> str:
    text = text.strip()
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return text[start:end+1]
    return text

def build_factual_core(alarm: dict, language: str = "English") -> str:
    """Généré à 100% par Python : Vérité terrain mathématique inattaquable."""
    minute = alarm["minute"]
    team = alarm["team"]
    victim = alarm["victim"]
    status = alarm.get("status", "ENTERED")
    stats = alarm.get("stats", {})
    def_actions = stats.get("def_actions", 0)
    pass_acc = stats.get("pass_acc")
    acc_pct = int(round(pass_acc * 100)) if pass_acc is not None else None

    if language.lower() in ("french", "français"):
        if status == "ENTERED":
            acc_str = f", réduisant l'efficacité de passes adverse à {acc_pct}%" if acc_pct is not None else ""
            return f"À la {minute}e minute, {team} impose un pressing haut intense avec {def_actions} actions défensives contre {victim}{acc_str}."
        else:
            acc_str = f" avec {acc_pct}% de passes réussies" if acc_pct is not None else ""
            return f"À la {minute}e minute, {victim} s'extirpe du pressing de {team}{acc_str} après {def_actions} actions défensives subies."
    else:
        if status == "ENTERED":
            acc_str = f", reducing build-up accuracy to {acc_pct}%" if acc_pct is not None else ""
            return f"At minute {minute}, {team} initiates a high press with {def_actions} defensive actions against {victim}{acc_str}."
        else:
            acc_str = f" with {acc_pct}% pass accuracy" if acc_pct is not None else ""
            return f"At minute {minute}, {victim} breaks the press of {team}{acc_str} following {def_actions} defensive actions."

def verify_color_commentary(payload: ColorCommentaryPayload, alarm: dict, valid_event_ids: set) -> list:
    """
    Vérificateur v5 (Facts by Python, Color by LLM) :
    1. IDs réels obligatoires (pas de placeholder 'EVT-XXXX').
    2. Interdiction absolue de chiffres dans le texte du LLM (anti-inventions mathématiques/temporelles).
    3. Interdiction des mots d'inventions factuelles (cartons, blessures, pénaltys non survenus).
    4. Interdiction de mentionner la victime comme agresseur dans le fan_view.
    """
    errors = []

    # 1. Validation des IDs
    if not payload.cited_event_ids:
        errors.append("No event IDs cited.")
    else:
        invalid = [eid for eid in payload.cited_event_ids if eid not in valid_event_ids or "XXXX" in eid]
        if invalid:
            errors.append(f"Invalid cited IDs: {invalid}. Allowed: {sorted(list(valid_event_ids))}")

    combined = f"{payload.analyst_color} {payload.fan_view}".strip()
    combined_lower = combined.lower()

    # 2. Règle d'or : Aucun chiffre dans la partie style (Python gère tous les chiffres)
    text_no_ids = re.sub(r"EVT-[A-Za-z0-9_-]+", "", combined)
    if re.search(r"\d", text_no_ids):
        found = re.findall(r"\d+", text_no_ids)
        errors.append(f"Digits are strictly forbidden in LLM color text: {found}. Python supplies all metrics.")

    # Nombres écrits en lettres interdits
    number_words = r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty|fifty|ninety|dix|douze|quatorze)\b"
    if re.search(number_words, combined_lower):
        errors.append("Number words are forbidden in LLM color text. Python supplies all metrics.")

    # 3. Interdiction absolue des hallucinations d'incidents non survenus
    hallucination_triggers = [
        "red card", "yellow card", "carton rouge", "carton jaune",
        "penalty", "pénalty", "injury", "injured", "blessé", "blessure",
        "sent off", "expulsé", "handball", "offside", "hors-jeu"
    ]
    for h in hallucination_triggers:
        if h in combined_lower:
            errors.append(f"Hallucinated match incident detected: '{h}'.")

    # 4. Anti-inversion des rôles dans le fan_view
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

def generate_fallback_overlay(alarm: dict, episode_key: str, language: str = "English", persona: str = "General Fan") -> dict:
    factual = build_factual_core(alarm, language)
    trigger_ids = alarm.get("trigger_event_ids", [])
    team = alarm["team"]
    victim = alarm["victim"]

    if language.lower() in ("french", "français"):
        color = "La structure tactique est sous tension maximale." if alarm.get("status") == "ENTERED" else "La relance propre permet de respirer."
        fan = f"Allez {team} ! Le pressing est total ! 🔥" if alarm.get("status") == "ENTERED" else f"Bravo {victim} ! Sortie de balle parfaite ! 🏃‍♂️💨"
    else:
        color = "Tactical structure is under severe territorial strain." if alarm.get("status") == "ENTERED" else "Clean ball progression relieves defensive pressure."
        fan = f"{team} turns up the heat! Relentless pressure! 🔥" if alarm.get("status") == "ENTERED" else f"{victim} escapes the trap with composure! 🏃‍♂️💨"

    return {
        "analyst_view": f"{factual} {color}",
        "fan_view": fan,
        "cited_event_ids": trigger_ids[:2],
        "language_used": language,
        "target_persona": persona,
        "timestamp": f"2026-10-27T15:{alarm['minute']:02d}:00Z",
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

    if language.lower() in ("french", "français"):
        analyst = f"BUT à la {minute}e minute ! {player} ({scorer_team}) marque. Score : Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
        fan = f"BUUUT ! Magnifique finition de {player} pour {scorer_team} ! ⚽🔥"
    else:
        analyst = f"GOAL at minute {minute}! {player} ({scorer_team}) scores. Score is now Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC."
        fan = f"GOOOAAAL! Superb finish from {player} for {scorer_team}! ⚽🔥"

    return {
        "analyst_view": analyst,
        "fan_view": fan,
        "cited_event_ids": [event["event_id"]],
        "language_used": language,
        "target_persona": "General Fan",
        "timestamp": event["timestamp"],
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
        instructions=f"""You are a live football broadcast co-commentator.
Language: {language}. Persona for fan_view: {persona}.
FACTS ALREADY FIXED BY PYTHON:
"{factual_core}"

YOUR TASK:
Provide stylistic color commentary that builds upon the fixed facts.
RULES:
1. Write 1 short tactical sentence for 'analyst_color' explaining the tactical consequence.
2. Write 1 hype sentence for 'fan_view'.
3. DO NOT write any numbers or digits (no minutes, percentages, or statistics). Python supplies all numbers.
4. DO NOT invent cards, injuries, penalties, or incidents.
5. In 'cited_event_ids', cite 1 or 2 IDs from: {json.dumps(trigger_ids)}. Do NOT use 'EVT-XXXX'.

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
    prompt = f"Add color commentary for episode {episode_key}."

    while attempts < 2:
        try:
            t0 = time.monotonic()
            res = await agent.run(prompt)
            duration = round(time.monotonic() - t0, 1)

            clean_str = extract_json(res.text)
            payload_obj = ColorCommentaryPayload.model_validate_json(clean_str)
            errors = verify_color_commentary(payload_obj, alarm, valid_ids_set)

            if not errors:
                print(f"   ✅ [Vérificateur v5] Style validé en {duration}s")
                break
            else:
                err_msg = " | ".join(errors)
                rejection_history.append(err_msg)
                print(f"   ⚠️ [Rejet Vérificateur v5]: {err_msg}")
                prompt = f"REJECTED: {err_msg}. Do NOT use digits or number words. Pick real IDs from {json.dumps(trigger_ids)}."
        except Exception as e:
            err_msg = f"Format Error: {type(e).__name__}"
            rejection_history.append(err_msg)
            print(f"   ⚠️ [Erreur format]: {err_msg}")
            prompt = f"Invalid JSON. Return only raw JSON matching the schema. Allowed IDs: {json.dumps(trigger_ids)}."
        attempts += 1

    if not payload_obj or errors:
        fb = generate_fallback_overlay(alarm, episode_key, language=language, persona=persona)
        fb["rejection_history"] = rejection_history
        return fb

    final_analyst = f"{factual_core} {payload_obj.analyst_color}".strip()
    final_json = {
        "analyst_view": final_analyst,
        "fan_view": payload_obj.fan_view,
        "cited_event_ids": payload_obj.cited_event_ids,
        "language_used": language,
        "target_persona": persona,
        "model_used": model,
        "timestamp": f"2026-10-27T15:{alarm['minute']:02d}:00Z",
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

async def generate_match_recap(match_id: str, verified_overlays: list, score: dict, language: str = "English", model_name: str = None) -> dict:
    """RecapAgent (Track 3) : Ancré strictement sur les faits vérifiés en Python."""
    model = model_name or DEFAULT_MODEL
    episode_ids = [o.get("episode_id", "ep") for o in verified_overlays]
    
    factual_bullet_points = [
        f"Minute {o.get('match_minute')}: {o.get('analyst_view')}"
        for o in verified_overlays
    ]
    facts_block = "\n".join(factual_bullet_points) if factual_bullet_points else "No major tactical shifts recorded."

    headline_fallback = (
        f"Score final : Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC"
        if language.lower() in ("french", "français")
        else f"Full Time: Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC"
    )
    summary_fallback = (
        f"Meteor City s'impose {score['Meteor City']}-{score['Nova FC']} grâce à un pressing haut soutenu entre les minutes 57 et 62."
        if language.lower() in ("french", "français")
        else f"Meteor City takes the win {score['Meteor City']}-{score['Nova FC']} supported by sustained high pressing between minutes 57 and 62."
    )

    client = get_clients(model)
    recap_agent = Agent(
        client=client,
        instructions=f"""You are a sports journalist writing a 2-sentence post-match tactical summary.
Language: {language}.
VERIFIED MATCH FACTS (DO NOT INVENT ANYTHING BEYOND THIS):
Score: Meteor City {score['Meteor City']} - {score['Nova FC']} Nova FC
Events:
{facts_block}

RULES:
1. Do not invent counter-attacks, cards, or injuries unless explicitly stated in the facts.
2. Stick strictly to the verified score and pressing phases.
Reply with ONLY valid JSON:
{{
  "headline": "{headline_fallback}",
  "tactical_summary": "...",
  "key_episode_ids": {json.dumps(episode_ids[:3])}
}}"""
    )
    try:
        res = await asyncio.wait_for(recap_agent.run("Generate match summary JSON."), timeout=20.0)
        parsed = MatchRecapPayload.model_validate_json(extract_json(res.text))
        return parsed.model_dump()
    except Exception:
        return {
            "headline": headline_fallback,
            "tactical_summary": summary_fallback,
            "key_episode_ids": episode_ids
        }
