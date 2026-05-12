Transform Jellyfish frontend into CineForge Studio workflow UI.

Stage switch:
- `stage_id`: `studio_ui`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish UI/API manifest, persist progress, then wait for user review before Data Schema.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
