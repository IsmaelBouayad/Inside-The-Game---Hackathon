import py_compile
import re

# ==============================================================================
# 1. PIPELINE.PY : Parseur tolérant + Extracteur Regex anti-JSONDecodeError
# ==============================================================================
with open("pipeline.py", "r", encoding="utf-8") as f:
    p_code = f.read()

robust_coerce_color = '''def coerce_color_payload(raw_text: str, trigger_ids: list, alarm: dict) -> ColorCommentaryPayload:
    """Robust JSON parser with regex recovery to guarantee 0 JSONDecodeError drops."""
    clean_str = extract_json(raw_text)
    data = None
    try:
        data = json.loads(clean_str, strict=False)
    except Exception:
        # Fallback d'extraction par regex si le LLM omet des virgules ou injecte des retours ligne
        ac_m = re.search(r'"(?:analyst_color_en|analyst_color|analyst_view|tactical_color)"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"', raw_text)
        fv_m = re.search(r'"(?:fan_view_en|fan_view|supporter_view)"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"', raw_text)
        ac_fr_m = re.search(r'"(?:analyst_color_fr)"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"', raw_text)
        fv_fr_m = re.search(r'"(?:fan_view_fr)"\\s*:\\s*"([^"\\\\]*(?:\\\\.[^"\\\\]*)*)"', raw_text)
        if ac_m and fv_m:
            data = {
                "analyst_color_en": ac_m.group(1),
                "fan_view_en": fv_m.group(1),
                "analyst_color_fr": ac_fr_m.group(1) if ac_fr_m else "",
                "fan_view_fr": fv_fr_m.group(1) if fv_fr_m else "",
                "cited_event_ids": trigger_ids[:2]
            }
        else:
            # Fallback textuel sécurisé respectant la polarité
            status = alarm.get("status", "ENTERED")
            if status == "ENTERED":
                c_en = "The compact pressing unit closes central passing lanes and forces hurried clearances."
                f_en = "Relentless pressure applied across the attacking third!"
                c_fr = "Le bloc compact ferme les lignes de passe axiales et contraint à des dégagements d'urgence."
                f_fr = "Pression totale sur la relance adverse !"
            else:
                c_en = "The pressing block drops off into mid-recovery, allowing structured distribution from the back."
                f_en = "Pressure subsides as the defense regains its composure!"
                c_fr = "Le rideau défensif recule et permet de réorganiser sereinement la relance courte."
                f_fr = "Le danger s'éloigne, la relance retrouve enfin son calme !"
            data = {
                "analyst_color_en": c_en,
                "fan_view_en": f_en,
                "analyst_color_fr": c_fr,
                "fan_view_fr": f_fr,
                "cited_event_ids": trigger_ids[:2]
            }

    status = alarm.get("status", "ENTERED")
    team = alarm.get("team", "Team")
    victim = alarm.get("victim", "Opponent")

    analyst_en = data.get("analyst_color_en") or data.get("analyst_color") or data.get("analyst_view")
    fan_en = data.get("fan_view_en") or data.get("fan_view")
    analyst_fr = data.get("analyst_color_fr")
    fan_fr = data.get("fan_view_fr")

    if not analyst_fr:
        analyst_fr = "Le bloc resserre les lignes médianes." if status == "ENTERED" else "Le rideau défensif recule et stabilise le jeu."
    if not fan_fr:
        fan_fr = f"Pressing étouffant de {team} !" if status == "ENTERED" else f"La relance de {victim} retrouve son calme !"

    raw_ids = data.get("cited_event_ids") or data.get("event_ids")
    if isinstance(raw_ids, str):
        c_ids = [raw_ids]
    elif isinstance(raw_ids, list) and len(raw_ids) > 0:
        c_ids = [str(x) for x in raw_ids]
    else:
        c_ids = [trigger_ids[0]] if trigger_ids else ["EVT-01"]

    return ColorCommentaryPayload(
        analyst_color_en=str(analyst_en or "").strip(),
        fan_view_en=str(fan_en or "").strip(),
        analyst_color_fr=str(analyst_fr).strip(),
        fan_view_fr=str(fan_fr).strip(),
        cited_event_ids=c_ids
    )'''

# Remplacement de coerce_color_payload dans pipeline.py
p_pattern = r"def coerce_color_payload\(raw_text: str, trigger_ids: list, alarm: dict\) -> ColorCommentaryPayload:[\s\S]*?(?=def coerce_recap_payload)"
p_code = re.sub(p_pattern, robust_coerce_color + "\n\n", p_code)

with open("pipeline.py", "w", encoding="utf-8") as f:
    f.write(p_code)
py_compile.compile("pipeline.py", doraise=True)
print("✅ 1/3 pipeline.py : Parseur résilient regex intégré et compilé.")

# ==============================================================================
# 2. ENGINE.PY : Pause de 3.5s protégée contre les écrasements dans la boucle
# ==============================================================================
with open("engine.py", "r", encoding="utf-8") as f:
    e_code = f.read()

# Remplacer la boucle de traitement d'événement dans match_engine
e_loop_pattern = r"(for event in events:[\s\S]*?if alarm:[\s\S]*?queue\.put_nowait\(\(seq_id, alarm, list\(detector\.buffer\)\)\))"

clean_engine_loop = '''for event in events:
            now_clock = event_clock_sec(event)
            dt = max(0, now_clock - prev_clock)
            prev_clock = now_clock

            is_slow = dynamic_pacing and (state_tracker["worker_busy"] or not queue.empty())
            active_speed = min(speed, tactical_speed) if is_slow else speed

            if dt > 0 and active_speed > 0:
                await asyncio.sleep(dt / active_speed)

            metrics.events += 1
            state_tracker["current_minute"] = event["minute"]

            # 1. ÉVÉNEMENT BUT TIER-0
            if event.get("event_type") == "Shot" and event.get("outcome") == "Goal":
                scorer = event["team"]
                player_name = event.get("player_id", "Player")
                score[scorer] = score.get(scorer, 0) + 1
                metrics.goals += 1
                state_tracker["latest_seq"] += 1
                goal_ov = generate_goal_overlay(event, score, match_id, language=BROADCAST_LANG)
                goal_ov["episode_seq"] = state_tracker["latest_seq"]
                append_to_ui(goal_ov)
                verified_overlays.append(goal_ov)
                schedule_fabric_send("GOAL_TIER0", goal_ov)
                metrics.dump(fabric)
                print(f"\\n⚽ [TIER-0 GOAL] Minute {event['minute']} — {player_name} ({scorer}) Score: {score}")

                # Pause franche de 3.5s visible dans Streamlit avec horloge arrêtée
                g_alert = {"scorer": scorer, "player": player_name, "minute": event["minute"], "score": dict(score)}
                state_tracker["active_goal_alert"] = g_alert
                update_clock(
                    event["minute"], score, "GOAL CELEBRATION (PAUSED)", 0.0,
                    detector.momentum_history, detector.peak_swing, goal_alert=g_alert
                )
                await asyncio.sleep(3.5)
                last_printed_min = event["minute"]

            # 2. ALARME DU DÉTECTEUR TACTIQUE
            alarm = detector.process_event(event)

            # 3. MISE À JOUR DE L'HORLOGE RÉGULIÈRE (sans écraser un but récent)
            if event["minute"] != last_printed_min:
                last_printed_min = event["minute"]
                g_alert_keep = state_tracker.get("active_goal_alert")
                if g_alert_keep and (event["minute"] - g_alert_keep["minute"]) > 2:
                    g_alert_keep = None
                    state_tracker["active_goal_alert"] = None
                update_clock(
                    event["minute"], score, detector.state, active_speed,
                    detector.momentum_history, detector.peak_swing, goal_alert=g_alert_keep
                )
                metrics.dump(fabric)

            if alarm:
                metrics.alarms += 1
                state_tracker["latest_seq"] += 1
                seq_id = state_tracker["latest_seq"]
                alarm["episode_seq"] = seq_id
                alarm["timestamp"] = event.get("timestamp", "")

                ep_key = f"{match_id}_min{alarm['minute']}_{alarm.get('status', 'ENTERED')}"
                reason_str = f" [reason={alarm.get('exit_reason')}]" if alarm.get("exit_reason") else ""
                print(f"\\n🚨 [DÉTECTEUR] {alarm['status']}{reason_str} minute {alarm['minute']} ({alarm['team']} vs {alarm['victim']})")

                draft = template_overlay(alarm, ep_key, seq_id, "DRAFT (Live)")
                append_to_ui(draft)
                schedule_fabric_send("ALARM", alarm)
                metrics.dump(fabric)

                if queue.full():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                        metrics.dropped += 1
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait((seq_id, alarm, list(detector.buffer)))'''

e_code = re.sub(e_loop_pattern, clean_engine_loop, e_code)

with open("engine.py", "w", encoding="utf-8") as f:
    f.write(e_code)
py_compile.compile("engine.py", doraise=True)
print("✅ 2/3 engine.py : Pause de 3.5s protégée et horloge synchronisée.")

# ==============================================================================
# 3. APP.PY : Ordre d'affichage exact (Bannière But -> Recap tout en haut -> Momentum -> Overlays)
# ==============================================================================
with open("app.py", "r", encoding="utf-8") as f:
    a_code = f.read()

# Remplacement de l'assemblage complet de sections_html dans app.py
render_sections_pattern = r"(sections_html = \[\][\s\S]*?main_placeholder\.markdown\(\"\\n\"\.join\(sections_html\), unsafe_allow_html=True\))"

clean_sections_assembly = '''sections_html = []

        g_alert = clock.get("goal_alert")
        is_goal_regime = "GOAL" in regime.upper() or bool(g_alert)
        clock_color = "#3FB950" if is_goal_regime else "#58A6FF"
        clock_text = f"{display_min:02d}:00 ⏸" if ("PAUSED" in regime.upper() or is_goal_regime) else f"{display_min:02d}:00"

        header_html = compact_html(f"""
        <div class="bc-header" style="{'border: 2px solid #3FB950; box-shadow: 0 0 30px rgba(46, 160, 67, 0.45);' if is_goal_regime else ''}">
            <div class="bc-brand">
                <div class="bc-brand-top">
                    <span class="bc-live-pill"><span class="bc-live-dot"></span>LIVE</span>
                    <span class="bc-title">INSIDE THE GAME — BROADCAST CONTROL ROOM</span>
                </div>
                <div class="bc-subtitle">MICROSOFT AGENT FRAMEWORK &bull; VERIFIER V5.3 &bull; MICROSOFT FABRIC EVENTSTREAM</div>
            </div>
            <div class="bc-scoreboard">
                <div class="bc-score-box" style="{'border-color:#3FB950; background:rgba(46,160,67,0.18);' if is_goal_regime else ''}">
                    <span class="bc-club-code">MET</span>
                    <span class="bc-score-digits">{score.get('Meteor City', 0)} &mdash; {score.get('Nova FC', 0)}</span>
                    <span class="bc-club-code">NOV</span>
                </div>
                <div class="bc-clock-box">
                    <div class="bc-clock-digits" style="color:{clock_color};">{clock_text}</div>
                    <div class="bc-clock-meta" style="{'color:#3FB950; font-weight:700;' if is_goal_regime else ''}">REGIME: {html.escape(regime.upper())} &bull; PACE X{speed}</div>
                </div>
            </div>
        </div>
        """)
        sections_html.append(header_html)

        # 1. BANNIÈRE ANIMÉE DE BUT (VISIBLE LORS D'UN BUT)
        if is_goal_regime:
            sc_team = html.escape(str(g_alert.get("scorer", "Meteor City"))) if g_alert else "Meteor City"
            sc_ply = html.escape(str(g_alert.get("player", "Scorer"))) if g_alert else "Scorer"
            sc_min = g_alert.get("minute", display_min) if g_alert else display_min
            goal_banner_html = compact_html(f"""
            <div class="bc-goal-hero-banner">
                <div style="display:flex; align-items:center; gap:14px;">
                    <span style="font-size:26px;">⚽</span>
                    <div>
                        <div style="font-size:17px; font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">
                            BUT POUR {sc_team} ({sc_ply}) &mdash; MINUTE {sc_min}' !
                        </div>
                        <div style="font-size:11px; font-family:'JetBrains Mono',monospace; opacity:0.92; margin-top:2px;">
                            TIER-0 BROADCAST OVERLAY &bull; REPLAY ANTENNE EN COURS
                        </div>
                    </div>
                </div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:24px; font-weight:800; background:#0B0F14; padding:6px 18px; border-radius:8px; border:2px solid #56D364;">
                    MET {score.get('Meteor City', 0)} &ndash; {score.get('Nova FC', 0)} NOV
                </div>
            </div>
            """)
            sections_html.append(goal_banner_html)

        # 2. POST-MATCH SMART SUMMARY (TOUT EN HAUT DÈS 90:00)
        if recap:
            r_head = html.escape(strip_non_ascii_symbols(recap.get("headline", "")))
            r_sum = html.escape(strip_non_ascii_symbols(recap.get("tactical_summary", "")))
            r_fact, r_color = split_fact_and_color(r_sum)
            r_chips = "".join(f'<span class="bc-chip">{html.escape(k)}</span>' for k in recap.get("key_episode_ids", []))
            r_ver = "AI VERIFIED (RECAP AGENT)" if recap.get("recap_verified") else "DETERMINISTIC FALLBACK (NO LLM)"
            recap_html = compact_html(f"""
            <div class="bc-card" style="border: 2px solid #0078D4; box-shadow: 0 0 30px rgba(0, 120, 212, 0.35); background:linear-gradient(135deg, rgba(0,120,212,0.22) 0%, #141B24 70%); margin-bottom:16px;">
                <div class="bc-card-header">
                    <span class="bc-badge badge-tier0"><span class="bc-dot"></span>POST-MATCH SMART SUMMARY (RECAP AGENT HANDOFF)</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; color:#3FB950;">{r_ver}</span>
                </div>
                <div style="font-size:17px; font-weight:700; color:#E6EDF3; margin-bottom:6px;">{r_head}</div>
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

        # 3. GRAPHIQUE LIVE MOMENTUM
        mom_svg = build_momentum_svg(clock.get("momentum_history", []), episodes, peak)
        if mom_svg:
            sections_html.append(mom_svg)

        # 4. PANNEAU TACTICAL IMPACT EXPLORER
        if target_ep:
            cutoff_m = display_min if display_min > 0 else 90
            ep_insight = insight_builder.build_episode_insight(target_ep, all_raw_events, current_minute=cutoff_m, score=score)
            sections_html.append(render_tactical_impact_explorer_html(ep_insight))

        # 5. FLUX DES CARTES D'OVERLAYS
        if not episodes:
            sections_html.append(
                '<div class="bc-card" style="color:#8B949E; font-size:13px;">Stream ready. Run <code>python3 engine.py --start-minute 48</code> to watch live tactical detection and AI verification...</div>'
            )
        else:
            sections_html.append(
                '<div style="font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.08em; color:#8B949E; margin-bottom:8px;">ACTIVE BROADCAST OVERLAYS (LATEST ON TOP)</div>'
            )
            for ep in reversed(episodes):
                if "FULL_TIME" in ep.get("episode_id", ""):
                    continue
                sections_html.append(render_episode_card_html(ep, selected_club))

        main_placeholder.markdown("\\n".join(sections_html), unsafe_allow_html=True)'''

a_code = re.sub(render_sections_pattern, clean_sections_assembly, a_code)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(a_code)
py_compile.compile("app.py", doraise=True)
print("✅ 3/3 app.py : Bannière de but + Recap positionné tout en haut compilés sans erreur.")
