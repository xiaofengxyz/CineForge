Implement QA and Retry Engine for all workflow stages.

Stage switch:
- `stage_id`: `qa_retry_engine`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish QA/Retry evaluation, persist progress, then wait for user review before Studio UI.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
