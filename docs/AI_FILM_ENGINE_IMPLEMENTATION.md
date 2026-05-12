# CineForge AI Film Engine

## 项目定位

CineForge 当前是在 Jellyfish Studio OS 基座上做二次开发的工业级 AI 漫剧/AI 电影引擎。

Jellyfish 继续负责：

- 项目、章节、镜头、资产、文件、任务、OpenAPI、Studio UI
- 异步任务和生成任务状态管理
- 创作工作台和人工确认流程

新增 Film Engine 负责：

- Story Graph / Shot Graph
- Director Planner / Director DSL
- Film Core 连续性状态
- Prompt Compiler
- Runtime Adapter / Render Runtime
- Model Adapter Layer（provider/model/base_url/api_key 隔离）
- QA Engine / Retry Engine
- Final Editing / Post-production Plan

核心链路：

```text
Novel / Script
→ Story Graph
→ Director Planner
→ Film Core
→ Prompt Compiler
→ Runtime Adapter
→ Render Runtime
→ Video Models
→ QA Engine
→ Retry Engine
→ Final Editing
```

## 九阶段实现状态

| 阶段 | 模块 | 状态 | 说明 |
| --- | --- | --- | --- |
| 1 | Runtime | Done | `src/models/*`、`src/utils/provider_*` 提供 DashScope/厂商路由和本地/OSS/URL 媒体解析。 |
| 2 | Director DSL | Done | `DirectorRuleEngine`、`DirectorConsistencyEngine` 校验镜头语言并合并角色/场景 Bible。 |
| 3 | Shot Graph | Done | `WorkflowGraph` 和 Jellyfish chapter workflow 固化镜头生产顺序。 |
| 4 | Prompt Compiler | Done | `PromptCompiler` 从结构化导演 DSL 与连续性状态编译供应商提示词。 |
| 5 | Character Registry | Done | `CharacterBible` 管理 LoRA、embedding、服装、声线、参考图和负向词。 |
| 6 | Scene Registry | Done | `SceneBible` 管理灯光、天气、色调、情绪、场景参考图。 |
| 7 | QA Engine | Done+ | `QAEngine` 生成结构化 QA 分数、问题码和失败原因；视频任务已接入 Film Visual QA 组合评估器。 |
| 8 | Retry Engine | Done+ | `RetryEngine` 将 QA 失败转成可执行修复参数和重试提示词；Film Engine API 可创建真实 retry 视频任务。 |
| 9 | Film State Engine | Done | `ShotContinuityState` 显式保存角色、服装、情绪、灯光、时间线、参考图。 |

补充说明：

- 项目级 `qa_threshold` 已进入 Film Core 计划计算，不再只是 UI 配置。
- 项目级 `auto_retry` 与 `retry_limit` 已控制 Retry 请求生成。
- 新增 `src/film_engine/model_adapters.py`，将 text/image/video 模型调用统一隔离为 `ModelEndpointConfig(provider, model, base_url, api_key)`；持久化和 API 输出默认只显示 `api_key_configured`，不泄露明文密钥。
- 新增 `src/film_engine/workflow_control.py`，与 `docs/Codex_Workflow_Prompts` 的 `stage_id/enabled/automatic` 保持一致：自动阶段继续推进，非自动阶段完成后停在 `waiting_for_user`。
- 新增 `src/film_engine/text_to_drama.py`，可从一段故事文本生成 Novel Plan、Character/Scene Bible、Shot Graph、image runtime calls、video render requests、QA/Retry 和最终 handoff，并写入可恢复 JSON state。
- 已选择 `opencv-python-headless` 作为稳定基线，并在同一条 QA 链路中接入可选 InsightFace 与 CLIP 后端。视频任务成功后会尝试读取生成视频、参考帧、角色参考图和镜头提示词，写入 `GenerationTask.result.film_engine_qa_metrics` 与 `film_engine_visual_qa`。
- InsightFace 后端可产出 `face_similarity`，用于触发 `low_face_similarity`；CLIP 后端可产出语义 `clip_score`，用于触发 `weak_prompt_alignment`。依赖未安装或模型不可用时会记录 skipped reason，OpenCV 基线仍保留可恢复 QA 证据。
- 真实视频任务仍可由其他评估器写入 `qa_metrics` 或 `film_engine_qa_metrics`；Film Engine 会优先读取任务指标。没有真实 CV 指标时，会退回稳定代理指标，确保 QA/Retry 状态可解释。
- Final Export 只有在当前章节所有可规划镜头都有生成视频后才会标为 Done，避免“部分生成即导出完成”的误判。

## 工业级落地结论

当前九阶段不是“玩具 demo”，已经能在真实 Project/Chapter/Shot 数据上落地：

- 可把项目、章节、镜头、角色、场景、参考帧转成 Film Core 的结构化生产计划。
- 可把 `qa_threshold`、`auto_retry`、`retry_limit` 用于真实 QA/Retry 计算。
- 可按多集聚合生产状态，定位每集卡在剧本、分镜、资产、生成、QA、Retry 还是导出。
- 可在视频任务完成后写入 Film Visual QA 指标，并通过页面按钮对旧视频重新评估。
- 可从 Film Engine Retry 请求创建真实 `video_generation` 任务。

仍需要外部生产条件才能达到“工业级电影成片质量”：

- 模型供应商质量、角色/场景素材质量、提示词模板和人工审片标准会直接决定成片上限。
- Film Visual QA 当前覆盖 OpenCV 亮度/清晰度/画面可读性、InsightFace 角色脸部一致性、CLIP 画面与剧情/提示词语义匹配；InsightFace/CLIP 采用懒加载可选依赖，便于在 GPU/CPU 镜像中分层部署。
- Final Export 目前已有完整性门禁和后期计划，真实 FFmpeg/TTS/BGM 合成任务仍是下一层工程增强。

## 关键文件

- `src/film_engine/core.py`：ECS、工作流、导演、一致性、Prompt Compiler、QA/Retry、闭环生产计划。
- `src/film_engine/platform.py`：Jellyfish Studio 记录到 Film Core 的边界适配。
- `src/film_engine/model_adapters.py`：模型调用适配层，支持 provider/model/base_url/api_key 注入与脱敏输出。
- `src/film_engine/workflow_control.py`：workflow prompt 阶段开关，支持 automatic/manual/disabled 状态。
- `src/film_engine/text_to_drama.py`：输入文字到小说、资产、分镜、runtime、QA/Retry、导出计划的端到端编排器。
- `src/film_engine/records.py`：Jellyfish Project/Chapter/Asset/Shot/Task 字典映射。
- `src/film_engine/post_production.py`：TTS、字幕、FFmpeg compose/concat/export 的计划编排。
- `src/film_engine/demo.py`：确定性的闭环生产计划样例。
- `src/film_engine/server.py`：无依赖本地运行仪表盘。
- `backend/app/api/v1/routes/film/engine.py`：FastAPI 下的 Film Engine 入口。
- `backend/app/services/film/engine_state.py`：从 Jellyfish Project/Chapter/Shot/Scene/Character 数据构建 Film Engine 项目上下文，并持久化项目级运行配置。
- `backend/app/services/film/visual_qa.py`：Film Visual QA 组合评估器，产出 `lighting_similarity`、`face_similarity` 和语义 `clip_score`。
- `backend/app/services/film/generated_video.py`：视频生成任务完成后，写入 Film Visual QA 证据。
- `front/src/pages/aiStudio/filmEngine/FilmEngineDashboard.tsx`：项目内 Film Engine 配置、九阶段证据、workflow、QA/Retry 和下一步操作入口。

## API

启动后端后可访问：

- `GET /api/v1/film/engine/demo-plan`
- `GET /api/v1/film/engine/stage-index`
- `GET /api/v1/film/engine/stage-index?project_id=...&chapter_id=...`
- `GET /api/v1/film/engine/series-index?project_id=...`
- `GET /api/v1/film/engine/config?project_id=...`
- `PATCH /api/v1/film/engine/config?project_id=...`
- `POST /api/v1/film/engine/text-to-drama-plan`
- `POST /api/v1/film/engine/qa/evaluate-shot`
- `POST /api/v1/film/engine/retry-task`

这些接口用于确认闭环链路、九阶段索引、QA 失败和 Retry 请求是否可恢复，并把 Film Engine 接入真实项目/章节上下文。

`stage-index` 现在同时返回两套索引：

- `stages`：工业级 AI Film Engine 九阶段能力索引，顺序为 Runtime Adapter → Director DSL → Shot Graph → Prompt Compiler → Character Registry → Scene Registry → QA Engine → Retry Engine → Film State Engine。
- `workflow_stages`：Jellyfish 到 Film Core 的生产闭环 workflow，顺序为 script breakdown → shot preparation → asset consistency → film state → prompt compiler → runtime adapter → QA → retry → final export。

带 `project_id/chapter_id` 调用时，`summary.metadata` 会额外返回：

- `config`：项目级 Film Engine 运行配置，存储在 `Project.stats.film_engine_config`。
- `next_action`：下一步建议，用于前端跳转到章节、分镜工作室或剪辑页。
- `workflow_status`：当前章节每个生产闭环阶段的 done/pending 证据和指标。
- `shot_count`、`plannable_shot_count`、`ready_shot_count`、`generated_video_count`：当前章节可观测生产指标。

`series-index` 返回项目多集生产总览：

- `episode_count`：章节/集数。
- `totals`：总镜头、可规划镜头、ready 镜头、已生成视频、QA 报告、Retry 请求。
- `chapters`：每集的九阶段完成度、workflow 完成度、QA/Retry、Final Export 和下一步动作。
- `all_chapters_done`：所有章节九阶段证据是否齐备。

`text-to-drama-plan` 用于从一段文字创建可执行生产计划：

- 请求体：`{"source_text":"...","title":"...","config":{"stage_switches":{...},"runtime_profiles":{...}}}`
- `runtime_profiles.text/image/video` 均支持 `provider`、`model`、`base_url`、`api_key`。
- 响应包含 Novel Plan、资产/分镜、image runtime calls、video render requests、QA/Retry、stage switch 进度和可恢复 `state_path`。
- 返回内容默认不暴露明文 `api_key`；只返回 `api_key_configured=true/false`。
- 当某阶段 `automatic=false` 时，响应 `status=waiting_for_user`，该阶段状态为 `waiting_for_user`，后续阶段为 `blocked`。

`qa/evaluate-shot` 用于旧视频或人工复检：

- 请求体：`{"shot_id":"..."}`
- 行为：读取镜头生成视频、参考帧、角色参考图和提示词文本，用 Film Visual QA 计算视觉/身份/语义指标，并把结果写入最新视频任务；如果没有视频任务，会创建 `film_visual_qa` 任务保存证据。

`retry-task` 用于一键二次渲染：

- 请求体：`{"project_id":"...","chapter_id":"...","shot_id":"...","ratio":"9:16"}`
- 行为：读取当前 Film Engine Retry prompt，创建真实 `video_generation` 任务，并关联回该镜头。

## 前端可见入口

Jellyfish 主前端已新增：

- 侧边栏入口：`Film Engine`
- 路由：`/film-engine`
- 项目工作台标签页：`Film Engine`
- 项目仪表盘摘要卡：展示九阶段证据、生产闭环完成度和下一步提示。
- 分镜列表按钮：从章节上下文直接进入当前章节 Film Engine 配置。

页面集中展示：

- 九阶段是否全部完成
- 每个阶段的 owner、证据、核心产物和运行指标
- 生产闭环 workflow
- 运行时供应商、模型、参考帧策略、Director DSL 焦段、QA 阈值、Retry 策略等项目级配置
- render requests、QA reports、retry requests
- 镜头运行计划中的 `Film QA` 按钮：对已有生成视频重评估并写回指标。
- 镜头运行计划中的 `Retry` 按钮：对有 Retry 请求的镜头创建真实二次渲染任务。
- final editing/export 状态
- 多集生产总览：每集镜头数、已生成视频数、QA/Retry 数量、九阶段完成度和下一步提示

## 用户操作手册

从配置到多集 AI 漫剧出片的详细步骤见：

- `docs/AI_FILM_ENGINE_USER_MANUAL.md`

## 本地测试

推荐先跑后端主测试：

```bash
cd backend
uv run pytest -q
```

再从仓库根目录跑 Film Engine 兼容测试：

```bash
pytest tests -q
```

如只验证新增核心：

```bash
pytest \
  tests/test_film_engine_api.py \
  tests/test_visual_qa.py \
  -q
```

## 运行

后端：

```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

轻量 Film Engine 仪表盘：

```bash
python -m src.film_engine.run_server
```

Jellyfish 前端仍按原项目运行：

```bash
cd front
pnpm dev --host 0.0.0.0
```
