import streamlit as st
import json
import time
import os

st.set_page_config(page_title="Inside The Game - Broadcast", layout="wide")
st.title("📺 Inside The Game — Régie TV Edge AI")
st.caption("Tactical Momentum Shift & Tier-0 Event Pipeline • Microsoft Agent Framework + Local LLM + Fabric Sink")

UI_FILE = "broadcast_ui.jsonl"
CLOCK_FILE = "match_clock.json"
METRICS_FILE = "engine_metrics.json"
RECAP_FILE = "match_recap.json"

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def load_episodes():
    if not os.path.exists(UI_FILE):
        return []
    by_episode = {}
    try:
        with open(UI_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                ep_id = item.get("episode_id")
                if ep_id not in by_episode:
                    by_episode[ep_id] = item
                else:
                    seq = by_episode[ep_id].get("episode_seq", 0)
                    by_episode[ep_id] = item
                    by_episode[ep_id]["episode_seq"] = seq
    except Exception:
        pass
    return sorted(by_episode.values(), key=lambda x: x.get("episode_seq", 0))

main_placeholder = st.empty()
sidebar_placeholder = st.sidebar.empty()

while True:
    episodes = load_episodes()
    clock = load_json(CLOCK_FILE)
    metrics = load_json(METRICS_FILE)
    recap = load_json(RECAP_FILE)

    with sidebar_placeholder.container():
        st.markdown("### ⏱️ Horloge & Score Direct")
        if clock:
            score = clock.get("score", {"Meteor City": 0, "Nova FC": 0})
            st.metric("Minute de jeu", f"{clock.get('minute', 0)}'")
            st.metric("Score", f"Meteor {score['Meteor City']} - {score['Nova FC']} Nova")
            st.caption(f"Régime : **{clock.get('tactical_state', 'Normal')}** | Vitesse : **x{clock.get('current_speed', 60)}**")
        else:
            st.info("En attente du coup d'envoi...")

        st.markdown("---")
        st.markdown("### 📊 Métriques Edge Engine")
        if metrics:
            st.metric("Événements analysés", metrics.get("events", 0))
            st.metric("Alarmes tactiques", metrics.get("alarms", 0))
            st.metric("Buts narrés (Tier-0)", metrics.get("goals_narrated_tier0", 0))
            st.metric("Overlays IA validés", metrics.get("llm_verified", 0))
            if metrics.get("llm_latency_sec_median"):
                st.metric("Latence médiane LLM", f"{metrics['llm_latency_sec_median']}s")
            st.caption(f"☁️ Fabric Delivery: `{metrics.get('fabric_delivery_mode', 'local')}`")

    with main_placeholder.container():
        if not episodes:
            st.info("⚽ Match en cours... Surveillance tactique active.")
        else:
            latest = episodes[-1]
            status = latest.get("render_status", "")
            is_draft = "DRAFT" in status
            is_verified = "AI Verified" in status
            is_goal = "TIER-0" in status or "GOAL" in status

            if is_goal:
                badge = "⚽ TIER-0 LIVE GOAL OVERLAY"
            elif is_verified:
                badge = "🟢 FINAL (AI VERIFIED)"
            elif is_draft:
                badge = "🟠 DRAFT (LIVE GABARIT INSTANTANÉ)"
            else:
                badge = f"⚪ {status}"

            st.subheader(f"{badge} — Minute {latest.get('match_minute')}'")
            st.caption(
                f"Épisode : `{latest.get('episode_id')}` | Modèle : `{latest.get('model_used', 'Deterministic Template')}` | "
                f"Langue : `{latest.get('language_used', 'English')}`"
            )

            stats = latest.get("stats_snapshot", {})
            if stats and "pass_acc" in stats:
                c1, c2, c3 = st.columns(3)
                if stats.get("pass_acc") is not None:
                    c1.metric("Précision passes victime", f"{int(round(stats['pass_acc'] * 100))}%")
                c2.metric("Actions défensives", stats.get("def_actions", 0))
                c3.metric("Preuves citées", ", ".join(latest.get("cited_event_ids", [])) or "N/A")

            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**🔬 Vue Analyste (Technique)**\n\n{latest.get('analyst_view', 'N/A')}")
            with col2:
                st.success(f"**🔥 Vue Supporter (Émotion)**\n\n{latest.get('fan_view', 'N/A')}")

            if latest.get("llm_latency_sec") is not None:
                st.caption(f"⚡ Inférence et validation en **{latest['llm_latency_sec']}s**")

            if recap:
                st.markdown("---")
                st.success(f"### 🏆 Bilan Fin de Match (Track 3 — RecapAgent)\n**{recap.get('headline')}**\n\n{recap.get('tactical_summary')}")

            st.markdown("### 📋 Fil chronologique des épisodes")
            for item in reversed(episodes[:-1]):
                with st.expander(f"{item.get('render_status')} — Min {item.get('match_minute')}' ({item.get('episode_id')})"):
                    st.write(f"**Analyste :** {item.get('analyst_view')}")
                    st.write(f"**Fan :** {item.get('fan_view')}")
                    st.caption(f"Preuves : `{item.get('cited_event_ids', [])}` | Latence : `{item.get('llm_latency_sec', 0)}s`")

    time.sleep(0.5)
