Implement Novel Engine with world bible, relationship graph, chapter outline, cliffhanger engine and editable workflow.

Stage switch:
- `stage_id`: `novel_engine`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish novel plan generation, persist progress, then wait for user review before Asset Pipeline.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
