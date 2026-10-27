with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# Déplacer le recap pour qu'il soit injecté AVANT target_ep (au-dessus de l'Explorer)
anchor = "        if target_ep:\n            cutoff_m = display_min if display_min > 0 else 90"

recap_top_logic = """        if recap:
            r_head = html.escape(strip_non_ascii_symbols(recap.get("headline", "")))
            r_sum = html.escape(strip_non_ascii_symbols(recap.get("tactical_summary", "")))
            r_fact, r_color = split_fact_and_color(r_sum)
            r_chips = "".join(f'<span class="bc-chip">{html.escape(k)}</span>' for k in recap.get("key_episode_ids", []))
            r_ver = "AI VERIFIED (RECAP AGENT)" if recap.get("recap_verified") else "DETERMINISTIC FALLBACK (NO LLM)"
            recap_html = compact_html(f\"\"\"
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
            \"\"\")
            sections_html.append(recap_html)

        if target_ep:
            cutoff_m = display_min if display_min > 0 else 90"""

# Nettoyer l'ancien emplacement en bas
old_bottom_recap = """        if recap:
            r_head = html.escape(strip_non_ascii_symbols(recap.get("headline", "")))
            r_sum = html.escape(strip_non_ascii_symbols(recap.get("tactical_summary", "")))
            r_fact, r_color = split_fact_and_color(r_sum)
            r_chips = "".join(f'<span class="bc-chip">{html.escape(k)}</span>' for k in recap.get("key_episode_ids", []))
            r_ver = "AI VERIFIED (RECAP AGENT)" if recap.get("recap_verified") else "DETERMINISTIC FALLBACK (NO LLM)"
            recap_html = compact_html(f\"\"\"
            <div class="bc-card" style="border-color:#0078D4; background:linear-gradient(135deg, rgba(0,120,212,0.14) 0%, #141B24 70%); margin-top:20px;">
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
            \"\"\")
            sections_html.append(recap_html)"""

if old_bottom_recap in code:
    code = code.replace(old_bottom_recap, "")
if anchor in code:
    code = code.replace(anchor, recap_top_logic)
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("✅ Option B appliquée : Le résumé Post-Match est affiché TOUT EN HAUT au-dessus de l'Explorer.")
