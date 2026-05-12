# CineForge AI Film Engine 用户操作手册

更新时间：2026-05-12

## 1. Film Engine 怎么操作

Film Engine 不是单独的“输入一句话生成视频”页面，它嵌在 Jellyfish 工作台里，负责把项目、章节、分镜、角色、场景、参考图和生成任务组织成工业化闭环。

常用入口：

- 全局入口：左侧菜单 `Film Engine`，路由 `/film-engine`。
- 项目入口：项目工作台 `/projects/{projectId}?tab=film-engine`。
- 章节入口：项目工作台 Film Engine 标签页选择章节，或分镜列表顶部 `Film Engine` 按钮。
- API 入口：`/api/v1/film/engine/stage-index`、`/api/v1/film/engine/series-index`、`/api/v1/film/engine/config`、`/api/v1/film/engine/stock-assets/collect`。

Film Engine 页面主要做四件事：

- 配置项目级运行策略：运行时供应商、模型、参考帧策略、镜头焦段、QA 阈值、Retry 上限。
- 通过 `text-to-drama-plan` API 从一段文字生成 Novel Plan、资产、分镜和漫剧生产计划。
- 无基础素材时点击 `采集基础素材`，从免费图库补齐图片/视频参考。
- 查看当前章节九阶段证据：Runtime、Director DSL、Shot Graph、Prompt Compiler、角色/场景注册表、QA、Retry、Film State。
- 查看生产闭环：剧本拆解、分镜准备、资产一致性、状态连续性、提示词编译、运行时请求、QA、Retry、最终导出。
- 查看多集总览：每集镜头数、可规划镜头、已生成视频、QA 报告、Retry 数量和下一步动作。

## 2. 功能完成核验

| 能力 | 当前状态 | 说明 |
| --- | --- | --- |
| graph-based workflow | 已完成 | `WorkflowGraph` 固化章节生产链路，API 和前端均显示 workflow stages。 |
| ECS-inspired architecture | 已完成 | `EntityRegistry`、`Entity`、`Component` 管理资产边界。 |
| runtime abstraction | 已完成 | `RenderRequest` 与 `src/models/*` 解耦具体供应商。 |
| model adapter isolation | 已完成 | `ModelEndpointConfig` 支持 provider/model/base_url/api_key 注入，API 输出默认脱敏。 |
| prompt compiler architecture | 已完成 | `PromptCompiler` 从结构化导演 DSL 和连续性状态生成提示词。 |
| character consistency | 已完成 | `CharacterBible`、角色参考图、identity terms、negative terms 进入提示词和 QA 证据。 |
| shot continuity | 已完成 | `ShotContinuityState` 保存角色、场景、服装、情绪、光线、时间线和参考图。 |
| film state continuity | 已完成 | 分镜状态通过项目/章节/镜头上下文进入 Film Core。 |
| automatic QA | 已接入 Film Visual QA | 视频任务完成后会尝试用 OpenCV 生成 `lighting_similarity`，用 InsightFace 生成 `face_similarity`，用 CLIP 生成语义 `clip_score`；旧视频可在 Film Engine 页面点击 `Film QA` 重新评估。 |
| automatic retry | 已接入真实任务 | QA 失败会生成结构化 retry prompt 和 repair 参数，并可在页面点击 `Retry` 创建真实 `video_generation` 任务。 |
| industrial batch production | 已完成状态闭环 | 支持多集 series index、章节批量状态和分镜批量生成入口；真实生成仍通过章节 Studio 的任务系统执行。 |
| text-to-drama operating plan | 已完成 | `POST /api/v1/film/engine/text-to-drama-plan` 可从输入文字生成小说、资产、分镜、runtime、QA/Retry 和 handoff。 |
| stock asset bootstrap | 已完成 | `POST /api/v1/film/engine/stock-assets/collect` 可从 Wikimedia Commons 采集免费图片/视频引用，并可写入项目素材上下文。 |
| 页面 UI 操作 | 已完成 | Film Engine 已在全局菜单、项目工作台和章节分镜流程中可见。 |

结论：文档要求的核心 Film Engine 架构能力已经落地；页面 UI 不缺席。当前真实 QA 已从单一 OpenCV 基线升级为组合式 Film Visual QA：OpenCV 保底，InsightFace 检查角色脸部身份，CLIP 检查画面和剧情/提示词语义匹配。

## 3. 术语说明：QA、CV、OpenCV、InsightFace、CLIP

QA 是 Quality Assurance，意思是质量检查。在 CineForge 里，QA 不是普通测试人员手动看一眼，而是系统给每个生成视频生成结构化分数、失败原因和下一步返工建议。

CV 是 Computer Vision，意思是计算机视觉。它指用算法读取图片/视频画面，检查画面是否稳定、清晰、亮度是否一致、角色是否相似、画面和文本是否匹配等。

当前已接入的 Film Visual QA 由三层组成：

- OpenCV：部署稳、不需要 GPU，读取视频帧并产出 `lighting_similarity`；在 CLIP 不可用时也会产出基础画面可读性代理 `clip_score`。
- InsightFace：读取角色参考图和生成视频中的脸部，产出 `face_similarity`，用于判断角色是否像同一个人。
- CLIP：读取生成视频采样帧与镜头提示词/剧情文本，产出语义 `clip_score`，用于判断画面是否匹配剧情和提示词。

推荐路线：

- OpenCV 默认随项目安装，适合批量生产基础质检。
- InsightFace/CLIP 采用懒加载可选后端，适合在有 CPU/GPU 模型环境的部署镜像里启用。
- 如果 InsightFace 或 CLIP 依赖未安装，QA 不会中断生成任务，会在 `film_engine_visual_qa.details.components` 中记录 skipped reason。

## 4. 解决的行业痛点

- 角色漂移：角色参考图、身份词、负向词、服装状态进入统一 Character Bible，不再靠每次手写 prompt。
- 镜头不连续：每个镜头都有 `timeline_position`、场景、光线、情绪和参考媒体。
- Prompt 随机堆叠：提示词由 Director DSL 和 Film State 编译，不是散落在页面里的硬编码长句。
- 供应商绑定：Film Core 输出 provider-neutral render request，具体模型由 runtime adapter 执行。
- 批量生产不可控：多集总览能按章节显示卡点、已生成数量、QA/Retry 数量。
- 审片返工靠人工记忆：QA issue code 会转成 Retry 参数和修复提示词。
- 页面看不到引擎状态：Film Engine 页面展示九阶段、workflow、render requests、QA、Retry、导出状态。

## 5. 从零到一部多集 AI 漫剧

### 5.1 启动环境

后端：

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

说明：`uv sync` 会安装 `opencv-python-headless`，这是 Film Visual QA 的基础依赖。InsightFace/CLIP 属于可选模型后端，生产环境可按镜像策略额外安装 `insightface`、`onnxruntime`、`transformers`、`torch`、`pillow`，未安装时系统会保留 OpenCV 基线并记录 skipped reason。

前端：

```bash
cd front
pnpm install
pnpm dev --host 0.0.0.0
```

打开：

- 前端：`http://localhost:7788`
- 后端 Swagger：`http://localhost:8000/docs`

### 5.2 配置模型和运行时

1. 进入 `模型管理`。
2. 添加视频模型供应商，例如 Kling、Vidu、Wanx、OpenAI 或内部代理。
3. 设置默认视频模型，否则视频任务会被后端拒绝。
4. 在项目里设置默认视频比例，漫剧常用 `9:16`。
5. 在 Film Engine 配置里确认：
   - `运行时供应商`：如 `kling`。
   - `运行时模型`：如 `kling-v1`。
   - `参考帧策略`：首尾关键帧齐备时选 `first_last_key`；早期草稿可选 `text_only`。
   - `Director DSL 默认焦段`：常用 `35mm`，特写密集可用 `50mm` 或 `85mm`。
   - `QA 阈值`：默认 `0.75`；越高越严格。
   - `自动 Retry`：建议开启。
   - `自动重试上限`：建议 `1-3`。

如果通过 `text-to-drama-plan` API 直接做自动生产计划，可以在请求体里传入模型 endpoint：

```json
{
  "config": {
    "runtime_profiles": {
      "text": {"provider": "openai_compatible", "model": "text-planner", "base_url": "https://llm.example/v1", "api_key": "..."},
      "image": {"provider": "comfyui", "model": "storyboard-xl", "base_url": "https://image.example", "api_key": "..."},
      "video": {"provider": "kling", "model": "kling-v1", "base_url": "https://video.example", "api_key": "..."}
    }
  }
}
```

响应会显示 `api_key_configured=true`，不会返回明文 `api_key`。

### 5.3 创建项目

1. 进入项目列表，创建项目。
2. 填写项目名称、题材、画面风格、简介。
3. 选择是否统一风格；多集漫剧建议开启。
4. 设置项目默认视频比例。

项目创建后，进入项目工作台，先看 Dashboard，再进入 Film Engine 标签页确认项目配置。

### 5.4 创建多集章节

建议一个章节对应一集：

1. 在项目工作台创建第 1 集、第 2 集、第 3 集。
2. 每集粘贴原始剧本。
3. 对剧本做智能精简、优化、角色混淆检查。
4. 执行分镜提取，把剧本拆成镜头。

Film Engine 的 `series-index` 会按章节顺序聚合多集状态。某一集没有分镜时，下一步会提示 `提取分镜`。

### 5.5 确认角色、场景、道具、服装

进入每集分镜准备流程：

1. 查看系统提取的角色候选、场景候选、道具候选、服装候选。
2. 已存在的资产选择“关联”，不存在的资产创建新资产。
3. 上传或生成角色图、场景图、服装图。
4. 角色资产需要稳定描述：年龄、脸型、发型、服装、身份特征、负向词。
5. 场景资产需要稳定描述：地点、光线、天气、色调、氛围。

这些资产会进入 Character Registry 和 Scene Registry，是多集一致性的核心。

### 5.6 准备每个镜头

每个镜头至少需要：

- 标题和剧情摘要。
- 景别、机位、运镜、时长。
- 关联角色和场景。
- 动作拍点和情绪标签。
- 首帧、尾帧或关键帧提示词。
- 对应帧图片，或使用 `text_only` 模式先生成草稿视频。

镜头状态达到 `ready` 后，Film Engine 才会把它计为可规划镜头。

### 5.7 进入 Film Engine 检查章节

在项目工作台打开 `Film Engine`：

1. 选择当前章节。
2. 查看“九阶段证据”：如果有 Pending，查看证据列。
3. 查看“生产闭环 Workflow”：确认卡点在剧本、分镜、资产、生成、QA 还是导出。
4. 查看“镜头运行计划”：确认每个 render request 的 provider、model、prompt、reference 和 output path。
5. 对已有生成视频点击 `Film QA`，可重新评估并写回真实 CV/身份/语义指标。
6. 对有 Retry 请求的镜头点击 `Retry`，可创建真实二次渲染视频任务。
7. 查看“多集生产总览”：确认每集的生成数量和下一步。

### 5.7.1 无基础素材时采集图片/视频

在 Film Engine 页面点击 `采集基础素材`：

1. 如果当前在项目/章节上下文里，系统会从项目名称、描述、章节标题和章节文本推导搜索词。
2. 系统默认从 Wikimedia Commons 查询图片和视频素材。
3. 采集结果会显示缩略图、图片/视频类型、素材源和许可证页。
4. 在项目上下文里，采集到的远程素材会写入 `FileItem`，并通过 `FileUsage` 关联当前项目/章节。
5. 如果外部图库临时不可用，系统会使用稳定兜底素材返回结果，保证流程不中断。

### 5.8 批量生成

真实生成任务在章节 Studio 中执行：

1. 从 Film Engine 点击下一步，进入章节分镜 Studio。
2. 先批量检查视频准备度。
3. 对未通过准备度的镜头补齐时长、参考图、提示词或资产关联。
4. 批量生成关键帧/参考帧。
5. 再发起视频生成任务。
6. 到任务中心观察运行状态、失败原因和生成结果。

生成完成后，视频会写回镜头 `generated_video_file_id`，Film Engine 刷新后会进入 QA 阶段。

视频任务成功后，后端会自动尝试：

1. 下载生成视频。
2. 下载首帧/尾帧/关键帧参考图。
3. 用 OpenCV 采样视频帧并计算基础视觉指标。
4. 读取角色参考图，用 InsightFace 检查角色脸部一致性。
5. 读取镜头提示词/剧情文本，用 CLIP 检查画面语义匹配。
6. 将 `film_engine_visual_qa` 和 `film_engine_qa_metrics` 写入 `GenerationTask.result`。

如果对象存储、视频编码、OpenCV 解码或 InsightFace/CLIP 模型加载失败，生成任务不会被判失败；Film Engine 会记录 skipped 原因，并退回已可用的基线或稳定代理指标。

### 5.9 QA 与 Retry

Film Engine QA 的指标来源有两种：

- 真实任务指标：视频任务结果里写入 `qa_metrics` 或 `film_engine_qa_metrics`。当前 Film Visual QA 会自动写入 OpenCV、InsightFace、CLIP 可用指标。
- 稳定代理指标：没有真实 CV 指标时，根据角色参考、场景锁定、动作描述等生成可解释分数。

常见问题码：

- `low_face_similarity`：角色脸部相似度不足。
- `outfit_drift`：服装漂移。
- `lighting_mismatch`：光线或色调不一致。
- `weak_prompt_alignment`：画面和动作提示词不够贴合。

处理方式：

1. 在 Film Engine 查看 QA 报告和 Retry 请求。
2. 点击 `Film QA`，确认旧视频已经有真实视觉、脸部身份和语义匹配指标。
3. 点击 `Retry`，让系统用 retry prompt 创建真实视频任务。
4. 到任务中心观察任务状态。
5. 新结果写回后刷新 Film Engine。
6. 直到 QA passed 或人工接受风险。

### 5.10 后期导出

Film Engine 只有在当前章节所有可规划镜头都有生成视频后，才会把 Final Export 标为 Done。

后期导出流程：

1. 确认章节所有镜头都有视频。
2. 进入项目剪辑/Editor。
3. 按镜头顺序检查片段。
4. 补字幕、TTS、BGM、转场。
5. 导出单集成片。
6. 每集完成后，再进行整季交付。

### 5.11 多集生产建议

推荐节奏：

1. 第 1 集先跑完整闭环，确认角色、画风、镜头语言。
2. 冻结角色 Bible、场景 Bible、核心负向词。
3. 第 2 集开始批量推进分镜和资产关联。
4. 每天按 Film Engine 多集总览处理 Pending 最多的章节。
5. 每集导出前必须确认：可规划镜头数 = 已生成视频数，QA 无高危失败，Retry 数量可解释。

## 6. API 快速核验

内置验收样例：

```bash
curl --noproxy '*' -s http://127.0.0.1:8000/api/v1/film/engine/stage-index
```

项目章节状态：

```bash
curl --noproxy '*' -s "http://127.0.0.1:8000/api/v1/film/engine/stage-index?project_id=PROJECT_ID&chapter_id=CHAPTER_ID"
```

多集总览：

```bash
curl --noproxy '*' -s "http://127.0.0.1:8000/api/v1/film/engine/series-index?project_id=PROJECT_ID"
```

从一段文字生成小说到漫剧生产计划：

```bash
curl --noproxy '*' -s -X POST "http://127.0.0.1:8000/api/v1/film/engine/text-to-drama-plan" \
  -H "Content-Type: application/json" \
  -d '{
    "source_text":"Ari finds a key in a neon alley and chooses to save the city.",
    "title":"Neon Trial",
    "config":{
      "persist":true,
      "max_chapters":2,
      "shots_per_chapter":2,
      "stage_switches":{"novel_engine":{"enabled":true,"automatic":true}},
      "runtime_profiles":{"video":{"provider":"kling","model":"kling-v1","base_url":"https://video.example","api_key":"YOUR_KEY"}}
    }
  }'
```

人工审核某阶段：

```json
{
  "config": {
    "stage_switches": {
      "novel_engine": {"enabled": true, "automatic": false}
    }
  }
}
```

此时系统会生成小说计划并停在 `waiting_for_user`，后续资产、图片、视频、QA 阶段不会自动执行。

没有基础素材时采集免费图片/视频：

```bash
curl --noproxy '*' -s -X POST "http://127.0.0.1:8000/api/v1/film/engine/stock-assets/collect" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id":"PROJECT_ID",
    "chapter_id":"CHAPTER_ID",
    "query":"neon alley cinematic drama",
    "image_count":4,
    "video_count":2,
    "persist":true
  }'
```

读取配置：

```bash
curl --noproxy '*' -s "http://127.0.0.1:8000/api/v1/film/engine/config?project_id=PROJECT_ID"
```

更新配置：

```bash
curl --noproxy '*' -X PATCH "http://127.0.0.1:8000/api/v1/film/engine/config?project_id=PROJECT_ID" \
  -H "Content-Type: application/json" \
  -d '{"runtime_provider":"kling","runtime_model":"kling-v1","reference_mode":"first_last_key","qa_threshold":0.8,"retry_limit":2}'
```

Film Visual QA 重评估：

```bash
curl --noproxy '*' -s -X POST "http://127.0.0.1:8000/api/v1/film/engine/qa/evaluate-shot" \
  -H "Content-Type: application/json" \
  -d '{"shot_id":"SHOT_ID"}'
```

创建 Retry 视频任务：

```bash
curl --noproxy '*' -s -X POST "http://127.0.0.1:8000/api/v1/film/engine/retry-task" \
  -H "Content-Type: application/json" \
  -d '{"project_id":"PROJECT_ID","chapter_id":"CHAPTER_ID","shot_id":"SHOT_ID","ratio":"9:16"}'
```

## 7. 常见故障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| Film Engine 页面连接失败 | 后端未启动或前端 API base 配置错误 | 启动后端，检查 `VITE_API_BASE_URL` 或 runtime `env.js`。 |
| 九阶段 Pending | 当前项目证据不足 | 查看阶段证据列，按下一步按钮进入对应页面处理。 |
| render requests 为 0 | 章节没有可规划镜头 | 提取分镜，补 ShotDetail 时长和镜头语言。 |
| QA reports 为 0 | 还没有生成视频 | 先在章节 Studio 生成视频。 |
| Retry 为空但 QA failed | 自动 Retry 关闭或 retry_limit 为 0 | 打开 Film Engine 配置并保存。 |
| Film QA skipped | 对象存储下载失败、视频编码不可读、OpenCV 不可用，或 InsightFace/CLIP 可选模型未安装 | 运行 `cd backend && uv sync`，检查视频文件可下载；需要高级评估时在部署镜像中安装 InsightFace/CLIP 依赖。 |
| 点击 Retry 后任务创建失败 | 默认视频模型未设置、参考帧数量不匹配或 Celery/Redis 未启动 | 设置默认视频模型，补齐参考帧，启动 Celery worker。 |
| Final Export Pending | 不是所有可规划镜头都有视频 | 补齐未生成镜头。 |
| 视频任务无法创建 | 默认视频模型未设置或参考帧数量不匹配 | 到模型管理设置默认视频模型，或调整参考帧策略。 |
