Implement production-grade schemas for workflow assets, QA, runtime and retry systems.

Stage switch:
- `stage_id`: `data_schema`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish schema manifest, persist progress, then wait for user review before Final Integration.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
