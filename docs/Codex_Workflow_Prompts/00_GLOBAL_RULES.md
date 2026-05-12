THIS PROJECT IS A FORK OF JELLYFISH.
DO NOT CREATE A NEW PROJECT.
Extend existing architecture only.

Requirements:
- Persist workflow state
- Support edit/regenerate
- Integrate QA and Retry
- Reuse Jellyfish systems

Workflow execution rule:
- Each prompt stage has `enabled` and `automatic` switches.
- Automatic stages continue to the next enabled stage without human review.
- Non-automatic stages finish their own artifacts, persist progress, then stop with `waiting_for_user`.
