# Director DSL Skill

Goal:
Build structured cinematic language.

Example:

```yaml
scene:
  mood: suspense
  pacing: slow

shots:
  - framing: medium_closeup
    movement: dolly_in
    lens: 85mm
    emotion: tension
```

Requirements:
- YAML support
- AST support
- schema validation
- timeline compatibility
- prompt compilation support
