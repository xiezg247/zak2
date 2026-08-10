# 情绪周期加深（全局阈值 + 短 TTL 缓存 + warm）设计

日期：2026-08-07  
状态：已批准（方案 1 + 存储方案 C：全局 meta）  
范围：仅 zak2；不改 zak；非桌面全量 SentimentService

## 目标

1. **全局可调阈值**：写入 `app.meta`，字段对齐桌面 `EmotionCycleThresholds` / 现有 `Thresholds`  
2. **短 TTL 缓存** + 可跑 `warm_market_summary` 预热  
3. Market 页可编辑阈值；Ops 可预热

## 非目标

- 按用户偏好（`auth.user_preferences emotion/thresholds`）  
- 断板率 / limit_list 输入加深  
- TickFlow / 桌面完整设置 Tab  
- 改 zak

## 阈值

- meta 键：`emotion_cycle_thresholds`（JSON）  
- `load_thresholds(db) -> Thresholds`：与默认合并；未知键忽略  
- `save_thresholds(db, partial|full)`：夹逼校验后整份写入  
- `reset_thresholds(db)`：删除 meta 键或写回默认  

字段（与现有 dataclass 一致）：  
`recession_limit_down, ice_max_boards, ice_limit_down, ice_up_ratio_max, climax_ladder_depth, climax_limit_up, divergence_limit_up_min, divergence_limit_spread, startup_max_boards, startup_limit_up, amount_floor_yuan, recession_break_rate, fear_greed_overheat, hysteresis_enabled`

API：
- `GET /api/v1/market/emotion-cycle/thresholds` → 当前生效值 + `is_default: bool`  
- `PUT /api/v1/market/emotion-cycle/thresholds` → body 同上字段（可部分）；保存后 **失效缓存**  
- `POST /api/v1/market/emotion-cycle/thresholds/reset` → 恢复默认并失效缓存  

`build_emotion_cycle(db, *, force: bool = False)` 使用 `load_thresholds`。

## 缓存

- 键：`zak2:emotion_cycle:v1`（Redis 若可用）+ 进程内兜底  
- TTL：env `EMOTION_CYCLE_CACHE_TTL_SEC`，默认 **60**  
- 读：未 force 且未过期 → 直接返回缓存快照  
- 写/失效：warm 成功写入；PUT/reset thresholds → invalidate  
- overview / GET emotion-cycle / leader_screen / team_prefetch 共用读路径  

## Job `warm_market_summary`

- 实现：`force` 重算 → 写缓存 → `save_job_run_meta`  
- 返回：`success, message, stage, stage_label, source`  
- `RUNNABLE` + `DEFAULT_CRON`：交易日 **09:25**（开盘前预热；可调）  
- catalog 描述：情绪周期预热写入短 TTL 缓存  

## 前端

**MarketView**
- 情绪卡片下方可折叠「判定阈值」：主要数字字段 + 保存 + 恢复默认  
- 保存成功后刷新 overview / emotion-cycle  

**OpsView**
- `warm_market_summary` 随 RUNNABLE 可跑；可选快捷「预热情绪周期」  

## 测试

- thresholds load/save/reset/merge  
- cache hit / miss / invalidate on save  
- warm job mock  
- classify 仍覆盖（注入 thresholds）  
- 不打真网  

## 文档

- gap：情绪周期 → 全局可调阈值 + 短 TTL 缓存 + warm（仍薄于桌面 SentimentService）  
- smoke：Market 可改阈值；Ops 可预热  

## 验收

1. 改阈值保存后生效（缓存已失效）  
2. warm / 读可走缓存；TTL 内重复读不重算（单测可验证）  
3. pytest + `npm run build` 绿  
