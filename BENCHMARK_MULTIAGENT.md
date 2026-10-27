## ⚖️ Measured Architecture Comparison: Single-Agent vs Multi-Agent Pipeline (N = 2 Tactical Episodes + 1 Post-Match Recap)

Both configurations were executed live against local `llama3.2` on the exact same Seed 42 tactical episodes (`m_42_min57_ENTERED`, `m_42_min62_EXITED`). For the multi-agent pipeline, the deterministic Python factual core was stripped prior to auditing so that **only LLM-generated stylistic segments** were evaluated:

| Configuration | Execution Protocol | Measured Rule Violations | Live Episodes Validated | Recap Handoff Verified | Total Execution Time |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Single-Agent Monolithic** | 1 unconstrained agent prompt (episodes + recap combined) | **2 violation(s)** (Unverified digits in LLM color: ['62', '57', '62', '57', '45', '2', '0'], Forbidden number words in LLM color) | Unstructured text (no schema) | No structured ledger | `46.32s` |
| **Inside The Game Multi-Agent** | **ExplainerAgent ➔ Verifier ➔ RecapAgent** | **0 violation(s)** | **`2 / 2`** | **`True` (`2` eps)** | `41.19s` |
