# AI Film Engine Test Cases

## 核心闭环

- `tests/test_closed_loop_production.py`
  - 验证 Jellyfish → Film Core → Prompt Compiler → Runtime → QA → Retry → Final Export 的顺序。
  - 验证角色参考、场景参考、负向词、QA 失败、Retry 参数。
  - 验证项目配置传入的 QA 阈值会改变失败判定。
  - 验证 `retry_limit` 会限制自动 Retry 请求数量。
  - 验证 `auto_retry=false` 时 QA 失败不会生成 Retry 请求。
  - 验证 QA report 会携带原始 metrics，便于前端解释真实 CV 分数。

## 模型适配层与阶段开关

- `tests/test_model_adapter_layer.py`
  - 验证 `ModelEndpointConfig` 接受 `baseurl/base_url` 和 `api_key` 输入。
  - 验证 `RuntimeAdapterLayer` 将 provider/model/base_url/api_key 隔离在适配层，不让 Film Core 直接依赖供应商 SDK。
  - 验证 API/日志安全输出会脱敏 `api_key` 和鉴权 header。

- `tests/test_workflow_control.py`
  - 验证 `automatic=false` 的阶段完成后进入 `waiting_for_user`。
  - 验证人工阶段之后的阶段被标记为 `blocked`。
  - 验证 `enabled=false` 的阶段被标记为 `disabled`，不会伪造成完成。

## Text-to-Drama 端到端计划

- `tests/test_text_to_drama_pipeline.py`
  - 验证一段文字可生成 Novel Plan、Character/Scene Bible、Shot Graph、image runtime calls、video render requests、QA/Retry 和最终 handoff。
  - 验证 workflow state 写入 `output/cineforge_runs/{run_id}/state.json` 风格的可恢复 JSON。
  - 验证 video runtime endpoint 可输入 `base_url/api_key`，响应和持久化状态不泄露明文密钥。
  - 验证 `novel_engine.automatic=false` 时停在小说审核点，资产、视频和 QA 阶段不会自动执行。

## 真实视觉 QA

- `backend/tests/test_visual_qa.py`
  - 验证 `OpenCVVisualEvaluator` 可以读取真实视频字节。
  - 验证输出 Film Engine 可消费的 `lighting_similarity` 与 `clip_score`。
  - 验证分数范围稳定在 `0..1`，不会污染 `QAEngine` 阈值计算。
  - 验证 `FilmSemanticVisualEvaluator` 可通过注入后端产出 InsightFace 风格 `face_similarity` 与 CLIP 风格语义 `clip_score`。
  - 验证组合式 `Film Visual QA` 会保留 OpenCV 基线，并让真实 CLIP 语义分覆盖 OpenCV 代理 `clip_score`。

## 导演和连续性

- `tests/test_director_consistency.py`
  - 验证 Character Bible、Scene Bible 合并到提示词上下文。
  - 验证缺失 Bible 会阻断生成上下文。

## Jellyfish 边界

- `tests/test_jellyfish_platform_bridge.py`
  - 验证 StudioAsset 注册为 ECS Entity。
  - 验证 StudioShot 转连续性状态。
  - 验证 Runtime Provider 留在边界层，不耦合 Film Core。

- `tests/test_jellyfish_record_mapper.py`
  - 验证 Jellyfish Project、Chapter、Asset、Shot、Task 字典映射。

## 后期制作

- `tests/test_post_production_planner.py`
  - 验证 TTS、字幕、FFmpeg compose、concat、export 计划。

## 后端 API

- `backend/tests/test_film_engine_api.py`
  - 验证 `/api/v1/film/engine/demo-plan`。
  - 验证 `/api/v1/film/engine/stage-index`。
  - 验证 `/api/v1/film/engine/series-index` 的多集聚合服务。
  - 验证 `/api/v1/film/engine/text-to-drama-plan` 可从文字生成可执行生产计划且不泄露密钥。
  - 验证九阶段能力索引为 Runtime Adapter → Film State Engine，且 `all_stages_done=true`。
  - 验证生产闭环 `workflow_stages` 仍保留 script breakdown → final export。
  - 验证项目级 Film Engine 配置会持久化到 `Project.stats.film_engine_config`。
  - 验证真实 Project/Chapter/Shot/Scene/Character 上下文可构建 render requests、QA reports、workflow status 和 final export 证据。
  - 验证视频任务结果中的 `qa_metrics` 会被 Film Engine 读取。
  - 验证手动 Film Visual QA 会把 `lighting_similarity`、`face_similarity`、语义 `clip_score` 写回任务结果。
  - 验证没有历史视频任务时，会创建 `film_visual_qa` 任务保存评估证据。
  - 验证 Film Engine Retry 请求可以创建真实 `video_generation` 任务，并关联回镜头。
  - 验证部分镜头生成时 `final_export` 仍保持 Pending。
  - 验证多集项目按章节聚合镜头、生成视频、QA、Retry 和下一步动作。

- `tests/test_luminai_runtime_entrypoint.py`
  - 验证轻量 Film Engine server 的 `/health`、`/demo/closed-loop-plan`、`/api/studio/status`。
  - 验证轻量 server `POST /api/text-to-drama/run` 可从文字生成可执行生产计划。
  - 测试内显式禁用本地代理，避免 `127.0.0.1` 在代理环境下被误拦截。

## 项目流程集成

- `backend/app/services/film/engine_state.py`
  - 空项目/空章节返回明确 `next_action`，不会伪造生成证据。
  - 有章节上下文时按真实镜头状态计算 `shot_count`、`plannable_shot_count`、`ready_shot_count`、`generated_video_count`。
  - 有角色/场景/参考图/生成视频时，九阶段和生产 workflow 均能形成 done 证据。

## 前端可见化

- `front/src/pages/aiStudio/filmEngine/FilmEngineDashboard.tsx`
  - 读取 `/api/v1/film/engine/stage-index`。
  - 读取 `/api/v1/film/engine/series-index` 并展示多集生产总览。
  - 带项目上下文时读取 `/api/v1/film/engine/config` 并可保存运行时、参考帧、QA、Retry 配置。
  - 展示九阶段完成度、阶段证据、生产 workflow、render requests、QA reports、retry requests 和 final export。
  - 镜头运行计划支持 `Film QA` 按钮，触发 `/api/v1/film/engine/qa/evaluate-shot`。
  - 镜头运行计划支持 `Retry` 按钮，触发 `/api/v1/film/engine/retry-task`。
  - 展示每集镜头数、可规划镜头数、已生成视频数、QA/Retry 数量、九阶段完成度和下一步提示。
  - 后端不可用时展示 API 地址和启动命令，保留“重新连接”操作。
  - 项目工作台和分镜列表均能进入带 chapter 上下文的 Film Engine 页面。
  - 通过 `front` TypeScript 检查覆盖接口类型、路由和页面编译。

## 本轮验证命令

```bash
cd backend
uv run python -m pytest tests/test_visual_qa.py tests/test_film_engine_api.py -q -s
```

```bash
uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_closed_loop_production.py -q -s
```

```bash
uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_model_adapter_layer.py tests/test_workflow_control.py tests/test_text_to_drama_pipeline.py tests/test_luminai_runtime_entrypoint.py -q -s
```

```bash
cd front
./node_modules/.bin/tsc --noEmit
```
