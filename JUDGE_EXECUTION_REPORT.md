# Automated Hackathon Judge — End-to-End Execution Report

- **Execution Timestamp (UTC):** `2026-10-27T14:58:10Z`
- **Git Commit (HEAD) & Seed:** `024b820` | `Seed 42 (min 48..90)`
- **Total Audit Duration:** `81.14s`
- **Overall Verification Score:** **`10 / 10 Checks Passed (100%)`**

## 1. End-to-End Verification Matrix

| Category | Verification Check | Status | Empirical Evidence |
| :--- | :--- | :---: | :--- |
| 1. Technical Implementation | Verifier & Tactical Impact Explorer Unit Suite | **PASS** | All unit & regression tests passed (test_verifier.py + test_insight_builder.py) |
| 1. Technical Implementation | Git Index Hygiene & Regex Secret Content Scan | **PASS** | 0 scratch files & 0 credential patterns across all 26 tracked files |
| 2. Data & Detector | Seed 42 Ground Truth & Realism | **PASS** | Pass Acc: 89.7%, Score: {'Meteor City': 2, 'Nova FC': 0}, True Press Window: min 52..64 |
| 2. Data & Detector | Control Match Silence Across All Control Seeds in 1..30 | **PASS** | 0 false alarms across all 10 control seeds ([2, 4, 9, 12, 16, 20, 22, 24, 25, 28]) |
| 2. Data & Detector | Independent Outcome Generalization (Both Nova FC Win AND Draw Verified) | **PASS** | Nova FC win verified on seeds [1, 6, 9]; Draw verified on seeds [3, 5, 7] |
| 3. Live Agentic Pipeline | In-Place DRAFT -> FINAL (AI Verified) Upgrade on All Tactical Alarms | **PASS** | Upgraded episodes: ['m_42_min57_ENTERED', 'm_42_min62_EXITED'] (llm_verified=2/2, median_latency=10.46s) |
| 3. Live Agentic Pipeline | Strict ISO-8601 Timestamp Validity (including minute >= 60) | **PASS** | All 6 emitted overlay lines have valid ISO-8601 timestamps |
| 4. UX & Multi-Audience | Uncontaminated Bilingual Split-Screen (EN & FR Verified in Both Modes) | **PASS** | EN feed starts with 'At minute 57' and FR feed starts with 'À la 57e minute' without cross-contamination |
| 4. UX & Multi-Audience | Verified RecapAgent Handoff & Causal Detection Wording | **PASS** | recap_verified=True, causal wording verified ('first confirmed by the causal detector at minute 57') |
| 5. Enterprise & Fabric | Director Hold/Approve State Transitions & Fabric Delivery Accounting | **PASS** | Director states verified ('🛑 HELD BY DIRECTOR (Withdrawn from Air)' -> '📡 ON-AIR (Director Approved)') | Fabric live_sends=8, local_fallbacks=0 |

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
  "fabric_live_sends_succeeded": 8,
  "fabric_local_fallbacks": 0,
  "llm_latency_sec_median": 10.46,
  "llm_latency_sec_max": 12.87,
  "last_updated_utc": "2026-10-27T14:58:01Z"
}
```

## 3. Live Verified Broadcast Overlays (`broadcast_ui.jsonl` Merged State)
```json
{
  "m_42_min51_GOAL_EVT-m_42-1037": {
    "analyst_view": "GOAL at minute 51! M-11 scores for Meteor City. Meteor City 1 - 0 Nova FC.",
    "fan_view": "GOOOAAAL! Clinical finish by M-11 for Meteor City!",
    "multiaudience": {
      "en": {
        "analyst_view": "GOAL at minute 51! M-11 scores for Meteor City. Meteor City 1 - 0 Nova FC.",
        "fan_view": "GOOOAAAL! Clinical finish by M-11 for Meteor City!"
      },
      "fr": {
        "analyst_view": "BUT à la 51e minute ! M-11 marque pour Meteor City. Meteor City 1 - 0 Nova FC.",
        "fan_view": "BUUUT ! Finition clinique signée M-11 pour Meteor City !"
      },
      "club_voices": {
        "Meteor City": "Goal update (1-0): Meteor City strikes at minute 51!",
        "Nova FC": "Score update at minute 51: Meteor City 1 - 0 Nova FC."
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
    "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. The compact pressing unit closes central passing lanes and forces hurried clearances.",
    "fan_view": "Meteor City's high pressure forces Nova FC on the back foot!",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 57, Meteor City initiates a high press with 8 defensive actions against Nova FC, reducing build-up accuracy to 50%. The compact pressing unit closes central passing lanes and forces hurried clearances.",
        "fan_view": "Meteor City's high pressure forces Nova FC on the back foot!"
      },
      "fr": {
        "analyst_view": "À la 57e minute, Meteor City enclenche un pressing haut avec 8 actions défensives dans le camp de Nova FC, réduisant la précision de relance adverse à 50%. Le bloc compact ferme les lignes de passe axiales et contraint à des dégagements d'urgence.",
        "fan_view": "Une pression totale de Meteor City agresse la zone de relance adversaire."
      },
      "club_voices": {
        "Meteor City": "Meteor City dominating territory with a sustained high press!",
        "Nova FC": "Nova FC forced into hurried clearances under heavy press!"
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1144"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "exit_reason": null,
    "model_used": "llama3.2",
    "timestamp": "2026-10-27T15:58:36",
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
    "llm_latency_sec": 8.06,
    "completed_at_match_minute": 57,
    "render_status": "FINAL (AI Verified)"
  },
  "m_42_min62_EXITED": {
    "analyst_view": "At minute 62, Meteor City's high press subsides with 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). Meter City's defensive shape now opens, allowing Nova FC to shift into structured build-up play.",
    "fan_view": "The pressure mounts to no avail as Nova FC picks up steam!",
    "multiaudience": {
      "en": {
        "analyst_view": "At minute 62, Meteor City's high press subsides with 1 recent defensive action, allowing Nova FC to stabilize possession (57% pass accuracy over the window). Meter City's defensive shape now opens, allowing Nova FC to shift into structured build-up play.",
        "fan_view": "The pressure mounts to no avail as Nova FC picks up steam!"
      },
      "fr": {
        "analyst_view": "À la 62e minute, le pressing haut de Meteor City retombe avec 1 action défensive récente, permettant à Nova FC de réorganiser son jeu (précision de relance remontée à 57%). Le bloc défensif de Meteor City s'ouvre, permitant à Nova FC de relancer avec une régularité accrue.",
        "fan_view": "Le barrage n'avantage rien, Nova FC se remonte pour l'affaire!"
      },
      "club_voices": {
        "Meteor City": "Meteor City regains tactical control as the pressing wave ends.",
        "Nova FC": "Nova FC manages to find passing lanes and stabilize the tempo."
      }
    },
    "cited_event_ids": [
      "EVT-m_42-1175"
    ],
    "language_used": "English",
    "target_persona": "General Fan",
    "exit_reason": "exhausted",
    "model_used": "llama3.2",
    "timestamp": "2026-10-27T16:03:45",
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
    "llm_latency_sec": 12.87,
    "completed_at_match_minute": 62,
    "render_status": "📡 ON-AIR (Director Approved)",
    "director_decision": "APPROVED_ON_AIR"
  },
  "m_42_min79_GOAL_EVT-m_42-1613": {
    "analyst_view": "GOAL at minute 79! M-02 scores for Meteor City. Meteor City 2 - 0 Nova FC.",
    "fan_view": "GOOOAAAL! Clinical finish by M-02 for Meteor City!",
    "multiaudience": {
      "en": {
        "analyst_view": "GOAL at minute 79! M-02 scores for Meteor City. Meteor City 2 - 0 Nova FC.",
        "fan_view": "GOOOAAAL! Clinical finish by M-02 for Meteor City!"
      },
      "fr": {
        "analyst_view": "BUT à la 79e minute ! M-02 marque pour Meteor City. Meteor City 2 - 0 Nova FC.",
        "fan_view": "BUUUT ! Finition clinique signée M-02 pour Meteor City !"
      },
      "club_voices": {
        "Meteor City": "Goal update (2-0): Meteor City strikes at minute 79!",
        "Nova FC": "Score update at minute 79: Meteor City 2 - 0 Nova FC."
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
  "tactical_summary": "Meteor City secures a 2-0 victory over Nova FC. Observed high-press regime spanned minutes 57 to 62 (first confirmed by the causal detector at minute 57). Disciplined interlocking of bodies enabled fleet high-intensity pressing, dominating possession and stifling opponent's buildup.",
  "turning_point": {
    "minute": 57,
    "episode_id": "m_42_min57_ENTERED"
  },
  "key_episode_ids": [
    "m_42_min51_GOAL_EVT-m_42-1037",
    "m_42_min57_ENTERED"
  ],
  "agent_handoff_count": 4,
  "recap_verified": true,
  "verification_mode": "llm_verified"
}
```
