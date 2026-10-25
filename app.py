import asyncio
import html
import json
import os
import re
import time
import streamlit as st
from fabric_sink import FabricTelemetrySink

UI_FILE = "broadcast_ui.jsonl"
CLOCK_FILE = "match_clock.json"
METRICS_FILE = "engine_metrics.json"
RECAP_FILE = "match_recap.json"
AUDIT_FILE = "director_audit.jsonl"


def compact_html(raw: str) -> str:
    """Strips leading whitespace on every line so Markdown never treats HTML as a 4-space code block."""
    return "\n".join(line.strip() for line in raw.splitlines() if line.strip())


BROADCAST_CSS = compact_html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap');

:root {
    --bg-main: #0B0F14;
    --bg-surface: #141B24;
    --bg-elevated: #1A2330;
    --text-primary: #E6EDF3;
    --text-muted: #8B949E;
    --border-color: #1F2A37;
    --green-onair: #2EA043;
    --red-hold: #DA3633;
    --amber-draft: #D29922;
    --blue-ms: #0078D4;
}

.stApp {
    background-color: var(--bg-main);
    color: var(--text-primary);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}

header[data-testid="stHeader"] {
    background: transparent !important;
    height: 1.5rem !important;
}

.block-container {
    padding-top: 1rem !important;
    padding-bottom: 2rem !important;
    max-width: 1440px !important;
}

section[data-testid="stSidebar"] {
    background-color: #0E141B !important;
    border-right: 1px solid var(--border-color) !important;
}

@keyframes pulse-dot {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.35; transform: scale(0.92); }
}

.bc-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 14px 22px;
    margin-bottom: 16px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
}

.bc-brand {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.bc-brand-top {
    display: flex;
    align-items: center;
    gap: 10px;
}

.bc-live-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(218, 54, 51, 0.16);
    border: 1px solid rgba(218, 54, 51, 0.45);
    color: #FF7B72;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 3px 9px;
    border-radius: 4px;
    text-transform: uppercase;
}

.bc-live-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--red-hold);
    animation: pulse-dot 1.4s infinite ease-in-out;
}

.bc-title {
    font-size: 17px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
}

.bc-subtitle {
    font-size: 11px;
    color: var(--text-muted);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.bc-scoreboard {
    display: flex;
    align-items: center;
    gap: 24px;
}

.bc-score-box {
    display: flex;
    align-items: center;
    gap: 14px;
    background: #0B0F14;
    border: 1px solid var(--border-color);
    padding: 8px 18px;
    border-radius: 8px;
}

.bc-club-code {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}

.bc-score-digits {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 34px;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
}

.bc-clock-box {
    text-align: right;
}

.bc-clock-digits {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 34px;
    font-weight: 700;
    color: #58A6FF;
    line-height: 1;
}

.bc-clock-meta {
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-top: 4px;
}

.bc-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 4px 10px;
    border-radius: 5px;
}

.bc-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
}

.badge-final {
    background: rgba(46, 160, 67, 0.16);
    border: 1px solid rgba(46, 160, 67, 0.45);
    color: #3FB950;
}
.badge-final .bc-dot { background: #3FB950; }

.badge-draft {
    background: rgba(210, 153, 34, 0.16);
    border: 1px solid rgba(210, 153, 34, 0.45);
    color: #E3B341;
}
.badge-draft .bc-dot {
    background: #E3B341;
    animation: pulse-dot 1.2s infinite;
}

.badge-held {
    background: rgba(218, 54, 51, 0.16);
    border: 1px solid rgba(218, 54, 51, 0.45);
    color: #FF7B72;
}
.badge-held .bc-dot { background: #FF7B72; }

.badge-tier0 {
    background: rgba(0, 120, 212, 0.18);
    border: 1px solid rgba(0, 120, 212, 0.55);
    color: #58A6FF;
}
.badge-tier0 .bc-dot { background: #58A6FF; }

.bc-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 18px 20px;
    margin-bottom: 16px;
}

.bc-card-goal {
    background: linear-gradient(135deg, rgba(46, 160, 67, 0.12) 0%, #141B24 65%);
    border: 1px solid rgba(46, 160, 67, 0.55);
    box-shadow: 0 0 20px rgba(46, 160, 67, 0.12);
}

.bc-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border-color);
    padding-bottom: 12px;
    margin-bottom: 14px;
}

.bc-card-meta {
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
}

.bc-stat-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 14px;
}

.bc-stat-pill {
    background: #0B0F14;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px 12px;
}

.bc-stat-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}

.bc-stat-val {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin-top: 2px;
}

.bc-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}

.bc-pane {
    background: #0B0F14;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px 14px;
}

.bc-pane-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}

.bc-pane-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}

.bc-lang-tag {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 600;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--bg-elevated);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
}

.bc-fact-text {
    font-size: 13.5px;
    line-height: 1.5;
    color: var(--text-primary);
    font-weight: 500;
}

.bc-color-text {
    font-size: 13.5px;
    line-height: 1.5;
    color: #8B949E;
    font-style: italic;
    margin-left: 4px;
}

.bc-fan-box {
    margin-top: 10px;
    padding-top: 8px;
    border-top: 1px dashed var(--border-color);
    font-size: 12.5px;
    color: #58A6FF;
}

.bc-chip-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 12px;
    flex-wrap: wrap;
}

.bc-chip {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(0, 120, 212, 0.12);
    border: 1px solid rgba(0, 120, 212, 0.35);
    color: #58A6FF;
}

.sb-section-title {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin: 10px 0 8px 0;
}

.sb-preview-box {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 10px;
}

.sb-telemetry-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 8px;
}

.sb-metric-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 8px 10px;
}

.sb-metric-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
}

.sb-metric-num {
    font-family: 'JetBrains Mono', monospace;
    font-variant-numeric: tabular-nums;
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary);
    margin-top: 2px;
}
</style>
""")


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def clear_run_files():
    """Clears all previous run artifacts so the UI starts clean and loads live data progressively."""
    for f_path in (UI_FILE, CLOCK_FILE, METRICS_FILE, RECAP_FILE, AUDIT_FILE):
        if os.path.exists(f_path):
            try:
                os.remove(f_path)
            except Exception:
                pass


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
    eps = load_episodes()
    for ep in eps:
        if ep.get("episode_id") == episode_id:
            updated = dict(ep)
            updated["director_decision"] = decision
            if decision == "HELD_BY_DIRECTOR":
                updated["render_status"] = "🛑 HELD BY DIRECTOR (Withdrawn from Air)"
            else:
                updated["render_status"] = "📡 ON-AIR (Director Approved)"
            with open(UI_FILE, "a", encoding="utf-8") as uf:
                uf.write(json.dumps(updated, ensure_ascii=False) + "\n")
            break
    import threading
    def _send_audit_bg(rec):
        try:
            async def _runner():
                sink = FabricTelemetrySink()
                try:
                    await asyncio.wait_for(sink.ingest_record("DIRECTOR_AUDIT", rec), timeout=4.0)
                finally:
                    await sink.close()
            asyncio.run(_runner())
        except Exception:
            pass
    threading.Thread(target=_send_audit_bg, args=(record,), daemon=True).start()


def split_fact_and_color(text: str) -> tuple[str, str]:
    if not text:
        return "", ""
    parts = text.split(". ", 1)
    if len(parts) == 2:
        return parts[0] + ".", parts[1]
    return text, ""


def strip_non_ascii_symbols(text: str) -> str:
    """Removes decorative emojis and variation selectors for clean broadcast typography."""
    if not text:
        return ""
    return re.sub(r"[\u2600-\u27BF\uFE00-\uFE0F\U0001F000-\U0001FAFF]+", "", text).strip()


def status_badge_html(render_status: str, is_fallback: bool = False) -> str:
    s = render_status or ""
    if "HELD BY DIRECTOR" in s:
        return '<span class="bc-badge badge-held"><span class="bc-dot"></span>HELD BY DIRECTOR</span>'
    if "ON-AIR" in s:
        return '<span class="bc-badge badge-final"><span class="bc-dot"></span>ON-AIR APPROVED</span>'
    if "TIER-0" in s or "GOAL" in s:
        return '<span class="bc-badge badge-tier0"><span class="bc-dot"></span>TIER-0 GOAL EVENT</span>'
    if "DRAFT" in s:
        return '<span class="bc-badge badge-draft"><span class="bc-dot"></span>DRAFT GABARIT</span>'
    if "AI Verified" in s and not is_fallback:
        return '<span class="bc-badge badge-final"><span class="bc-dot"></span>FINAL &bull; AI VERIFIED</span>'
    return '<span class="bc-badge badge-draft"><span class="bc-dot"></span>FINAL &bull; TEMPLATE FALLBACK</span>'


def build_momentum_svg(momentum_history: list, episodes: list, peak_swing: dict) -> str:
    if not momentum_history:
        return ""

    w, h = 920, 200
    pad_l, pad_r, pad_t, pad_b = 44, 20, 22, 28
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b
    zero_y = pad_t + plot_h / 2.0

    mins = [pt["minute"] for pt in momentum_history]
    min_m = min(mins)
    raw_max_m = max(mins)
    max_m = 90 if raw_max_m >= 89 else max(raw_max_m, min_m + 1)

    def x_pos(m):
        return pad_l + ((m - min_m) / max(1, (max_m - min_m))) * plot_w

    def y_pos(val):
        clamped = max(-100.0, min(100.0, float(val)))
        return zero_y - (clamped / 100.0) * (plot_h / 2.0)

    pts = [(x_pos(90 if pt["minute"] == 89 and max_m == 90 else pt["minute"]), y_pos(pt["momentum_index"])) for pt in momentum_history]
    poly_line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area_pts = f"{pts[0][0]:.1f},{zero_y:.1f} " + poly_line + f" {pts[-1][0]:.1f},{zero_y:.1f}"

    enter_mins = [ep["match_minute"] for ep in episodes if "ENTERED" in ep.get("episode_id", "")]
    exit_mins = [ep["match_minute"] for ep in episodes if "EXITED" in ep.get("episode_id", "")]
    goal_mins = [ep["match_minute"] for ep in episodes if "GOAL" in ep.get("episode_id", "")]

    bands_svg = ""
    if enter_mins:
        m_start = enter_mins[0]
        m_end = exit_mins[0] if exit_mins else max_m
        if m_end >= min_m:
            bx1 = x_pos(max(min_m, m_start))
            bx2 = x_pos(min(max_m, m_end))
            bw = max(4.0, bx2 - bx1)
            bands_svg += (
                f'<rect x="{bx1:.1f}" y="{pad_t}" width="{bw:.1f}" height="{plot_h}" '
                f'fill="rgba(210, 153, 34, 0.13)" stroke="rgba(210, 153, 34, 0.45)" stroke-dasharray="3,3"/>'
                f'<text x="{bx1 + 4:.1f}" y="{pad_t + 12}" fill="#E3B341" font-size="9" font-family="JetBrains Mono">HIGH PRESS ({m_start}\'–{m_end}\')</text>'
            )

    goals_svg = ""
    for gm in goal_mins:
        if min_m <= gm <= max_m:
            gx = x_pos(gm)
            goals_svg += (
                f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t + plot_h}" stroke="#2EA043" stroke-width="1.5"/>'
                f'<circle cx="{gx:.1f}" cy="{pad_t + 8}" r="4" fill="#2EA043"/>'
                f'<text x="{gx + 6:.1f}" y="{pad_t + 11}" fill="#3FB950" font-size="9" font-weight="600" font-family="JetBrains Mono">GOAL {gm}\'</text>'
            )

    tp_min = enter_mins[0] if enter_mins else (peak_swing.get("minute") if peak_swing else None)
    peak_svg = ""
    if tp_min and min_m <= tp_min <= max_m:
        px = x_pos(tp_min)
        match_pts = [pt["momentum_index"] for pt in momentum_history if pt["minute"] == tp_min]
        py = y_pos(match_pts[0] if match_pts else 0.0)
        peak_svg = (
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="#0078D4" stroke="#E6EDF3" stroke-width="1.5"/>'
            f'<text x="{px + 6:.1f}" y="{max(pad_t + 22, py - 5):.1f}" fill="#58A6FF" font-size="9" font-family="JetBrains Mono">TURNING POINT {tp_min}\'</text>'
        )

    return compact_html(f"""
    <div class="bc-card" style="padding: 14px 18px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <span style="font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.08em; color:#8B949E;">
                LIVE MOMENTUM SHIFT INDEX (TERRITORIAL &amp; PRESSING DOMINANCE)
            </span>
            <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#8B949E;">
                +100 METEOR CITY &nbsp;|&nbsp; 0 NEUTRAL &nbsp;|&nbsp; -100 NOVA FC
            </span>
        </div>
        <svg viewBox="0 0 {w} {h}" width="100%" height="185" style="display:block;">
            <defs>
                <linearGradient id="momGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stop-color="#2EA043" stop-opacity="0.38"/>
                    <stop offset="50%" stop-color="#0078D4" stop-opacity="0.05"/>
                    <stop offset="100%" stop-color="#DA3633" stop-opacity="0.38"/>
                </linearGradient>
            </defs>
            <line x1="{pad_l}" y1="{pad_t}" x2="{w - pad_r}" y2="{pad_t}" stroke="#1F2A37" stroke-width="1"/>
            <line x1="{pad_l}" y1="{zero_y:.1f}" x2="{w - pad_r}" y2="{zero_y:.1f}" stroke="#8B949E" stroke-width="1" stroke-dasharray="4,4"/>
            <line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{w - pad_r}" y2="{pad_t + plot_h}" stroke="#1F2A37" stroke-width="1"/>
            <text x="6" y="{pad_t + 4}" fill="#3FB950" font-size="9" font-family="JetBrains Mono">+100</text>
            <text x="18" y="{zero_y + 3:.1f}" fill="#8B949E" font-size="9" font-family="JetBrains Mono">0</text>
            <text x="6" y="{pad_t + plot_h}" fill="#FF7B72" font-size="9" font-family="JetBrains Mono">-100</text>
            {bands_svg}
            <polygon points="{area_pts}" fill="url(#momGrad)"/>
            <polyline fill="none" stroke="#58A6FF" stroke-width="2.2" points="{poly_line}"/>
            {goals_svg}
            {peak_svg}
            <text x="{pad_l}" y="{h - 6}" fill="#8B949E" font-size="9" font-family="JetBrains Mono">MIN {min_m}'</text>
            <text x="{w - pad_r - 42}" y="{h - 6}" fill="#8B949E" font-size="9" font-family="JetBrains Mono">MIN {max_m}'</text>
        </svg>
    </div>
    """)


def render_episode_card_html(ep: dict, selected_club: str) -> str:
    status = ep.get("render_status", "")
    is_goal = "TIER-0" in status or "GOAL" in status
    is_fallback = bool(ep.get("is_fallback"))
    badge = status_badge_html(status, is_fallback=is_fallback)
    minute = ep.get("match_minute", 0)
    ep_id = html.escape(ep.get("episode_id", ""))
    model_name = html.escape(ep.get("model_used", "Deterministic Rule"))
    latency = ep.get("llm_latency_sec")
    lat_str = f"{latency:.2f}s" if isinstance(latency, (int, float)) else "0.00s"
    exit_reason = ep.get("exit_reason")
    exit_pill = f'<span>EXIT: {html.escape(exit_reason.upper())}</span>' if exit_reason else ""

    multi = ep.get("multiaudience", {})
    en_views = multi.get("en", {"analyst_view": ep.get("analyst_view", ""), "fan_view": ep.get("fan_view", "")})
    fr_views = multi.get("fr", {"analyst_view": ep.get("analyst_view", ""), "fan_view": ep.get("fan_view", "")})
    club_voice = strip_non_ascii_symbols(multi.get("club_voices", {}).get(selected_club, ep.get("fan_view", "")))

    en_fact, en_color = split_fact_and_color(strip_non_ascii_symbols(en_views.get("analyst_view", "")))
    fr_fact, fr_color = split_fact_and_color(strip_non_ascii_symbols(fr_views.get("analyst_view", "")))
    en_fan = html.escape(strip_non_ascii_symbols(en_views.get("fan_view", "")))
    fr_fan = html.escape(strip_non_ascii_symbols(fr_views.get("fan_view", "")))

    stats = ep.get("stats_snapshot", {})
    stats_html = ""
    if stats and "pass_acc" in stats:
        acc_val = f"{int(round(stats['pass_acc'] * 100))}%" if stats.get("pass_acc") is not None else "N/A"
        def_act = stats.get("def_actions", 0)
        n_pass = stats.get("n_passes", 0)
        ver_tag = "AI VERIFIED" if not is_fallback else "TEMPLATE FALLBACK"
        stats_html = f"""
        <div class="bc-stat-strip">
            <div class="bc-stat-pill"><div class="bc-stat-label">Victim Pass Acc</div><div class="bc-stat-val">{acc_val}</div></div>
            <div class="bc-stat-pill"><div class="bc-stat-label">Pressing Actions</div><div class="bc-stat-val">{def_act}</div></div>
            <div class="bc-stat-pill"><div class="bc-stat-label">Window Passes</div><div class="bc-stat-val">{n_pass}</div></div>
            <div class="bc-stat-pill"><div class="bc-stat-label">Verification</div><div class="bc-stat-val" style="font-size:13px; color:#3FB950;">{ver_tag}</div></div>
        </div>
        """

    chips_html = "".join(f'<span class="bc-chip">{html.escape(cid)}</span>' for cid in ep.get("cited_event_ids", []))
    card_cls = "bc-card bc-card-goal" if is_goal else "bc-card"

    return compact_html(f"""
    <div class="{card_cls}">
        <div class="bc-card-header">
            <div style="display:flex; align-items:center; gap:12px;">
                {badge}
                <span style="font-family:'JetBrains Mono',monospace; font-size:15px; font-weight:700; color:#E6EDF3;">MIN {minute:02d}'</span>
                <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#8B949E;">{ep_id}</span>
            </div>
            <div class="bc-card-meta">
                {exit_pill}
                <span>ENGINE: {model_name}</span>
                <span>LATENCY: {lat_str}</span>
            </div>
        </div>
        {stats_html}
        <div class="bc-grid-3">
            <div class="bc-pane">
                <div class="bc-pane-head">
                    <span class="bc-pane-title">Analyst Broadcast</span>
                    <span class="bc-lang-tag">EN</span>
                </div>
                <div>
                    <span class="bc-fact-text">{html.escape(en_fact)}</span>
                    <span class="bc-color-text">{html.escape(en_color)}</span>
                </div>
                <div class="bc-fan-box"><strong>FAN EN:</strong> {en_fan}</div>
            </div>
            <div class="bc-pane">
                <div class="bc-pane-head">
                    <span class="bc-pane-title">Analyste Antenne</span>
                    <span class="bc-lang-tag">FR</span>
                </div>
                <div>
                    <span class="bc-fact-text">{html.escape(fr_fact)}</span>
                    <span class="bc-color-text">{html.escape(fr_color)}</span>
                </div>
                <div class="bc-fan-box"><strong>FAN FR:</strong> {fr_fan}</div>
            </div>
            <div class="bc-pane">
                <div class="bc-pane-head">
                    <span class="bc-pane-title">Companion Feed</span>
                    <span class="bc-lang-tag">{html.escape(selected_club.upper())}</span>
                </div>
                <div class="bc-fact-text">{html.escape(club_voice)}</div>
                <div class="bc-fan-box" style="color:#8B949E;">
                    <strong>ARCHITECTURE:</strong> Bold = Python Fact &nbsp;|&nbsp; <em>Italic = Verified LLM Color</em>
                </div>
            </div>
        </div>
        <div class="bc-chip-row">
            <span style="font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:#8B949E;">CITED TELEMETRY PROOFS:</span>
            {chips_html}
        </div>
    </div>
    """)


def main():
    st.set_page_config(page_title="Inside The Game — Broadcast Control Room", layout="wide")
    st.markdown(BROADCAST_CSS, unsafe_allow_html=True)

    st.sidebar.markdown('<div class="sb-section-title">1. COMPANION ALLEGIANCE</div>', unsafe_allow_html=True)
    selected_club = st.sidebar.radio(
        "Club Filter",
        ["Meteor City", "Nova FC"],
        horizontal=True,
        label_visibility="collapsed"
    )

    st.sidebar.markdown('<div class="sb-section-title">2. DIRECTOR CONSOLE (HUMAN-IN-THE-LOOP)</div>', unsafe_allow_html=True)
    sidebar_preview = st.sidebar.empty()

    col_btn1, col_btn2 = st.sidebar.columns(2)
    if col_btn1.button("✔ APPROVE ON-AIR", use_container_width=True):
        eps = load_episodes()
        tactical_eps = [e for e in eps if "ENTERED" in e.get("episode_id", "") or "EXITED" in e.get("episode_id", "")]
        target = tactical_eps[-1] if tactical_eps else (eps[-1] if eps else None)
        if target:
            log_director_decision(target.get("episode_id", "unknown"), "APPROVED_ON_AIR")
            st.rerun()
    if col_btn2.button("✖ OVERRIDE / HOLD", use_container_width=True):
        eps = load_episodes()
        tactical_eps = [e for e in eps if "ENTERED" in e.get("episode_id", "") or "EXITED" in e.get("episode_id", "")]
        target = tactical_eps[-1] if tactical_eps else (eps[-1] if eps else None)
        if target:
            log_director_decision(target.get("episode_id", "unknown"), "HELD_BY_DIRECTOR")
            st.rerun()

    if st.sidebar.button("⟲ RESET / CLEAR STREAM", use_container_width=True):
        clear_run_files()
        st.rerun()

    st.sidebar.markdown('<div class="sb-section-title">3. EDGE &amp; FABRIC TELEMETRY</div>', unsafe_allow_html=True)
    sidebar_telemetry = st.sidebar.empty()

    main_placeholder = st.empty()

    while True:
        episodes = load_episodes()
        clock = load_json(CLOCK_FILE) or {}
        metrics = load_json(METRICS_FILE) or {}
        recap = load_json(RECAP_FILE)

        raw_min = clock.get("minute", 0)
        display_min = 90 if (raw_min >= 89 and recap is not None) else raw_min
        score = clock.get("score", {"Meteor City": 0, "Nova FC": 0})
        regime = "Full Time" if display_min == 90 else clock.get("tactical_state", "Normal")
        speed = clock.get("current_speed", 60)
        peak = clock.get("peak_swing", {})

        tactical_eps = [e for e in episodes if "ENTERED" in e.get("episode_id", "") or "EXITED" in e.get("episode_id", "")]
        target_ep = tactical_eps[-1] if tactical_eps else (episodes[-1] if episodes else None)

        with sidebar_preview.container():
            if target_ep:
                t_id = html.escape(target_ep.get("episode_id", ""))
                t_txt = html.escape(strip_non_ascii_symbols(target_ep.get("analyst_view", ""))[:130])
                st.markdown(
                    compact_html(f"""
                    <div class="sb-preview-box">
                        <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#58A6FF; margin-bottom:4px;">
                            TARGET: {t_id}
                        </div>
                        <div style="font-size:12px; color:#E6EDF3; line-height:1.4;">{t_txt}...</div>
                    </div>
                    """),
                    unsafe_allow_html=True
                )
            else:
                st.markdown('<div class="sb-preview-box" style="color:#8B949E; font-size:12px;">Stream clean — awaiting live match events...</div>', unsafe_allow_html=True)

        with sidebar_telemetry.container():
            ev_count = metrics.get("events", 0)
            alarms_cnt = metrics.get("alarms", 0)
            ver_cnt = metrics.get("llm_verified", 0)
            goals_cnt = metrics.get("goals_narrated_tier0", 0)
            med_lat = metrics.get("llm_latency_sec_median")
            lat_color = "#3FB950" if (med_lat and med_lat < 10) else ("#E3B341" if (med_lat and med_lat < 20) else "#8B949E")
            lat_disp = f"{med_lat:.2f}s" if med_lat else "—"
            fab_sends = metrics.get("fabric_live_sends_succeeded", 0)
            fab_mode = "LIVE EVENTSTREAM" if metrics.get("fabric_delivery_mode") == "fabric_eventstream_live" else "READY / STANDBY"

            dir_approved_cnt = sum(1 for e in episodes if e.get("director_decision") == "APPROVED_ON_AIR")
            dir_held_cnt = sum(1 for e in episodes if e.get("director_decision") == "HELD_BY_DIRECTOR")
            upd_ts = metrics.get("last_updated_utc", "STANDBY")
            st.markdown(
                compact_html(f"""
                <div class="sb-telemetry-grid">
                    <div class="sb-metric-card"><div class="sb-metric-lbl">Events Streamed</div><div class="sb-metric-num">{ev_count}</div></div>
                    <div class="sb-metric-card"><div class="sb-metric-lbl">Tactical Alarms</div><div class="sb-metric-num">{alarms_cnt}</div></div>
                    <div class="sb-metric-card"><div class="sb-metric-lbl">AI Verified</div><div class="sb-metric-num" style="color:#3FB950;">{ver_cnt} / {alarms_cnt}</div></div>
                    <div class="sb-metric-card"><div class="sb-metric-lbl">Director App / Hold</div><div class="sb-metric-num" style="color:#58A6FF;">{dir_approved_cnt} / <span style="color:#FF7B72;">{dir_held_cnt}</span></div></div>
                    <div class="sb-metric-card"><div class="sb-metric-lbl">Median Latency</div><div class="sb-metric-num" style="color:{lat_color};">{lat_disp}</div></div>
                    <div class="sb-metric-card"><div class="sb-metric-lbl">Fabric Live Sends</div><div class="sb-metric-num" style="color:#58A6FF;">{fab_sends}</div></div>
                </div>
                <div style="margin-top:8px; font-family:'JetBrains Mono',monospace; font-size:10px; color:#8B949E;">
                    SINK: {fab_mode} &bull; UPDATED: {upd_ts[-9:] if len(upd_ts) >= 9 else upd_ts}
                </div>
                """),
                unsafe_allow_html=True
            )

        sections_html = []

        header_html = compact_html(f"""
        <div class="bc-header">
            <div class="bc-brand">
                <div class="bc-brand-top">
                    <span class="bc-live-pill"><span class="bc-live-dot"></span>LIVE</span>
                    <span class="bc-title">INSIDE THE GAME — BROADCAST CONTROL ROOM</span>
                </div>
                <div class="bc-subtitle">MICROSOFT AGENT FRAMEWORK &bull; VERIFIER V5.2 &bull; MICROSOFT FABRIC EVENTSTREAM</div>
            </div>
            <div class="bc-scoreboard">
                <div class="bc-score-box">
                    <span class="bc-club-code">MET</span>
                    <span class="bc-score-digits">{score.get('Meteor City', 0)} &mdash; {score.get('Nova FC', 0)}</span>
                    <span class="bc-club-code">NOV</span>
                </div>
                <div class="bc-clock-box">
                    <div class="bc-clock-digits">{display_min:02d}:00</div>
                    <div class="bc-clock-meta">REGIME: {html.escape(regime.upper())} &bull; PACE X{speed}</div>
                </div>
            </div>
        </div>
        """)
        sections_html.append(header_html)

        mom_svg = build_momentum_svg(clock.get("momentum_history", []), episodes, peak)
        if mom_svg:
            sections_html.append(mom_svg)

        if recap:
            r_head = html.escape(strip_non_ascii_symbols(recap.get("headline", "")))
            r_sum = html.escape(strip_non_ascii_symbols(recap.get("tactical_summary", "")))
            r_fact, r_color = split_fact_and_color(r_sum)
            r_chips = "".join(f'<span class="bc-chip">{html.escape(k)}</span>' for k in recap.get("key_episode_ids", []))
            r_ver = "AI VERIFIED (RECAP AGENT)" if recap.get("recap_verified") else "DETERMINISTIC FALLBACK (NO LLM)"
            recap_html = compact_html(f"""
            <div class="bc-card" style="border-color:#0078D4; background:linear-gradient(135deg, rgba(0,120,212,0.14) 0%, #141B24 70%);">
                <div class="bc-card-header">
                    <span class="bc-badge badge-tier0"><span class="bc-dot"></span>POST-MATCH SMART SUMMARY (RECAP AGENT HANDOFF)</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#3FB950;">{r_ver}</span>
                </div>
                <div style="font-size:16px; font-weight:600; color:#E6EDF3; margin-bottom:6px;">{r_head}</div>
                <div style="margin-bottom:10px;">
                    <span class="bc-fact-text">{r_fact}</span>
                    <span class="bc-color-text">{r_color}</span>
                </div>
                <div class="bc-chip-row">
                    <span style="font-size:10px; text-transform:uppercase; letter-spacing:0.08em; color:#8B949E;">HANDOFF EPISODES:</span>
                    {r_chips}
                </div>
            </div>
            """)
            sections_html.append(recap_html)

        if not episodes:
            sections_html.append(
                '<div class="bc-card" style="color:#8B949E; font-size:13px;">Stream ready. Run <code>python3 engine.py --start-minute 48</code> to watch live tactical detection and AI verification...</div>'
            )
        else:
            sections_html.append(
                '<div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#8B949E; margin-bottom:8px;">ACTIVE BROADCAST OVERLAYS (LATEST ON TOP)</div>'
            )
            for ep in reversed(episodes):
                sections_html.append(render_episode_card_html(ep, selected_club))

        main_placeholder.markdown("\n".join(sections_html), unsafe_allow_html=True)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
