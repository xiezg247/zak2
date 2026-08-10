# 其余内置 Skill 只读 skill.py 补全设计

日期：2026-08-10  
状态：已批准（方案 A：抽 `ai_read_tools` 共享；跳过 notes）  
范围：仅 zak2；不改 zak；不改 skill_runtime 超时语义

## 目标

1. 为 `watchlist` / `screener` / `radar` 增加只读 `skill.py`，经现有 `run_skill` 可执行。  
2. 抽出 `ai_read_tools`，供 `ai_tools` 与 skill 共用，消除与 `_get_*` / `market-emotion` 重复。  
3. `market-emotion/skill.py` 改走同一 helper。

## 非目标

- `notes` 的 `skill.py` 或只读 notes 工具（另刀）  
- 写操作经 skill / 进 `WRITE_TOOL_NAMES`  
- 新增 Agent 工具名（仍用 `run_skill`）  
- 改 `skill_runtime` 超时 / 沙箱  
- 改 zak / 桌面 skill  

## 共享模块

新建 `backend/app/services/ai_read_tools.py`：

| 函数 | 签名 | 行为 |
|------|------|------|
| `get_watchlist` | `(db, user_id, args) -> dict` | 原 `_get_watchlist` |
| `get_market_emotion` | `(db, user_id, args) -> dict` | 原 `_get_market_emotion` |
| `get_recent_screening` | `(db, user_id, args) -> dict` | 原 `_get_recent_screening` |
| `get_radar_snapshot` | `(db, user_id, args) -> dict` | 原 `_get_radar_snapshot` |

`ai_tools` 中对应 `_get_*` 改为调用上述函数；工具名与 schema 不变。

## skill.py

| 目录 | `run(ctx, args)` |
|------|------------------|
| `watchlist` | `ai_read_tools.get_watchlist(ctx.db, ctx.user_id, args)` |
| `screener` | `get_recent_screening(...)` |
| `radar` | `get_radar_snapshot(...)` |
| `market-emotion` | 改为 `get_market_emotion(...)` |

参数透传：与现有只读工具相同（如 `limit`、`with_quotes`、`card_id`、`max_rows`、`top_n`）。

各 `SKILL.md`（watchlist / screener / radar）工具表增加 `run_skill` 行；market-emotion 已有可保留。

## 测试

- 抽 helper 后：既有 `ai_tools` / skills catalog 相关测仍绿  
- `list_skills`：`watchlist`/`screener`/`radar`/`market-emotion` 的 `runnable=True`；`notes` 仍 `False`  
- 各新 skill：mock `ai_read_tools` 或集成 mock 底层，断言 `run_skill` / `run_skill_module` 成功路径  
- 不打真网  

## 文档

- `docs/gap-vs-desktop.md`：Skills 行注明四 skill 可 run；notes 仍无  
- 「建议下一刀」：notes 只读 + skill，或 B 站 / Docker  
- `docs/smoke-checklist.md`：补 runnable skill 的 `run_skill` 验收（可合并一条）  

## 验收

1. 四 skill `runnable=True`；notes `False`  
2. `run_skill` 对 watchlist/screener/radar 返回形与对应只读工具一致  
3. 原 `get_watchlist` 等工具行为不变  
4. 相关 pytest 绿  
