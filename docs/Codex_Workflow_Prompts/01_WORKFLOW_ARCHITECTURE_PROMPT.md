Implement workflow-first CineForge architecture integrated into Jellyfish.

Stage switch:
- `stage_id`: `workflow_architecture`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish architecture/state setup, persist progress, then wait for user review before Novel Engine.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
