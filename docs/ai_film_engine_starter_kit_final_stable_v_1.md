# AI Film Engine Starter Kit Final Stable v1

> 最终稳定版（不要再频繁修改）
>
> 用途：
> - Codex CLI
> - Claude Code
> - Cursor Agent
> - OpenHands
> - Devin 类 Agent
>
> 目标：
> 搭建工业级 AI 漫剧 / AI 电影引擎。

---

# 一、项目定位

本项目不是：

- AI 视频 demo
- Prompt 拼接器
- 简单工作流网站

而是：

# AI Film Engine

目标：

- AI 漫剧生成
- AI 电影生成
- 长剧情连续性
- 角色一致性
- 镜头语言系统
- 自动审片
- 自动重试
- 工业化批量生产

---

# 二、核心架构

```text
Novel / Script
    ↓
Story Graph
    ↓
Director Planner
    ↓
Film Core
    ↓
Prompt Compiler
    ↓
Runtime Adapter
    ↓
Render Runtime
    ↓
Video Models
    ↓
QA Engine
    ↓
Retry Engine
    ↓
Final Editing
```

---

# 三、核心原则

必须：

- ECS-inspired
- graph-driven
- state-centric
- runtime abstraction
- compiler architecture
- modular systems

禁止：

- giant monolith
- hardcoded prompts
- tightly coupled runtimes
- prompt spaghetti
- stateless generation

---

# 四、推荐技术栈

## Backend

- Python
- FastAPI
- Pydantic

## Workflow

- LangGraph

## Database

- PostgreSQL
- Redis

## Storage

- MinIO

## Queue

- Celery

## QA

- InsightFace
- MediaPipe
- OpenCV
- CLIP similarity

---

# 五、核心参考项目

## 1. huobao-drama

GitHub:
https://github.com/chatfire-AI/huobao-drama

用途：

- Runtime
- ffmpeg orchestration
- render queue
- subtitle pipeline
- video stitching
- TTS workflow

注意：

huobao-drama 适合作为：

# Runtime Layer

不适合作为：

# Film Core

不要重度魔改。

---

## 2. director_ai

GitHub:
https://github.com/freestylefly/director_ai

用途：

- Director DSL
- Shot abstraction
- Scene graph
- Timeline logic
- Camera abstraction

重点拆：

- Shot definition
- Scene definition
- Timeline logic
- Transition system

这是最适合做：

# 导演抽象层

的项目。

---

## 3. BigBanana-AI-Director

GitHub:
https://github.com/shuyu-labs/BigBanana-AI-Director

用途：

- emotional camera mapping
- pacing rules
- cinematic rhythm
- composition logic

适合：

# 导演规则层

不适合：

# 核心 DSL

重点拆：

- 情绪 → 运镜
- 节奏规则
- 镜头 rhythm

---

## 4. waoowaoo

GitHub:
https://github.com/waooAI/waoowaoo

用途：

- workflow graph
- orchestration
- memory systems
- multi-stage generation

重点学习：

- workflow graph
- context orchestration
- memory flow

---

# 六、扩展推荐开源项目（新增）

除了最初分析的 14 个项目，以下项目也非常值得研究。

---

## 1. ArcReel（非常推荐）

GitHub:
https://github.com/ArcReel/ArcReel

定位：

- Novel → Video
- AI Agent workflow
- 自动化长流程生成
- consistency workflow

适合借鉴：

- multi-agent orchestration
- story pipeline
- 自动生成链路

---

## 2. MoneyPrinterTurbo（强烈推荐）

GitHub:
https://github.com/harry0703/MoneyPrinterTurbo

定位：

- 自动化批量视频生产
- AI 短视频工厂

适合借鉴：

- subtitle pipeline
- auto editing
- batch generation
- low-cost production

---

## 3. ComfyUI（必须研究）

GitHub:
https://github.com/comfyanonymous/ComfyUI

定位：

- Graph-based AI workflow engine

适合借鉴：

- node graph architecture
- workflow execution
- graph runtime
- reusable pipelines

重要：

未来 AI Film Engine：

很可能会：

# ComfyUI 化

---

## 4. Open-Sora（长期重点关注）

GitHub:
https://github.com/hpcaitech/Open-Sora

定位：

- Open-source Sora-like video generation

适合研究：

- long video generation
- temporal consistency
- video diffusion

---

## 5. DiffSynth Studio（非常值得研究）

GitHub:
https://github.com/modelscope/DiffSynth-Studio

定位：

- diffusion video editing
- shot-based generation
- timeline orchestration

适合借鉴：

- timeline editing
- shot orchestration
- diffusion workflow

---

## 6. ComfyUI-CogVideoXWrapper（推荐）

GitHub:
https://github.com/kijai/ComfyUI-CogVideoXWrapper

适合借鉴：

- video workflow integration
- multi-model runtime
- CogVideo orchestration

---

## 7. StoryDiffusion（推荐）

GitHub:
https://github.com/HVision-NKU/StoryDiffusion

定位：

- consistent character generation
- long story image generation

适合借鉴：

- character consistency
- story continuity
- reference image flow

---

## 8. AnimateDiff（必须了解）

GitHub:
https://github.com/guoyww/AnimateDiff

适合借鉴：

- motion modules
- controllable animation
- diffusion motion workflow

---

# 七、推荐模型

## 视频模型

- Kling
- Seedance 2
- Veo
- Wan2.1

## 图像模型

- FLUX
- LoRA
- IPAdapter

## 语音模型

- CosyVoice
- Fish Speech
- GPT-SoVITS

---

# 七、最终推荐目录结构

```text
ai-film-engine/
│
├── AGENTS.md
├── SYSTEM_ARCHITECTURE.md
├── README.md
├── requirements.txt
├── .env.example
│
├── backend/
│   ├── api/
│   ├── core/
│   ├── runtime/
│   ├── compiler/
│   ├── registry/
│   ├── orchestration/
│   ├── qa/
│   ├── retry/
│   ├── state/
│   └── storage/
│
├── frontend/
│
├── runtime/
│   ├── adapters/
│   ├── ffmpeg/
│   ├── subtitle/
│   └── tts/
│
├── skills/
├── tests/
├── freeze/
├── benchmarks/
├── schemas/
├── migrations/
├── datasets/
├── samples/
├── tasks/
└── docs/
```

---

# 七点五、最终基座方案（核心）

这是最终稳定推荐方案。

不要：

- 从 0 开始自己重写所有系统
- 单独依赖某一个项目
- 重度魔改单个仓库

正确方式：

# 多项目拆解 + 重组。

---

# 主基座（最重要）

## Jellyfish

GitHub:
https://github.com/Forget-C/Jellyfish

最终定位：

# AI Studio OS / Workflow Core

负责：

- Project system
- Chapter management
- Shot management
- Asset management
- Async task system
- Queue system
- Workflow orchestration
- OpenAPI backend
- Studio UI
- Team collaboration

这是：

# 整个 AI Film Engine 的主平台基座。

不要重写。

建议：

- Fork 后二次开发
- 保留其 studio/workflow 架构
- 在其上增加 Film Core

---

# 从哪些项目拆什么（最重要）

## 1. huobao-drama

GitHub:
https://github.com/chatfire-AI/huobao-drama

拆：

- render pipeline
- ffmpeg orchestration
- subtitle pipeline
- TTS workflow
- stitching logic
- runtime adapters

不要拆：

- UI
- 主 workflow

最终定位：

# Runtime Layer

---

## 2. director_ai

GitHub:
https://github.com/freestylefly/director_ai

拆：

- Director DSL
- Shot abstraction
- Camera grammar
- Scene timeline
- Transition system
- Shot metadata

最终定位：

# Director Layer

这是：

# 最重要的导演抽象层来源。

---

## 3. BigBanana-AI-Director

GitHub:
https://github.com/shuyu-labs/BigBanana-AI-Director

拆：

- emotion → camera mapping
- pacing rules
- cinematic rhythm
- composition heuristics
- emotional transition logic

不要直接照搬。

重点是：

# 导演规则。

最终定位：

# Cinematic Rule Layer

---

## 4. waoowaoo

GitHub:
https://github.com/waooAI/waoowaoo

拆：

- workflow graph
- context orchestration
- memory flow
- agent coordination

最终定位：

# Orchestration Layer

---

## 5. Toonflow-app

GitHub:
https://github.com/HBAI-Ltd/Toonflow-app

拆：

- storyboard UI
- timeline UI
- shot editing interaction

最终定位：

# Storyboard UI Layer

---

## 6. StoryDiffusion

GitHub:
https://github.com/HVision-NKU/StoryDiffusion

拆：

- consistent character generation
- reference image pipeline
- long-story consistency

最终定位：

# Character Consistency Layer

---

# 你自己必须做（真正壁垒）

下面这些：

# 开源项目基本都没真正做好。

必须自己研发。

---

## 1. Film State Engine

维护：

- character continuity
- outfit continuity
- emotion continuity
- lighting continuity
- timeline continuity

这是：

# 下一代 AI Film Engine 最大壁垒。

---

## 2. QA Engine

自动检测：

- 崩脸
- 多手指
- outfit drift
- lighting mismatch
- shot continuity failure

---

## 3. Retry Engine

实现：

Generate
→ QA
→ Repair
→ Retry
→ Re-QA

---

## 4. Prompt Compiler

将：

- Director DSL
- Character State
- Scene State
- Shot State

编译为：

- Kling prompt
- Seedance prompt
- Veo prompt

---

## 5. Character Bible

包括：

- LoRA
- embedding
- outfit
- hairstyle
- voice
- emotional profile

---

## 6. Scene Bible

包括：

- lighting
- weather
- color tone
- camera style
- time of day

---

# 八、真正核心系统

真正值钱的是：

- Director DSL
- Shot Graph
- Character Registry
- Scene Registry
- Prompt Compiler
- QA Engine
- Retry Engine
- Film State Engine

不是：

# 单个视频模型

---

# 九、开发顺序（最终稳定版）

```text
1. Runtime
2. Director DSL
3. Shot Graph
4. Prompt Compiler
5. Character Registry
6. Scene Registry
7. QA Engine
8. Retry Engine
9. Film State Engine
```

不要乱序。

---

# 十、Skill 标准结构（固定）

每个 Skill 必须：

```text
开发
→ 测试
→ Freeze
→ Sample
→ Benchmark
```

标准目录：

```text
skills/
    xxx.md

tests/
    xxx_test.md

freeze/
    xxx_freeze.md

samples/
    xxx/

benchmarks/
    xxx_benchmark.md
```

---

# 十一、AGENTS.md（固定模板）

```md
# AI Film Engine

You are the lead architect of an industrial AI Film Engine.

This project is NOT a toy AI video generator.

Goals:
- cinematic storytelling
- character consistency
- shot continuity
- film state continuity
- automatic QA
- automatic retry
- industrial batch production

Core principles:
- graph-based workflow
- ECS-inspired architecture
- runtime abstraction
- prompt compiler architecture
- modular systems

DO NOT:
- build giant monoliths
- hardcode prompts
- tightly couple runtimes

DO:
- build reusable systems
- optimize consistency
- reduce generation randomness
```

---

# 十二、Skill：Director DSL

## 文件

```text
skills/director_dsl.md
```

## 内容

```md
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
```

---

## 测试

```text
tests/director_dsl_test.md
```

```md
Validate:
- YAML parsing
- AST generation
- schema validation
- prompt compilation
```

---

## Freeze

```text
freeze/director_dsl_freeze.md
```

```md
Frozen:
- shot schema
- scene schema
- AST structure

DO NOT rename:
- framing
- movement
- lens
- emotion
```

---

## Sample

```text
samples/director_dsl/suspense_scene.yaml
```

```yaml
scene:
  mood: suspense
  pacing: slow

shots:
  - framing: wide
    movement: slow_push
    lens: 35mm
    emotion: nervous
```

---

# 十三、Skill：Shot Graph

## 文件

```text
skills/shot_graph.md
```

## 内容

```md
Goal:
Build cinematic shot relationships.

Implement:
- shot sequencing
- pacing logic
- emotional escalation
- transition system
```

---

## 测试

```text
tests/shot_graph_test.md
```

```md
Validate:
- shot sequencing
- transition logic
- pacing continuity
```

---

## Freeze

```text
freeze/shot_graph_freeze.md
```

```md
Frozen:
- graph edge structure
- transition schema
- pacing metadata
```

---

## Samples

```text
samples/shot_graph/
├── confession_sequence.yaml
├── fight_sequence.yaml
└── suspense_sequence.yaml
```

### confession_sequence.yaml

```yaml
sequence_id: confession_scene_v1

scene:
  location: rooftop_night
  mood: emotional
  lighting: cinematic_blue
  weather: light_wind

characters:
  - heroine_001
  - hero_001

shots:
  - id: shot_001
    type: establishing_wide
    duration: 4
    movement: slow_push
    emotion: nervous

  - id: shot_002
    type: medium_two_shot
    duration: 5
    movement: static
    emotion: hesitation

  - id: shot_003
    type: closeup
    target: heroine_001
    duration: 4
    movement: dolly_in
    emotion: emotional

  - id: shot_004
    type: reaction_closeup
    target: hero_001
    duration: 3
    emotion: surprised

transitions:
  - from: shot_001
    to: shot_002
    type: cut

  - from: shot_002
    to: shot_003
    type: slow_dissolve

  - from: shot_003
    to: shot_004
    type: reaction_cut
```

---

### fight_sequence.yaml

```yaml
sequence_id: alley_fight_v1

scene:
  location: rainy_alley
  mood: aggressive
  lighting: neon_red

characters:
  - hero_001
  - villain_001

shots:
  - id: shot_001
    type: handheld_wide
    duration: 3
    movement: shaky_follow
    pacing: fast

  - id: shot_002
    type: impact_closeup
    duration: 1.5
    movement: whip_pan

  - id: shot_003
    type: tracking_shot
    duration: 4
    movement: side_tracking

  - id: shot_004
    type: slow_motion_finish
    duration: 3
    movement: arc_orbit

transitions:
  - from: shot_001
    to: shot_002
    type: hard_cut

  - from: shot_002
    to: shot_003
    type: motion_match

  - from: shot_003
    to: shot_004
    type: speed_ramp
```

---

### suspense_sequence.yaml

```yaml
sequence_id: suspense_corridor_v1

scene:
  location: dark_corridor
  mood: suspense
  lighting: low_key

characters:
  - heroine_001

shots:
  - id: shot_001
    type: hallway_wide
    duration: 5
    movement: slow_dolly

  - id: shot_002
    type: over_shoulder
    duration: 4
    movement: handheld_subtle

  - id: shot_003
    type: extreme_closeup
    duration: 2
    target: eyes

  - id: shot_004
    type: reveal_shot
    duration: 2
    movement: sudden_pan

transitions:
  - from: shot_001
    to: shot_002
    type: suspense_cut

  - from: shot_002
    to: shot_003
    type: tension_push

  - from: shot_003
    to: shot_004
    type: jump_reveal
```

---

# 十四、Skill：Character Registry

## 文件

```text
skills/character_registry.md
```

## 内容

```md
Goal:
Build character asset system.

Characters are entities, NOT prompts.

Each character contains:
- LoRA
- embeddings
- outfits
- voices
- reference images
```

---

## 测试

```text
tests/character_registry_test.md
```

```md
Validate:
- embedding loading
- outfit switching
- reference workflow
```

---

## Freeze

```text
freeze/character_registry_freeze.md
```

```md
Frozen:
- character schema
- outfit schema
- embedding structure
```

---

## Sample

```text
samples/character_registry/heroine_001.json
```

```json
{
  "id": "heroine_001",
  "base_model": "flux",
  "lora": "heroine_v12.safetensors",
  "seed": 12345,
  "outfits": [
    "school_uniform"
  ]
}
```

---

# 十五、Skill：Scene Registry

## 文件

```text
skills/scene_registry.md
```

## 内容

```md
Goal:
Build reusable scene assets.

Store:
- lighting
- weather
- tone
- mood
- camera style
```

---

## 测试

```text
tests/scene_registry_test.md
```

```md
Validate:
- lighting persistence
- scene continuity
- scene reuse
```

---

## Freeze

```text
freeze/scene_registry_freeze.md
```

```md
Frozen:
- scene schema
- lighting schema
- weather schema
```

---

# 十六、Skill：Prompt Compiler

## 文件

```text
skills/prompt_compiler.md
```

## 内容

```md
Goal:
Compile:
- Director DSL
- Character State
- Scene State
- Shot State

Into:
- Kling prompt
- Seedance prompt
- Veo prompt
```

---

## 测试

```text
tests/prompt_compiler_test.md
```

```md
Validate:
- DSL → prompt
- backend-specific prompts
- compile stability
```

---

## Freeze

```text
freeze/prompt_compiler_freeze.md
```

```md
Frozen:
- compiler interface
- metadata structure
```

---

# 十七、Skill：QA Engine

## 文件

```text
skills/qa_engine.md
```

## 内容

```md
Goal:
Detect:
- face drift
- broken anatomy
- outfit inconsistency
- lighting inconsistency
```

---

## 测试

```text
tests/qa_engine_test.md
```

```md
Validate:
- face detection
- anatomy detection
- continuity scoring
```

---

## Freeze

```text
freeze/qa_engine_freeze.md
```

```md
Frozen:
- QA score format
- failure schema
```

---

# 十八、Skill：Retry Engine

## 文件

```text
skills/retry_engine.md
```

## 内容

```md
Workflow:

Generate
→ QA
→ Fail
→ Repair
→ Retry
→ QA Again
```

---

## 测试

```text
tests/retry_engine_test.md
```

```md
Validate:
- retry policy
- regeneration logic
- repair strategy
```

---

# 十九、Skill：Film State Engine

## 文件

```text
skills/film_state_engine.md
```

## 内容

```md
Maintain:
- character continuity
- outfit continuity
- emotional continuity
- lighting continuity
- timeline continuity
```

---

# 二十、真正正确开发方式

不要：

```text
一句 prompt 生成整个系统
```

必须：

```text
AGENTS.md
+ skill
+ test
+ freeze
+ sample
+ benchmark
```

逐步开发。

---

# 二十一、真正核心思想（最终）

未来真正值钱的：

不是：

# “视频模型”

而是：

# “稳定、低成本、批量生产高一致性内容的能力”

真正壁垒：

- Director DSL
- Shot Graph
- Character Registry
- QA Engine
- Retry Engine
- Film State Engine

这才是：

# 下一代 AI 内容工厂核心。
