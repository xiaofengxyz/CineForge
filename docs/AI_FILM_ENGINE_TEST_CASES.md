# AI Film Engine Test Cases

## 核心闭环

- `tests/test_closed_loop_production.py`
  - 验证 Jellyfish → Film Core → Prompt Compiler → Runtime → QA → Retry → Final Export 的顺序。
  - 验证角色参考、场景参考、负向词、QA 失败、Retry 参数。

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

