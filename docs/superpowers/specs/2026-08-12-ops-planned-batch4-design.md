# Ops planned 第四批：概念预拉 / 关注池 1m（诚实 skipped 壳）设计

日期：2026-08-12  
状态：已批准（方案 A：两独立 skipped 壳 + RUNNABLE；enabled 默认 false）  
范围：仅 zak2；不改 zak / vnpy-*；catalog 自此无 planned job

## 背景

第三批后仍剩 2 个 planned。本刀全部升级为诚实 skipped 壳（用户选深度 1、方案 A）：

1. `prefetch_concept_board`  
2. `fill_focus_pool_minute`  

zak 侧 concept 为同花顺 ths 预热（多为内存映射）；1m 依赖分钟下载与关注池管线。zak2 尚无对等落点 / 1m 下载实现，本刀**不写入**真实数据。

## 目标

1. 两 job 升级为 **RUNNABLE**：Ops 可手动执行；`DEFAULT_CRON` 展示，**enabled 默认 false**。  
2. **诚实 skipped 壳**：明确 message；`save_job_run_meta(last_success=False)`；不写概念缓存、不写 1m K。  
3. JobSpec / roadmap / smoke 标明缺口；**catalog 中不再有 planned id**；planned 守卫测试改为 mock `job_kind_for`。

## 非目标

- 真拉 ths_index / ths_daily / ths_member 或新建概念表  
- 真下关注池 1m K / 移植 `focus_pool_minute`  
- 默认启用定时；改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 结构 | 每 job 一服务模块 + `ops_runners`（方案 A） |
| 行为 | 恒 skipped（本刀无真跑分支） |
| 定时 | 有 DEFAULT_CRON；enabled 默认 false |
| planned 测试 | mock `job_kind_for=="planned"`；断言 catalog 无 planned |

---

## 1. Job 行为

### 1.1 `prefetch_concept_board`

- **行为**：不拉 Tushare、不写任何概念缓存表。  
- **返回**：`{success: False, skipped: True, message: "zak2 尚未接入同花顺概念预热落点，无法预拉 concept board"}`（文案可微调，语义不变）。  
- **meta**：`save_job_run_meta(..., last_success=False)`。  
- **Cron**：`{"hour": 17, "minute": 30, "day_of_week": "mon-fri"}`

### 1.2 `fill_focus_pool_minute`

- **行为**：不下载、不写 `public.dbbardata` 分钟线。  
- **返回**：`{success: False, skipped: True, message: "zak2 尚未接入关注池 1m K 补全管线"}`。  
- **meta**：`save_job_run_meta(..., last_success=False)`。  
- **Cron**：`{"hour": 19, "minute": 0, "day_of_week": "mon-fri"}`

---

## 2. 模块与注册

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_prefetch_concept_board.py` | concept skipped 壳 |
| `backend/app/services/ops_fill_focus_pool_minute.py` | 1m skipped 壳 |
| `ops_catalog.py` | RUNNABLE + JobSpec 注明占位 skipped |
| `ops_runners.py` | 映射 |
| `scheduler_defaults.py` | DEFAULT_CRON |
| `tests/test_ops_prefetch_concept_board.py` | skipped + meta |
| `tests/test_ops_fill_focus_pool_minute.py` | skipped + meta |
| `tests/test_ops_job_kind.py` | 两 id runnable；catalog 无 planned（或等价断言） |
| `tests/test_ops_job_guards.py` | planned 守卫改 mock `job_kind_for`（不再依赖真实 planned id） |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

## 3. 验收

1. 两 job `job_kind_for(...) == "runnable"`；RUNNERS 覆盖；DEFAULT_CRON 有键。  
2. `job_kind_for` 对全部 `JOB_SPECS` 无 `"planned"`（仅剩 process + runnable）。  
3. 单测：恒 skipped + meta；guards 在 mock planned 下仍拒绝启用。  
4. `./scripts/check.sh` 通过。  
5. Ops 手动跑可见明确 skipped 文案。

## 明确不做（复述）

ths 真拉；1m 真下；策略/展望真算（第三批已占位）；双写桌面；下单；自动默认启用定时。
