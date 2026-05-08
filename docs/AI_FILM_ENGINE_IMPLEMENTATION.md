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
| 7 | QA Engine | Done | `QAEngine` 生成结构化 QA 分数、问题码和失败原因。 |
| 8 | Retry Engine | Done | `RetryEngine` 将 QA 失败转成可执行修复参数和重试提示词。 |
| 9 | Film State Engine | Done | `ShotContinuityState` 显式保存角色、服装、情绪、灯光、时间线、参考图。 |

## 关键文件

- `src/film_engine/core.py`：ECS、工作流、导演、一致性、Prompt Compiler、QA/Retry、闭环生产计划。
- `src/film_engine/platform.py`：Jellyfish Studio 记录到 Film Core 的边界适配。
- `src/film_engine/records.py`：Jellyfish Project/Chapter/Asset/Shot/Task 字典映射。
- `src/film_engine/post_production.py`：TTS、字幕、FFmpeg compose/concat/export 的计划编排。
- `src/film_engine/demo.py`：确定性的闭环生产计划样例。
- `src/film_engine/server.py`：无依赖本地运行仪表盘。
- `backend/app/api/v1/routes/film/engine.py`：FastAPI 下的 Film Engine 入口。

## API

启动后端后可访问：

- `GET /api/v1/film/engine/demo-plan`
- `GET /api/v1/film/engine/stage-index`

这两个接口用于确认闭环链路、九阶段索引、QA 失败和 Retry 请求是否可恢复。

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
  tests/test_closed_loop_production.py \
  tests/test_director_consistency.py \
  tests/test_jellyfish_platform_bridge.py \
  tests/test_luminai_runtime_entrypoint.py \
  tests/test_post_production_planner.py \
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

