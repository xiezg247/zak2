# zak2 联调清单

本地验证 zak2 独立实例（自有 PG/Redis）。勾选即记。

## 0. 前置

- [ ] `cd backend && uv run alembic upgrade head` 已执行，`alembic_version` 为最新
- [ ] `.env` 已从 `.env.example` 复制，`DATABASE_URL` / `JWT_SECRET` 指向 zak2 自有库
- [ ] （可选）从旧 zak 库导入：`scripts/import_from_zak.py` 后可登录
- [ ] （可选）Redis 有行情：启动 `python -m app.quote_collector`（或 `./scripts/quote_collector.sh`）；本实例内勿多开 collector
- [ ] （可选）collector 运行后 `redis-cli GET zak2:meta:quote_count` 有数值（Compose 宿主机 Redis 为 `127.0.0.1:6380`）
- [ ] （可选）`TUSHARE_TOKEN` / `LLM_API_KEY` / `TICKFLOW_API_KEY` 已填
- [ ] （可选）内嵌调度：`EMBEDDED_SCHEDULER_ENABLED` / `BARS_SCHEDULER_ENABLED`；选股定时需 `SCHEDULER_SCREEN_USER_ID`；多 API 副本需 `REDIS_URL`（Redis job 锁防双跑；Redis 不可用或抢锁失败则跳过该次定时）

## 1. 启动

```bash
# 方式 A：一键
./scripts/dev.sh

# 方式 B：分终端
cd backend && uv run uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

- [ ] （可选）`docker compose up --build` 后 http://127.0.0.1:8080 可登录（API 文档 http://127.0.0.1:8001/docs；PG/Redis 宿主机 5433/6380）

## 2. 鉴权

- [ ] 登录成功（新建用户或导入后原账号）
- [ ] 刷新页面仍保持登录（token）
- [ ] 错误密码有明确提示

## 3. 自选 · 行情

- [ ] `/watchlist` 列表可读；增删一只自选；底部**策略看盘**可读；看盘上方**仓位与风控**卡片可改总资金/止损%/浮亏警戒并保存，可见实际仓位占比、计划外数量、计划日；风控与通知之间可见**当日计划**（空态或三态标签；点行可选中）；风控下方可展开**通知历史**（条目或空态；点行可看 payload）；**持仓可录入/改/删**（须先自选）；持仓区可见**风险**列（含「计划外」等 tag，计划外行可高亮）；**信号名单可增删**（上限 10）；有 Redis notify 时 WS 可触发刷新
- [ ] Ops 已同步行业映射后，自选列表「行业」列在 Redis 缺 `industry` 时仍可见行业名
- [ ] 有 Redis 时行情字段非空；点选见蜡烛图；点信号行可联动 K 线
- [ ] `/market` 排行点选可联动（有行情时）；顶部有**情绪周期**卡片；可展开**判定阈值**→ 改字段保存 / 恢复默认后阶段或警告变化；WS 连通时文案为「WS+慢轮询」

## 4. 选股 Hub

- [ ] 条件：涨幅榜 / 自定义区间 / 硬过滤切换后命中数变化
- [ ] Preset：涨停股（需 Redis）；低 PE / 中大盘（需 Tushare）
- [ ] 配方：盘中多因子、盘后多因子、**超短统一**、**雷达龙头**；**形态**六类（含平台突破/回踩 MA20）；**对标**五维权重、输入标杆代码可跑（需 Tushare）；任意结果行点「**找同类**」→ 切对标 Tab 并以该行代码自动跑
- [ ] 先 Ops **同步行业映射**（`sync_stock_industry`）；Redis 行情缺 `industry` 时，配方/雷达龙头结果列可见行业名（硬过滤「允许行业」可命中补全后的名）
- [ ] 硬过滤模板下方可展开**行业白名单勾选**（读 `GET /screener/industries`）；未同步映射时空列表提示去 Ops 同步；勾选 1～2 个行业后跑条件/配方 → 结果列行业落在白名单内；**全不勾选**时命中数与仅选模板时一致
- [ ] 勾选行业后**保存方案** → 刷新 → **加载复跑**仍保留勾选；取消全部勾选再跑与未限制时一致
- [ ] 盘中/盘后/超短 **因子权重**：配方 Tab 可改权重 → 保存后刷新仍保留 →「恢复默认」回到内置比例 → 再跑选股（排序可相对变化）
- [ ] 保存方案 → 刷新 → 加载复跑
- [ ] 历史出现记录；CSV 可下

## 5. 市场 · 板块 · 雷达

- [ ] `/market` 情绪周期 + 连板摘要（有 Redis/梯队时）；阈值保存后 overview 刷新仍生效
- [ ] `/sectors` 有日期与资金表（可先 Ops 同步板块资金）
- [ ] `/radar` 有卡片与**共振侧栏**；明细/共振有封板时刻时显示「HH:MM 封板」；「龙头选股 → Hub」跳转正确；冰点/退潮时龙头空池提示合理
- [ ] `/radar` **共振权重**：侧栏可展开编辑各卡权重 → 保存后共振分数/排序变化 → 刷新页面仍保留 →「恢复默认」清空自定义
- [ ] Hub 可跑「**雷达共振**」并见历史
- [ ] `/radar` 明细对多卡共振标的显示 ★
- [ ] 「**共振选股 → Hub**」跳转 `recipe=radar_resonance`
- [ ] Hub **雷达龙头**结果：连板旁或形态说明可见封板时刻（需先同步涨停列表）
- [ ] `/radar`「**生成次日计划草案**」可写 draft；成功提示含「去守则看计划」→ Playbook 可见 draft
- [ ] 冰点/退潮或无共振时生成失败，文案明确（如「当前情绪不宜新开（冰点/退潮）」「暂无雷达卡片…」「暂无共振标的」）
- [ ] 同日再点「生成次日计划草案」覆盖已有 draft（提示含「已覆盖」）

## 6. 内容 · 回测 · AI · 运维

- [ ] `/playbook` 章节可读、纪律可勾
- [ ] `/notes` 备忘/流水可写；**研报 Tab** 可看团队落库（`?symbol=&report=` 可直达）
- [ ] `/feed` 时间线可读；左侧输入 **mid** →「添加」可新增 UP 订阅（无 `BILIBILI_COOKIES` 时 400 提示明确）；**关键词搜索** → 结果点「添加」走现有添加路径（可勾选「并同步」）；勾选「并同步」可立即拉动态（失败仍保留订阅，页内提示 `sync_error`）；每行「删」confirm 后订阅及条目移除；配置 Cookie 后 Ops 跑 `sync_bilibili_feed` 可见新条目（无 Cookie / 无启用订阅时 skipped）；亦可 `pytest backend/tests/test_bilibili_user_search.py backend/tests/test_feed_search.py backend/tests/test_feed_subscriptions.py`
- [ ] `/backtest` 对有日 K 的票跑通双均线
- [ ] `/ai` 流式回复；写操作确认卡；可提议 `upsert_position` / `delete_position` / `add_signal_panel` / `remove_signal_panel`，确认卡后落库（缺自选时 upsert 应失败）；**团队分析**快速/深度；结束后可「研报已保存」并跳转笔记；Agent 可调用 `list_skills` / `read_skill` 加载内置 Skill 说明（亦可 `pytest backend/tests/test_ai_write_positions.py backend/tests/test_ai_tools_skills.py backend/tests/test_skills_catalog.py` 单测覆盖）
- [ ] Agent / 工具：`list_note_symbols` / `get_stock_notes` 只读可用；`run_skill` 对 watchlist / screener / radar / market-emotion / **notes** 可用（只读；emotion 需情绪数据或可接受空结构；notes 无 vt_symbol 列符号、有则读备忘+流水；亦可 `pytest backend/tests/test_ai_read_tools.py backend/tests/test_skills_catalog.py backend/tests/test_ai_tools_skills.py` 单测覆盖）
- [ ] `/ops` 健康绿（含 `scheduler_lock`；**行情采集**卡片可见 running/hint；「强制采一轮」在 collector 未启动时文案明确，启动后可触发）；MCP 未启用显示「未启用」；启用且 URL 正确显示「已连接」）；可跑清理 cache / 盘中或盘后选股（需行情）；可跑 **`sync_limit_list`**（需 Tushare token；写入当日涨停列表/封板时刻）；可提交**同步 A 股列表**（`sync_universe`）；可提交**同步行业映射**（`sync_stock_industry` → `app.stock_industry`，需 Tushare token；申万空则回退 stock_basic）；可快捷**预热情绪周期**（`warm_market_summary`，写入短 TTL 缓存）；可快捷**B站订阅同步**（`sync_bilibili_feed`，需 `BILIBILI_COOKIES`）；无 token / 空结果有明确失败文案
- [ ] （可选）配置 `MCP_ENABLED` + `MCP_URL` 后，`/ops` MCP 卡片为已连接；AI 可调用 `mcp_diagnose_*` 只读工具；`GET /api/v1/ops/mcp/tools` 可列白名单
- [ ] `/ops` 定时任务：可开关全部可跑 job（含 cache/日历/板块/涨停/universe/**sync_stock_industry**/日 K/选股/**warm_market_summary**/**sync_bilibili_feed**）；任务表可见 `sync_bilibili_feed` 开关；cron 只读展示（universe 默认周一 08:00；**stock_industry 默认周一 08:15**；warm 默认工作日 09:25；**bilibili 默认工作日 8–19 点每小时 :15**）；日 K「补全自选」/「补全过期」/「全市场日 K 首下」可提交（需 token；首下另需 app.universe，可先同步 A 股列表）；无 universe / 无 token 有明确失败文案；overview 不再提示仅 CLI
- [ ] （可选）配置 `SCHEDULER_SCREEN_USER_ID` 后，盘中/盘后选股定时可写入该用户 `screener_runs`（未配置则跳过选股定时）

## 7. 自动化冒烟

```bash
./scripts/check.sh
```

- [ ] pytest 全绿
- [ ] `npm run build` 通过

---

失败时优先查：`.env` 库址、Redis 是否空、Tushare 积分、浏览器 Network 里 `/api` 是否 401/502。

[产品路线](./product-roadmap.md) · [归档缺口对照](./archive/gap-vs-desktop.md)
