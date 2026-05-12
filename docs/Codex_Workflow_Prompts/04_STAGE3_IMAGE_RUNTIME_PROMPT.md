Implement Image Runtime pipeline using FLUX, SDXL, StoryDiffusion and ComfyUI adapters.

Stage switch:
- `stage_id`: `image_runtime`
- `enabled`: `true`
- `automatic`: `true`
- If `automatic=false`, finish image runtime request preparation, persist progress, then wait for user review before Video Runtime.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems
