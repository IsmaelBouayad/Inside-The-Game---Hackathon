# Automated Hackathon Judge — End-to-End Execution Report

- **Execution Timestamp (UTC):** `2026-10-21T11:05:35Z`
- **Total Audit Duration:** `62.39s`
- **Overall Verification Score:** **`10 / 10 Checks Passed (100%)`**

## 1. End-to-End Verification Matrix

| Category | Verification Check | Status | Empirical Evidence |
| :--- | :--- | :---: | :--- |
| 1. Technical Implementation | Verifier & Regression Unit Suite | **PASS** | All unit & regression tests passed |
| 1. Technical Implementation | Git Repository Hygiene & Secret Protection | **PASS** | 0 leaked/scratch files in git index (21 clean files tracked) |
| 2. Data & Detector | Seed 42 Ground Truth & Realism | **PASS** | Pass Acc: 89.7%, Score: {'Meteor City': 2, 'Nova FC': 0}, Shift: Meteor City (min 52..64) |
| 2. Data & Detector | Control Match Silence (No-Press Seed) | **PASS** | 0 false alarms on control seed |
| 2. Data & Detector | Dynamic Outcome Generalization (Draw / Nova Win) | **PASS** | Recap adapts to Nova FC wins and draws |
| 3. Live Agentic Pipeline | In-Place DRAFT -> FINAL (AI Verified) Upgrade | **PASS** | Upgraded episodes: ['m_42_min57_ENTERED', 'm_42_min62_EXITED'] (llm_verified=2, median_latency=13.36s) |
| 3. Live Agentic Pipeline | Strict ISO-8601 Timestamp Validity (including minute >= 60) | **PASS** | All 6 emitted overlay lines have valid ISO-8601 timestamps |
| 4. UX & Multi-Audience | Simultaneous Split-Screen Payloads (EN / FR / Club Allegiance) | **PASS** | Verified EN, FR, and Club feeds across 2 tactical episodes |
| 4. UX & Multi-Audience | Continuous Momentum Index & Post-Match RecapAgent Handoff | **PASS** | Momentum points: 30 | Recap handoff count: 4 | Verified: True |
| 5. Enterprise & Fabric | Broadcast Director Audit & Microsoft Fabric Delivery | **PASS** | Fabric mode: fabric_eventstream_live | Audited episode: m_42_min62_EXITED |

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
  "llm_latency_sec_median": 13.36,
  "llm_latency_sec_max": 14.33
}
```

## 3. Live Verified Broadcast Overlays (`broadcast_ui.jsonl` Merged State)
```json
{
  "m_42_min51_GOAL_EVT-m_42-1037": {
    "analyst_view": "GOAL at minute 51! M-11 (Meteor City) scores. Score is now Meteor City 1 - 0 Nova FC.",
    "fan_view": "GOOOAAAL! Clinical finish by M-11 for Meteor City! ⚽🔥",
    "multiaudience": {
      "en": {
        "analyst_view": "GOAL at minute 51! M-11 (Meteor City) scores. Score is now Meteor City 1 - 0 Nova FC.",
        "fan_view": "GOOOAAAL! Clinical finish by M-11 for Meteor City! ⚽🔥"
      },
      "fr": {
        "analyst_view": "BUT à la 51e minute ! M-11 (Meteor City) marque. Score : Meteor City 1 - 0 Nova FC.",
        "fan_view": "BUUUT ! Finition décisive de M-11 pour Meteor City ! ⚽🔥"
      },
      "club_voices": {
        "Meteor City": "💙 Goal update (1-0): Meteor City strikes at minute 51!",
        "Nova FC": "💛 Score update at minute 51: Meteor City 1 - 0 Nova FC."
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1037"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "timestamp": "2026-10-27T15:52:35Z",
    "match_minute": 51,
    "episode_id": "m_42_min51_GOAL_EVT-m_42-1037",
    "stats_snapshot": {
      "score": {
        "Meteor City": 1,
        "Nova FC": 0
      }
    },
    "render_status": "TIER-0 (Live Goal Event)",
    "is_fallback": false,
    "episode_seq": 1
  },
  "m_42_min57_ENTERED": {
    "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. Nova FC's defenders are congesting the central third, while Meteor City's midfield trio is using a wide, diagonal passing lane to bypass their press.",
    "fan_view": "The high press is starting to sting!",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. Nova FC's defenders are congesting the central third, while Meteor City's midfield trio is using a wide, diagonal passing lane to bypass their press.",
        "fan_view": "The high press is starting to sting!"
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
    "rejection_history": [
      "Format Error: ValidationError"
    ],
    "is_fallback": false,
    "episode_seq": 2,
    "superseded": false,
    "llm_latency_sec": 14.33,
    "completed_at_match_minute": 57,
    "render_status": "FINAL (AI Verified)"
  },
  "m_42_min62_EXITED": {
    "analyst_view": "At minute 62, Meteor City's high press subsides with only 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). Meteor City's midfield trio is sitting deep, creating narrow passing lanes, and stifling Nova FC's tempo.",
    "fan_view": "This is it, the momentum is all on Nova FC!",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 62, Meteor City's high press subsides with only 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). Meteor City's midfield trio is sitting deep, creating narrow passing lanes, and stifling Nova FC's tempo.",
        "fan_view": "This is it, the momentum is all on Nova FC!"
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
    "rejection_history": [
      "Format Error: ValidationError"
    ],
    "is_fallback": false,
    "episode_seq": 3,
    "superseded": false,
    "llm_latency_sec": 12.38,
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
  "tactical_summary": "Meteor City secures a 2-0 victory over Nova FC. Verified high-press tactical shifts occurred between minutes 57 and 62 (key tactical inflection initiated at minute 57). Aggressive fluidity yielded decisive possession, ultimately crushing Nova FC's defense.",
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
