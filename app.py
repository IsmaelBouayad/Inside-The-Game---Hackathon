import asyncio
import json
import os
import time
import pandas as pd
import streamlit as st
from fabric_sink import FabricTelemetrySink

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
    record = {
        "episode_id": episode_id,
        "director_decision": decision,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    try:
        sink = FabricTelemetrySink()
        asyncio.run(sink.ingest_record("DIRECTOR_AUDIT", record))
    except Exception:
        pass


def main():
    st.set_page_config(page_title="Inside The Game - Broadcast Control", layout="wide")
    st.title("📺 Inside The Game — Edge AI Broadcast Control Room")
    st.caption("Continuous Momentum Shift Index • Multi-Audience Split-Screen (EN/FR/Club) • Director Approval Audit to Microsoft Fabric")

    st.sidebar.markdown("### 🎛️ Broadcast Director (Human-in-the-Loop)")
    selected_club = st.sidebar.selectbox("Companion App Club Allegiance (Track 4)", ["Meteor City", "Nova FC"])
    col_btn1, col_btn2 = st.sidebar.columns(2)
    if col_btn1.button("✅ Approve On-Air"):
        eps = load_episodes()
        if eps:
            log_director_decision(eps[-1].get("episode_id", "unknown"), "APPROVED_ON_AIR")
            st.sidebar.success(f"Approved & audited to Fabric: {eps[-1].get('episode_id')}")
    if col_btn2.button("🛑 Override / Hold"):
        eps = load_episodes()
        if eps:
            log_director_decision(eps[-1].get("episode_id", "unknown"), "HELD_BY_DIRECTOR")
            st.sidebar.warning(f"Held by Director: {eps[-1].get('episode_id')}")

    st.sidebar.markdown("---")
    sidebar_placeholder = st.sidebar.empty()
    main_placeholder = st.empty()

    while True:
        episodes = load_episodes()
        clock = load_json(CLOCK_FILE)
        metrics = load_json(METRICS_FILE)
        recap = load_json(RECAP_FILE)

        with sidebar_placeholder.container():
            st.markdown("### ⏱️ Live Match Clock & Score")
            if clock:
                score = clock.get("score", {"Meteor City": 0, "Nova FC": 0})
                st.metric("Match Minute", f"{clock.get('minute', 0)}'")
                st.metric("Live Score", f"Meteor {score['Meteor City']} - {score['Nova FC']} Nova")
                st.caption(f"Tactical Regime: **{clock.get('tactical_state', 'Normal')}** | Replay Speed: **x{clock.get('current_speed', 60)}**")
                peak = clock.get("peak_swing")
                if peak and peak.get("minute", 0) > 0:
                    st.info(f"⚡ **Turning Point Detected:** Min {peak['minute']}' ({peak['team']}, swing {peak['delta']:+.1f})")
            else:
                st.info("Waiting for kick-off...")

            st.markdown("---")
            st.markdown("### 📊 Edge Engine Telemetry")
            if metrics:
                st.metric("Events Processed", metrics.get("events", 0))
                st.metric("Tactical Alarms", metrics.get("alarms", 0))
                st.metric("Goals Narrated (Tier-0)", metrics.get("goals_narrated_tier0", 0))
                st.metric("AI Verified Overlays", metrics.get("llm_verified", 0))
                if metrics.get("llm_latency_sec_median"):
                    st.metric("Median LLM Latency", f"{metrics['llm_latency_sec_median']}s")
                st.caption(f"☁️ Fabric Sink: `{metrics.get('fabric_delivery_mode', 'local')}`")

        with main_placeholder.container():
            if clock and clock.get("momentum_history"):
                st.markdown("#### 📈 Live Momentum Shift Index ([-100 Nova FC ⟷ +100 Meteor City])")
                df_mom = pd.DataFrame(clock["momentum_history"])
                if not df_mom.empty and "minute" in df_mom and "momentum_index" in df_mom:
                    st.line_chart(df_mom.set_index("minute")["momentum_index"], height=160)

            if not episodes:
                st.info("⚽ Match in progress... Computing continuous Momentum Index and scanning for tactical shifts.")
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
                    badge = "🟠 DRAFT (INSTANT DETERMINISTIC TEMPLATE)"
                else:
                    badge = f"⚪ {status}"

                exit_tag = f" • Exit Reason: `{latest.get('exit_reason')}`" if latest.get("exit_reason") else ""
                st.subheader(f"{badge} — Minute {latest.get('match_minute')}'{exit_tag}")
                st.caption(
                    f"Episode: `{latest.get('episode_id')}` | Model: `{latest.get('model_used', 'Deterministic Template')}` | "
                    f"Cited Evidence: `{', '.join(latest.get('cited_event_ids', []))}`"
                )

                stats = latest.get("stats_snapshot", {})
                if stats and "pass_acc" in stats:
                    c1, c2, c3 = st.columns(3)
                    if stats.get("pass_acc") is not None:
                        c1.metric("Victim Pass Accuracy", f"{int(round(stats['pass_acc'] * 100))}%")
                    c2.metric("Recent Pressing Actions", stats.get("def_actions", 0))
                    c3.metric("Passes in Window", stats.get("n_passes", 0))

                multi = latest.get("multiaudience", {})
                en_views = multi.get("en", {"analyst_view": latest.get("analyst_view"), "fan_view": latest.get("fan_view")})
                fr_views = multi.get("fr", {"analyst_view": latest.get("analyst_view"), "fan_view": latest.get("fan_view")})
                club_voice = multi.get("club_voices", {}).get(selected_club, latest.get("fan_view"))

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**🇬🇧 Analyst View (EN — Technical)**\n\n{en_views.get('analyst_view', 'N/A')}")
                    st.success(f"**🇬🇧 Global Fan View (EN)**\n\n{en_views.get('fan_view', 'N/A')}")
                with col2:
                    st.info(f"**🇫🇷 Vue Analyste (FR — Localization)**\n\n{fr_views.get('analyst_view', 'N/A')}")
                    st.success(f"**🇫🇷 Vue Supporter (FR)**\n\n{fr_views.get('fan_view', 'N/A')}")
                with col3:
                    st.warning(f"**🏟️ Companion App — {selected_club} Feed**\n\n{club_voice}")
                    if latest.get("llm_latency_sec") is not None:
                        st.caption(f"⚡ Edge CPU + Verifier v5.1 Latency: **{latest['llm_latency_sec']}s**")

                if recap:
                    st.markdown("---")
                    st.success(
                        f"### 🏆 Post-Match Smart Summary & Turning Point (Track 3 — RecapAgent)\n"
                        f"**{recap.get('headline')}**\n\n{recap.get('tactical_summary')}"
                    )

                st.markdown("### 📋 Chronological Broadcast Feed")
                for item in reversed(episodes[:-1]):
                    with st.expander(f"{item.get('render_status')} — Min {item.get('match_minute')}' ({item.get('episode_id')})"):
                        st.write(f"**🇬🇧 Analyst:** {item.get('analyst_view')}")
                        st.write(f"**🇫🇷 Analyste:** {item.get('multiaudience', {}).get('fr', {}).get('analyst_view', '')}")
                        st.caption(f"Evidence: `{item.get('cited_event_ids', [])}` | Latency: `{item.get('llm_latency_sec', 0)}s`")

        time.sleep(0.5)


if __name__ == "__main__":
    main()
