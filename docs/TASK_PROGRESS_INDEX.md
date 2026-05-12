# Task Progress Index

更新时间：2026-05-12

## 当前任务

在 Jellyfish fork 基础上实现工业级 AI 漫剧/电影引擎闭环，覆盖产品设计、架构、代码实现、测试、文档和可运行入口。

本轮补充目标：按 `docs/Codex_Workflow_Prompts` 继续补齐可执行能力，重点落地“无基础图片/视频资产时可一键从免费图库采集素材”的可运行闭环，并同步补齐后端接口、前端按钮、测试和文档。

## 本轮执行计划

1. 审阅当前 Film Engine、Jellyfish 接入、workflow prompt 文档、测试和文档，确认本轮新增落点。
2. 新增 provider-neutral 免费图库采集服务：默认使用 Wikimedia Commons Core REST API，支持图片/视频查询、失败降级、去重和许可证页面追踪。
3. 新增 Film Engine API：`POST /api/v1/film/engine/stock-assets/collect`，支持项目/章节上下文、非持久预览和持久化为 Jellyfish `FileItem` + `FileUsage`。
4. 将采集入口接入前端 Film Engine 页面：项目无基础资产或需要补素材时，可点击按钮采集图片/视频并查看结果。
5. 为采集服务、API、幂等持久化和 UI 类型安全补测试。
6. 更新实现文档、测试用例文档、用户手册和本任务进度索引。
7. 启动后端/前端，调用接口和页面入口做运行验证。

## 当前完成点

| ID | 工作项 | 状态 | 恢复提示 |
| --- | --- | --- | --- |
| P0 | 仓库和文档审阅 | Done | 参考 `docs/ai_film_engine_starter_kit_final_stable_v_1.md` 与本文件。 |
| P1 | 九阶段计划固化 | Done | 阶段顺序以 Runtime → Film State Engine 为准。 |
| P2 | Film Engine Core | Done | 查看 `src/film_engine/core.py`。 |
| P3 | Jellyfish Platform Bridge | Done | 查看 `src/film_engine/platform.py`、`src/film_engine/records.py`。 |
| P4 | Runtime Adapter | Done | 查看 `src/models/*`、`src/utils/provider_*`。 |
| P5 | Final Editing | Done | 查看 `src/film_engine/post_production.py`。 |
| P6 | FastAPI 入口 | Done | `/api/v1/film/engine/stage-index` 返回 `all_stages_done=true`、工业九阶段 `stages` 和生产闭环 `workflow_stages`。 |
| P7 | 测试 | Done | `backend/tests/test_film_engine_api.py` 和根级闭环测试已覆盖九阶段、workflow、QA/Retry。 |
| P8 | 文档 | Done | 查看 `docs/AI_FILM_ENGINE_IMPLEMENTATION.md` 与 `docs/AI_FILM_ENGINE_TEST_CASES.md`。 |
| P9 | Jellyfish 主前端可见化 | Done | 侧边栏新增 `Film Engine`，路由 `/film-engine` 展示九阶段完成度、阶段证据、workflow、render requests、QA、Retry、Final Export。 |
| P10 | 项目/章节流程集成 | Done | `GET /api/v1/film/engine/stage-index?project_id=&chapter_id=` 可读取真实 Project/Chapter/Shot 上下文；项目工作台新增 Film Engine 标签页，分镜列表可按章节进入。 |
| P11 | Film Engine 项目配置 | Done | `GET/PATCH /api/v1/film/engine/config?project_id=` 读写 `Project.stats.film_engine_config`，支持 runtime、reference mode、Director DSL lens、QA threshold、Retry limit。 |
| P12 | 不可用状态兜底 | Done | 前端统一读取 runtime `env.js`/Vite API base，Film Engine 连接失败时显示 API 地址、后端启动命令和重新连接按钮。 |
| P13 | 本轮计划与缺口核验 | Done | 已确认核心九阶段存在，但真实项目侧需要多集总览、QA 阈值生效、Retry limit 生效、Final Export 完整性区分和用户操作手册。 |
| P14 | QA/Retry/Final Export 项目侧补强 | Done | 已将 `qa_threshold`、`retry_limit` 接入 Film Core，并在项目 summary 中区分“部分生成”和“整章可导出”。 |
| P15 | 多集生产总览 | Done | 新增后端 `GET /api/v1/film/engine/series-index?project_id=`，前端 Film Engine 页已接入，并已用后端服务测试覆盖。 |
| P16 | 用户操作手册 | Done | 新增 `docs/AI_FILM_ENGINE_USER_MANUAL.md`，覆盖从配置到多集 AI 漫剧出片。 |
| P17 | 本轮测试补强 | Done | 新增/更新 QA 阈值、Retry limit、自动 Retry 关闭、任务 QA 指标、多集聚合、部分生成不导出的测试。 |
| P18 | OpenCV 真实视觉 QA | Done | 已安装 `opencv-python-headless`，新增 `backend/app/services/film/visual_qa.py`，视频任务成功后写入 `film_engine_qa_metrics` 和 `film_engine_visual_qa`。 |
| P19 | 旧视频手动重评估 | Done | 新增 `POST /api/v1/film/engine/qa/evaluate-shot`，可对已有生成视频补写 Film Visual QA 指标。 |
| P20 | 真实 Retry 任务 | Done | 新增 `POST /api/v1/film/engine/retry-task`，可从 Film Engine Retry 请求创建真实 `video_generation` 任务。 |
| P21 | 前端 QA/Retry 操作 | Done | Film Engine 镜头运行计划新增 `Film QA` 与 `Retry` 操作按钮。 |
| P22 | InsightFace/CLIP QA 方案 | Done | 设计为组合式 `FilmVisualQA`：OpenCV 基线始终可用，InsightFace 与 CLIP 通过懒加载后端产生 `face_similarity` 和语义 `clip_score`。 |
| P23 | Film Visual QA 后端接入 | Done | `video_generation` 成功后与 `/qa/evaluate-shot` 手动重评估均已接入组合式 QA 上下文，包含角色参考图、镜头参考帧和提示词文本。 |
| P24 | InsightFace/CLIP 测试与文档 | Done | 已新增注入式 InsightFace/CLIP 单元测试，并更新测试用例文档、实现文档和用户手册。 |
| P25 | 本轮计划与落点核验 | Done | 已确认缺口为模型适配层、workflow prompt 阶段开关、text-to-drama 可执行入口。 |
| P26 | 模型调用适配层 | Done | 新增 `src/film_engine/model_adapters.py`，provider/model/base_url/api_key 可注入，输出默认脱敏。 |
| P27 | Workflow Prompt 阶段开关 | Done | 新增 `src/film_engine/workflow_control.py`；每阶段支持 enabled/automatic，非自动阶段完成后等待用户操作。 |
| P28 | Text-to-Drama 编排器 | Done | 新增 `src/film_engine/text_to_drama.py`；输入文本生成 Novel Plan、资产/分镜、runtime 请求、QA/Retry 和导出计划。 |
| P29 | API/轻量 server 入口 | Done | 新增 `POST /api/v1/film/engine/text-to-drama-plan` 和轻量 server `POST /api/text-to-drama/run`。 |
| P30 | 本轮测试与文档 | Done | 已补单元/接口测试，更新测试用例、实现文档、用户手册，并完成定向验证。 |
| P31 | 免费图库采集服务 | Done | 新增 `backend/app/services/film/stock_assets.py`，默认接入 Wikimedia Commons，支持图片/视频、失败降级、去重和许可证页面追踪。 |
| P32 | 采集 API 与持久化 | Done | 新增 `POST /api/v1/film/engine/stock-assets/collect`，可非持久预览，也可写入 `FileItem` + `FileUsage`。 |
| P33 | 前端采集按钮 | Done | Film Engine 页面新增 `采集基础素材`，展示缩略图、图片/视频类型、素材源、许可证页和持久化状态。 |
| P34 | 采集测试与文档 | Done | 已补采集 API、幂等持久化、前端类型检查说明，并更新实现文档、测试用例和用户手册。 |
| P35 | 本轮运行验证 | Done | 后端/前端已启动验证；`stage-index`、`stock-assets/collect` 和 `/film-engine` 页面入口均可访问。 |
| P36 | 重启后服务恢复验证 | Done | 2026-05-12 重启后确认 7788/8000 未监听，已重新启动 uvicorn 与 Vite；`/film-engine`、`stage-index`、免费素材采集 API 和定向测试均通过。 |

## 九阶段结论

九个工业能力阶段在内置验收样例中均为 Done，并已在多处可见：

- API：`GET /api/v1/film/engine/stage-index`
- 项目 API：`GET /api/v1/film/engine/stage-index?project_id=...&chapter_id=...`
- 多集 API：`GET /api/v1/film/engine/series-index?project_id=...`
- 基础素材采集 API：`POST /api/v1/film/engine/stock-assets/collect`
- 前端：`http://localhost:7788/film-engine`
- 项目工作台：`/projects/{projectId}?tab=film-engine&chapter={chapterId}`
- 分镜列表：章节顶部 `Film Engine` 按钮
- 文档：`docs/AI_FILM_ENGINE_IMPLEMENTATION.md`、`docs/AI_FILM_ENGINE_USER_MANUAL.md`

九阶段顺序：

1. Runtime Adapter
2. Director DSL
3. Shot Graph
4. Prompt Compiler
5. Character Registry
6. Scene Registry
7. QA Engine
8. Retry Engine
9. Film State Engine

同时保留生产闭环 workflow：script breakdown → shot preparation → asset consistency → film state → prompt compiler → runtime adapter → QA → retry → final export。

说明：

- 不带项目参数时，`stage-index` 返回内置验收样例，代表引擎能力九阶段已完成。
- 带 `project_id/chapter_id` 时，`stage-index` 返回当前漫剧项目/章节的真实证据；如果章节还没分镜、镜头未准备或视频未生成，页面会显示 Pending 并给出下一步操作。
- 带 `project_id` 调用 `series-index` 时，返回多集/多章节聚合状态，用于从零到整季 AI 漫剧的批量生产管理。
- `Film Visual QA` 现在由 OpenCV 基线、InsightFace 身份一致性和 CLIP 语义匹配组成；高级后端采用懒加载可选依赖，不会阻断生成任务。
- 当前系统是工业级生产工作流/状态闭环，成片达到电影级审美仍依赖视频模型、角色素材、场景素材、审片规则和后续剪辑/合成增强。

## 本轮验证记录

- 后端 Film Engine API/项目上下文/视觉 QA 定向测试：`cd backend && uv run python -m pytest tests/test_visual_qa.py tests/test_film_engine_api.py -q -s`，11 passed。
- 根级 Film Engine 闭环测试：`uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_closed_loop_production.py tests/test_luminai_runtime_entrypoint.py tests/test_jellyfish_base_status.py -q -s`，10 passed。
- 前端类型检查：`cd front && ./node_modules/.bin/tsc --noEmit`，passed。
- 差异空白检查：`git diff --check`，passed。
- 语法检查：`cd backend && uv run python -m compileall app/services/film/visual_qa.py app/services/film/engine_state.py app/services/film/generated_video.py`，passed。
- OpenAPI 路由：代码层已确认 `/api/v1/film/engine/qa/evaluate-shot`、`/api/v1/film/engine/retry-task` 和 `/api/v1/film/engine/series-index` 均注册。
- 项目级 Film Engine 配置：已验证配置写入 `Project.stats.film_engine_config`，且 `qa_threshold`、`auto_retry`、`retry_limit` 参与计划计算。
- 真实章节上下文：已验证 Project/Chapter/Shot/Scene/Character 可构建 render requests、QA reports、workflow status；部分镜头生成时 Final Export 保持 Pending。
- 多集上下文：已验证 `series-index` 可聚合章节、镜头、生成视频、QA、Retry 和下一步动作。
- Film Visual QA：已验证 OpenCV `lighting_similarity`、InsightFace 风格 `face_similarity`、CLIP 风格语义 `clip_score` 可进入 `film_engine_qa_metrics`。
- Retry 真实任务：已验证 Film Engine Retry 请求可创建 `video_generation` 任务并关联回镜头。
- 模型适配层：`uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_model_adapter_layer.py tests/test_workflow_control.py tests/test_text_to_drama_pipeline.py -q -s`，6 passed。
- Text-to-Drama API：`cd backend && uv run python -m pytest tests/test_film_engine_api.py -q -s`，9 passed。
- 轻量 server 与既有闭环回归：`uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_closed_loop_production.py tests/test_luminai_runtime_entrypoint.py tests/test_jellyfish_base_status.py -q -s`，11 passed。
- 本轮采集 API/Film Engine API：`cd backend && uv run python -m pytest tests/test_film_engine_api.py -q -s`，11 passed。
- 本轮根级闭环回归：`uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_model_adapter_layer.py tests/test_workflow_control.py tests/test_text_to_drama_pipeline.py tests/test_closed_loop_production.py tests/test_luminai_runtime_entrypoint.py tests/test_jellyfish_base_status.py -q -s`，17 passed。
- 本轮前端类型检查：`cd front && ./node_modules/.bin/tsc --noEmit`，passed。
- 本轮语法检查：`cd backend && uv run python -m compileall app/services/film/stock_assets.py app/api/v1/routes/film/engine.py`，passed。
- 本轮运行验证：后端 `http://127.0.0.1:8000/health` 返回 ok，前端 `http://127.0.0.1:7788/film-engine` 返回 Vite 页面，`POST /api/v1/film/engine/stock-assets/collect` 返回 2 图 1 视频兜底素材。
- 重启后端口核验：`ss -ltnp | rg ':(7788|8000)\b' || true` 初始无监听，问题原因是电脑重启后服务未恢复。
- 重启后服务恢复：`cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` 与 `cd front && ./node_modules/.bin/vite --host 0.0.0.0 --port 7788` 均已启动。
- 重启后现场 API 验收：`curl --noproxy '*' -sSf http://127.0.0.1:8000/health` 返回 `status=ok`；`GET /api/v1/film/engine/stage-index` 返回 `code=200` 且 `all_stages_done=true`。
- 重启后前端验收：`curl --noproxy '*' -sSf http://127.0.0.1:7788/film-engine` 返回 Vite SPA 页面，可直接打开 `http://127.0.0.1:7788/film-engine`。
- 重启后素材采集验收：`POST /api/v1/film/engine/stock-assets/collect` 使用 `persist=false,image_count=2,video_count=1` 返回 3 个 Wikimedia Commons 线上素材引用，含图片、视频、缩略图和许可证页。
- 重启后后端 Film Engine/Visual QA 定向测试：`cd backend && uv run python -m pytest tests/test_visual_qa.py tests/test_film_engine_api.py -q -s`，14 passed。
- 重启后根级 Film Engine 闭环回归：`uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_model_adapter_layer.py tests/test_workflow_control.py tests/test_text_to_drama_pipeline.py tests/test_closed_loop_production.py tests/test_luminai_runtime_entrypoint.py tests/test_jellyfish_base_status.py -q -s`，17 passed。
- 重启后前端类型检查：`cd front && ./node_modules/.bin/tsc --noEmit`，passed。
- 重启后语法检查：`cd backend && uv run python -m compileall app/services/film/stock_assets.py app/api/v1/routes/film/engine.py`，passed。
- 空白检查：`git diff --check`，passed。
- 说明：本轮已重新启动 uvicorn 和 Vite 做运行验证；Celery 未启动。

## 中断恢复流程

1. 运行 `git status --short`，确认用户已有改动，不回退。
2. 后端：`cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`。
3. 前端：`cd front && ./node_modules/.bin/vite --host 0.0.0.0 --port 7788`。
4. 验证 API：`curl --noproxy '*' -sSf http://127.0.0.1:8000/api/v1/film/engine/stage-index`。
5. 验证前端：
   - 全局验收页：打开 `http://localhost:7788/film-engine`。
   - 项目内流程页：打开 `/projects/{projectId}?tab=film-engine&chapter={chapterId}`。
6. 验证测试：
   - `cd backend && uv run python -m pytest tests/test_visual_qa.py tests/test_film_engine_api.py -q -s`
   - `uv run --project backend python -m pytest --rootdir=/mnt/d/workplace/CineForge -o testpaths= tests/test_closed_loop_production.py tests/test_luminai_runtime_entrypoint.py tests/test_jellyfish_base_status.py -q -s`
   - `cd front && ./node_modules/.bin/tsc --noEmit`

## 下一步建议

- 在生产镜像中安装并缓存真实 InsightFace/CLIP 模型权重，按题材校准 `face_similarity` 与语义 `clip_score` 阈值。
- 增加真实样片集回归测试，覆盖真人、动漫脸、多人同框、无脸远景和动作复杂镜头。
- 将 Final Export 接入真实剪辑/合成任务，而不是仅返回规划路径。
