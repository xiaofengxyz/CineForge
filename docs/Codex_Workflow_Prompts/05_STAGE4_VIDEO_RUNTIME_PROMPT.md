Implement Video Runtime Engine for Seedance, Kling, Veo and Wan2.1, Sora and so on.

Stage switch:
- `stage_id`: `video_runtime`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish video render request compilation, persist progress, then wait for user review before QA/Retry.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
