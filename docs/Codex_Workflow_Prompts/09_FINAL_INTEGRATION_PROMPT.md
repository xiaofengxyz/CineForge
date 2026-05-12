Connect all workflow stages into one executable AI Drama Operating System.

Stage switch:
- `stage_id`: `final_integration`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish final handoff, persist progress, then wait for user acceptance instead of marking the run fully released.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
