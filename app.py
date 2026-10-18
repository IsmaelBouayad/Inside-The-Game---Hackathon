import streamlit as st
import json
import time
import os
import asyncio
import pandas as pd
from fabric_sink import FabricTelemetrySink

st.set_page_config(page_title="Inside The Game - Broadcast Control", layout="wide")
st.title("📺 Inside The Game — Régie TV Edge AI & Multi-Audience Control")
st.caption("Continuous Momentum Shift Index • Multi-Audience Split-Screen (EN/FR/Club) • Director Approval Audit to Microsoft Fabric")

UI_FILE = "broadcast_ui.jsonl"
CLOCK_FILE = "match_clock.json"
METRICS_FILE = "engine_metrics.json"
RECAP_FILE = "match_recap.json"
AUDIT_FILE = "director_audit.jsonl"


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


def log_director_decision(episode_id: str, decision: str):
    record = {"episode_id": episode_id, "director_decision": decision, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    try:
        sink = FabricTelemetrySink()
        asyncio.run(sink.ingest_record("DIRECTOR_AUDIT", record))
    except Exception:
        pass


# Contrôles Réalisateur dans la barre latérale (Hors de la boucle pour l'interactivité)
st.sidebar.markdown("### 🎛️ Contrôle Réalisateur (Human-in-the-Loop)")
selected_club = st.sidebar.selectbox("Allégeance Second Écran (Track 4)", ["Meteor City", "Nova FC"])
col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("✅ Approve On-Air"):
    eps = load_episodes()
    if eps:
        log_director_decision(eps[-1].get("episode_id", "unknown"), "APPROVED_ON_AIR")
        st.sidebar.success(f"Approuvé & audité dans Fabric : {eps[-1].get('episode_id')}")
if col_btn2.button("🛑 Override / Hold"):
    eps = load_episodes()
    if eps:
        log_director_decision(eps[-1].get("episode_id", "unknown"), "HELD_BY_DIRECTOR")
        st.sidebar.warning(f"Retenu par la régie : {eps[-1].get('episode_id')}")

st.sidebar.markdown("---")
sidebar_placeholder = st.sidebar.empty()
main_placeholder = st.empty()

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
            peak = clock.get("peak_swing")
            if peak and peak.get("minute", 0) > 0:
                st.info(f"⚡ **Turning Point détecté :** Min {peak['minute']}' ({peak['team']}, swing {peak['delta']:+.1f})")
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
            st.caption(f"☁️ Fabric : `{metrics.get('fabric_delivery_mode', 'local')}`")

    with main_placeholder.container():
        # 1. Jauge continue du Momentum Shift Index (Track 2)
        if clock and clock.get("momentum_history"):
            st.markdown("#### 📈 Live Momentum Shift Index ([-100 Nova FC ⟷ +100 Meteor City])")
            df_mom = pd.DataFrame(clock["momentum_history"])
            if not df_mom.empty and "minute" in df_mom and "momentum_index" in df_mom:
                st.line_chart(df_mom.set_index("minute")["momentum_index"], height=160)

        if not episodes:
            st.info("⚽ Match en cours... Calcul de l'indice de momentum et surveillance tactique active.")
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

            exit_tag = f" • Exit Reason: `{latest.get('exit_reason')}`" if latest.get("exit_reason") else ""
            st.subheader(f"{badge} — Minute {latest.get('match_minute')}'{exit_tag}")
            st.caption(
                f"Épisode : `{latest.get('episode_id')}` | Modèle : `{latest.get('model_used', 'Deterministic Template')}` | "
                f"Preuves : `{', '.join(latest.get('cited_event_ids', []))}`"
            )

            stats = latest.get("stats_snapshot", {})
            if stats and "pass_acc" in stats:
                c1, c2, c3 = st.columns(3)
                if stats.get("pass_acc") is not None:
                    c1.metric("Précision passes victime", f"{int(round(stats['pass_acc'] * 100))}%")
                c2.metric("Actions défensives récentes", stats.get("def_actions", 0))
                c3.metric("Passes analysées (fenêtre)", stats.get("n_passes", 0))

            # 2. Split-Screen Multi-Audience (Track 1 & Track 4 : 1 Fait Vérifié -> Plusieurs Publics)
            multi = latest.get("multiaudience", {})
            en_views = multi.get("en", {"analyst_view": latest.get("analyst_view"), "fan_view": latest.get("fan_view")})
            fr_views = multi.get("fr", {"analyst_view": latest.get("analyst_view"), "fan_view": latest.get("fan_view")})
            club_voice = multi.get("club_voices", {}).get(selected_club, latest.get("fan_view"))

            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**🇬🇧 Analyst View (EN — Technical)**\n\n{en_views.get('analyst_view', 'N/A')}")
                st.success(f"**🇬🇧 Global Fan View (EN)**\n\n{en_views.get('fan_view', 'N/A')}")
            with col2:
                st.info(f"**🇫🇷 Vue Analyste (FR — Technique)**\n\n{fr_views.get('analyst_view', 'N/A')}")
                st.success(f"**🇫🇷 Vue Supporter (FR)**\n\n{fr_views.get('fan_view', 'N/A')}")
            with col3:
                st.warning(f"**🏟️ Companion App — {selected_club} Feed**\n\n{club_voice}")
                if latest.get("llm_latency_sec") is not None:
                    st.caption(f"⚡ Latence Edge CPU + Vérificateur v5.1 : **{latest['llm_latency_sec']}s**")

            if recap:
                st.markdown("---")
                st.success(
                    f"### 🏆 Bilan Fin de Match & Turning Point (Track 3 — RecapAgent)\n"
                    f"**{recap.get('headline')}**\n\n{recap.get('tactical_summary')}"
                )

            st.markdown("### 📋 Fil chronologique des épisodes")
            for item in reversed(episodes[:-1]):
                with st.expander(f"{item.get('render_status')} — Min {item.get('match_minute')}' ({item.get('episode_id')})"):
                    st.write(f"**🇬🇧 Analyst :** {item.get('analyst_view')}")
                    st.write(f"**🇫🇷 Analyste :** {item.get('multiaudience', {}).get('fr', {}).get('analyst_view', '')}")
                    st.caption(f"Preuves : `{item.get('cited_event_ids', [])}` | Latence : `{item.get('llm_latency_sec', 0)}s`")

    time.sleep(0.5)
