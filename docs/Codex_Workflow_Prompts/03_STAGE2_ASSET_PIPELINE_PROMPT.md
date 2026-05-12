Implement Drama Asset Pipeline including Character Bible, Scene Bible, Shot Graph and Storyboard systems.

Stage switch:
- `stage_id`: `asset_pipeline`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish asset/storyboard extraction, persist progress, then wait for user review before Image Runtime.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
