# CineForge Codex Workflow Prompts

按顺序执行各阶段 Prompt。

## Stage Switch Contract

每个阶段都支持同一组开关：

- `enabled=true`：阶段参与本次 workflow。
- `enabled=false`：阶段跳过，状态记录为 `disabled`。
- `automatic=true`：阶段完成后自动进入下一个 enabled 阶段。
- `automatic=false`：阶段完成后记录为 `waiting_for_user`，后续阶段记录为 `blocked`，等待用户审核、修改或手动继续。

示例：

```json
{
  "stage_switches": {
    "novel_engine": {"enabled": true, "automatic": false},
    "asset_pipeline": {"enabled": true, "automatic": true},
    "video_runtime": {"enabled": true, "automatic": true}
  }
}
```

运行时代码以 `src/film_engine/workflow_control.py` 为准。
