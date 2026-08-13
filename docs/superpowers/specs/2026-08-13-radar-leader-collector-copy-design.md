# 雷达/龙头空行情文案去 collect_quotes

日期：2026-08-13  
状态：已批准（方案 A：直接替换；短文案）

## 背景

独立演进 #1 收口已改 `engine` / `pattern_screen` 等 API detail，但雷达合成路径仍写「请先 collect_quotes」：

- `radar._synth_change_top` → `empty_message`
- `leader_screen.synth_leader_pick_rows` → 返回的 empty_message

与 zak2 自有 `quote-collector` 定位不符。

## 目标

1. 两处用户可见空行情文案改为短版引导 collector。  
2. 单测锁定；活代码用户消息不再出现「请先 collect_quotes」。

## 非目标

- 不改 `ops_catalog` / 调度里的 job_id `collect_quotes`（进程型任务名）。  
- 不统一为 #1 收口的长文案（含 `python -m ...`）。  
- 不改 engine/pattern 已有长文案。  
- 不强制更新路线图编号（可选：本刀仅代码+测；文档可在 commit message / smoke 一行带过，或省略）。

## 文案

统一为：

```text
行情快照为空，请启动 quote-collector
```

## 测试

- 覆盖 `_synth_change_top` 或等价路径、以及 `synth_leader_pick_rows`：空行情时 message 含 `quote-collector`，不含 `collect_quotes`。  
- `rg`：`backend/app/services` 用户文案路径无「请先 collect_quotes」（job_id / 测试夹具除外）。

## 验收

- [ ] 两处已替换  
- [ ] 相关 pytest 绿  
- [ ] 用户可见串无「请先 collect_quotes」

## 风险

前端若硬编码匹配旧 empty_message：当前无匹配；改为展示后端字段即可。
