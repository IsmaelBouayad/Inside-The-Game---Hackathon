# Automated Hackathon Judge — End-to-End Execution Report

- **Execution Timestamp (UTC):** `2026-10-22T12:38:49Z`
- **Git Commit (HEAD) & Seed:** `30f7231` | `Seed 42 (min 48..90)`
- **Total Audit Duration:** `76.74s`
- **Overall Verification Score:** **`9 / 10 Checks Passed (90%)`**

## 1. End-to-End Verification Matrix

| Category | Verification Check | Status | Empirical Evidence |
| :--- | :--- | :---: | :--- |
| 1. Technical Implementation | Verifier v5.2 & Regression Unit Suite (21 tests) | **PASS** | 21/21 unit & regression tests passed |
| 1. Technical Implementation | Git Index Hygiene & Regex Secret Content Scan | **PASS** | 0 scratch files & 0 credential patterns across all 27 tracked files |
| 2. Data & Detector | Seed 42 Ground Truth & Realism | **PASS** | Pass Acc: 89.7%, Score: {'Meteor City': 2, 'Nova FC': 0}, True Press Window: min 52..64 |
| 2. Data & Detector | Control Match Silence Across All Control Seeds in 1..30 | **PASS** | 0 false alarms across all 10 control seeds ([2, 4, 9, 12, 16, 20, 22, 24, 25, 28]) |
| 2. Data & Detector | Independent Outcome Generalization (Both Nova FC Win AND Draw Verified) | **PASS** | Nova FC win verified on seeds [1, 6, 9]; Draw verified on seeds [3, 5, 7] |
| 3. Live Agentic Pipeline | In-Place DRAFT -> FINAL (AI Verified) Upgrade on All Tactical Alarms | **FAIL** | Upgraded episodes: ['m_42_min62_EXITED'] (llm_verified=2/2, median_latency=9.48s) |
| 3. Live Agentic Pipeline | Strict ISO-8601 Timestamp Validity (including minute >= 60) | **PASS** | All 9 emitted overlay lines have valid ISO-8601 timestamps |
| 4. UX & Multi-Audience | Uncontaminated Bilingual Split-Screen (EN & FR Verified in Both Modes) | **PASS** | EN feed starts with 'At minute 57' and FR feed starts with 'À la 57e minute' without cross-contamination |
| 4. UX & Multi-Audience | Verified RecapAgent Handoff & Causal Detection Wording | **PASS** | recap_verified=True, causal wording verified ('first confirmed by the causal detector at minute 57') |
| 5. Enterprise & Fabric | Director Hold/Approve State Transitions & Fabric Delivery Accounting | **PASS** | Director states verified ('🛑 HELD BY DIRECTOR (Withdrawn from Air)' -> '📡 ON-AIR (Director Approved)') | Fabric live_sends=7, local_fallbacks=0 |

## 2. Live Engine Metrics (`engine_metrics.json`)
```json
{
  "events": 856,
  "alarms": 2,
  "goals_narrated_tier0": 2,
  "dropped_jobs": 0,
  "llm_verified": 2,
  "fallback_after_rejection": 0,
  "timeouts": 0,
  "errors": 0,
  "superseded_finals": 0,
  "fabric_delivery_mode": "fabric_eventstream_live",
  "fabric_live_sends_succeeded": 7,
  "fabric_local_fallbacks": 0,
  "llm_latency_sec_median": 9.48,
  "llm_latency_sec_max": 9.55,
  "last_updated_utc": "2026-10-22T12:38:27Z"
}
```

## 3. Live Verified Broadcast Overlays (`broadcast_ui.jsonl` Merged State)
```json
{
  "m_42_min57_ENTERED": {
    "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. Meteor City's midfield pack is congesting the centre, making it difficult for Nova FC to establish a rhythm.",
    "fan_view": "What a high-potential attack from Nova FC is being repelled!",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. Meteor City's midfield pack is congesting the centre, making it difficult for Nova FC to establish a rhythm.",
        "fan_view": "What a high-potential attack from Nova FC is being repelled!"
      },
      "fr": {
        "analyst_view": "À la 57e minute, Meteor City enclenche un pressing haut avec 8 actions défensives dans le tiers défensif de Nova FC, réduisant la précision de relance adverse à 50%. Le bloc collectif resserre les lignes et verrouille la relance courte.",
        "fan_view": "Quel pressing étouffant de Meteor City ! La relance adverse est bloquée ! 🔥"
      },
      "club_voices": {
        "Meteor City": "💙 Meteor City imposes total territorial control!",
        "Nova FC": "⚠️ Nova FC under heavy pressure in their own third!"
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1144"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "exit_reason": null,
    "model_used": "llama3.2",
    "timestamp": "2026-10-27T15:57:00Z",
    "match_minute": 57,
    "episode_id": "m_42_min57_ENTERED",
    "stats_snapshot": {
      "pass_acc": 0.5,
      "def_actions": 8,
      "n_passes": 8
    },
    "rejection_history": [],
    "is_fallback": false,
    "episode_seq": 2,
    "superseded": false,
    "llm_latency_sec": 9.55,
    "completed_at_match_minute": 57,
    "render_status": "FINAL (AI Verified)"
  },
  "m_42_min62_EXITED": {
    "analyst_view": "At minute 62, Meteor City's high press subsides with only 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). The high press is waning as Meteor City's defenders start to sit deeper, allowing Nova FC to dictate terms and regain control.",
    "fan_view": "The tension is palpable, can Nova turn this around?",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 62, Meteor City's high press subsides with only 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). The high press is waning as Meteor City's defenders start to sit deeper, allowing Nova FC to dictate terms and regain control.",
        "fan_view": "The tension is palpable, can Nova turn this around?"
      },
      "fr": {
        "analyst_view": "À la 62e minute, le pressing haut de Meteor City retombe avec seulement 1 action défensive récente, permettant à Nova FC de se réorganiser (précision de passes de 57% sur la période). L'intensité du pressing adverse baisse, permettant de temporiser.",
        "fan_view": "Le pressing de Meteor City s'essouffle, Nova FC reprend le contrôle du ballon ! ⚖️"
      },
      "club_voices": {
        "Meteor City": "💙 Meteor City resets the tempo and organizes the midfield!",
        "Nova FC": "💛 Nova FC stabilizes possession and looks forward!"
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1175"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "exit_reason": "exhausted",
    "model_used": "llama3.2",
    "timestamp": "2026-10-27T16:02:00Z",
    "match_minute": 62,
    "episode_id": "m_42_min62_EXITED",
    "stats_snapshot": {
      "pass_acc": 0.57,
      "def_actions": 1,
      "n_passes": 14
    },
    "rejection_history": [],
    "is_fallback": false,
    "episode_seq": 3,
    "superseded": false,
    "llm_latency_sec": 9.4,
    "completed_at_match_minute": 62,
    "render_status": "📡 ON-AIR (Director Approved)",
    "director_decision": "APPROVED_ON_AIR"
  },
  "m_42_min79_GOAL_EVT-m_42-1613": {
    "analyst_view": "GOAL at minute 79! M-02 (Meteor City) scores. Score is now Meteor City 2 - 0 Nova FC.",
    "fan_view": "GOOOAAAL! Clinical finish by M-02 for Meteor City! ⚽🔥",
    "multiaudience": {
      "en": {
        "analyst_view": "GOAL at minute 79! M-02 (Meteor City) scores. Score is now Meteor City 2 - 0 Nova FC.",
        "fan_view": "GOOOAAAL! Clinical finish by M-02 for Meteor City! ⚽🔥"
      },
      "fr": {
        "analyst_view": "BUT à la 79e minute ! M-02 (Meteor City) marque. Score : Meteor City 2 - 0 Nova FC.",
        "fan_view": "BUUUT ! Finition décisive de M-02 pour Meteor City ! ⚽🔥"
      },
      "club_voices": {
        "Meteor City": "💙 Goal update (2-0): Meteor City strikes at minute 79!",
        "Nova FC": "💛 Score update at minute 79: Meteor City 2 - 0 Nova FC."
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1613"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "timestamp": "2026-10-27T16:21:18Z",
    "match_minute": 79,
    "episode_id": "m_42_min79_GOAL_EVT-m_42-1613",
    "stats_snapshot": {
      "score": {
        "Meteor City": 2,
        "Nova FC": 0
      }
    },
    "render_status": "TIER-0 (Live Goal Event)",
    "is_fallback": false,
    "episode_seq": 4
  }
}
```

## 4. Post-Match RecapAgent Output (`match_recap.json`)
```json
{
  "headline": "Full Time: Meteor City 2 - 0 Nova FC",
  "tactical_summary": "Meteor City secures a 2-0 victory over Nova FC. Observed high-press regime spanned minutes 57 to 62 (first confirmed by the causal detector at minute 57). Aggressive Dominance",
  "turning_point": {
    "minute": 57,
    "episode_id": "m_42_min57_ENTERED"
  },
  "key_episode_ids": [
    "m_42_min51_GOAL_EVT-m_42-1037",
    "m_42_min57_ENTERED"
  ],
  "agent_handoff_count": 4,
  "recap_verified": true
}
```
