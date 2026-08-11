# zak2 ↔ zak 桌面能力缺口对照

> 以当前 zak2 代码为准；桌面以 `packages/vnpy-*` + `docs/` 为准。  
> 更新节奏：每完成一轮增强后改本表。

图例：**有** = Web 可用（可简化） · **薄** = 子集/近似 · **无** = 基本未做 · **CLI** = 仍靠 zak CLI/桌面

---

## 总览

| 域 | zak2 | 相对桌面 |
|----|------|----------|
| 登录 / JWT | **有** | 共用 `auth.users` |
| 选股 Hub | **有**（薄） | 条件/配方/形态/对标已齐；盘中/盘后/超短可编辑权重 |
| 自选 | **有**（薄） | 策略看盘 + 持仓录入 + 信号名单 Web 编辑 |
| 市场 / 板块 / 雷达 | **有**（薄） | 情绪周期/选龙头为近似；Hub 雷达共振可落历史；可生成次日 draft；仍无激活/编辑 |
| 守则 / 笔记 / 信息流 | **有**（薄） | 计划只读；自选可见当日计划对照；B 站动态 Web 可同步（需 Cookie）；Feed 可按 mid 添加/删除 UP（可选立即同步）；亦可关键词搜索 UP 后点选添加 |
| 回测 | **薄** | 仅双均线 ≠ vnpy CTA |
| AI | **薄** | 单 Agent + 团队 + 写确认卡 + Web 研报落库；MCP Streamable HTTP 诊断工具 |
| 运维 | **薄** | 可跑 job 已内嵌定时（含 Web `sync_universe` / `sync_stock_industry` / `sync_bilibili_feed`）；不可跑仍 CLI |
| 风控通知 / 交易链路 | **薄** | 计划外 + trading/risk 偏好与仓位占比；自选可见计划标的对照；有通知历史只读；无下单 |
| 行情采集常驻 | **有**（薄） | zak2 `quote-collector`（TickFlow→Redis 键兼容）；无 enrich/L1；与 zak CLI 采集互斥 |

---

## 选股

| 能力 | zak2 | 备注 |
|------|------|------|
| 条件 preset（涨幅/换手/量比/成交量/自定义） | **有** | |
| 涨停股 / 低 PE / 中大盘 / 主力净流入 | **有** | Tushare 依赖 token/积分 |
| 硬过滤模板 + 方案保存复跑 | **有** | Redis 行业为空时硬过滤前读 `app.stock_industry` 补全；Hub 可勾选行业白名单（`GET /screener/industries` + 与模板 merge） |
| 盘中/盘后/超短多因子配方 | **有** | 简化打分；Hub 可编辑因子权重（按用户 meta）；缺 Redis 行业时可补全 |
| 雷达龙头配方 | **有** | 简化 `leader_score`；情绪周期五阶段 gate；候选池硬过滤前可补空行业 |
| 形态 / 对标 | **薄** | 六形态（含平台突破/回踩 MA20）+ 五维标杆对标（同业/估值/5·20 日动量/换手，Tushare）；Hub 结果行「找同类」；未扩全桌面因子库 |
| 自动选股 cron | **薄** | Web 内嵌可定时（需 SCHEDULER_SCREEN_USER_ID）；亦可手动跑 |

## 看盘

| 能力 | zak2 | 备注 |
|------|------|------|
| 自选 CRUD / 分组 / Redis enrich | **有** | Redis 空行业时 list/quotes 读 `app.stock_industry`；前端列表「行业」列 |
| 日 K 蜡烛图 | **有** | SVG 轻量 |
| 日 K Web 补全 | **有**（薄） | 自选 + 全市场过期 + 全市场首下（单次上限）；`app.universe` 可由 Web `sync_universe` 同步（Tushare，非 TickFlow）；Tushare daily |
| 15s 刷新 / 排行联动 | **有** | |
| 策略看盘（信号/持仓只读） | **有** | 读 Redis/PG cache + `watchlist_positions`；持仓区 risk tag（含「计划外」）+ `risk_summary` |
| 仓位与风控偏好 | **有**（薄） | 自选页卡片读写 `trading/risk`；展示实际仓位占比 / 计划外数 / 计划日 |
| 当日计划对照 | **有**（薄） | `risk_summary.plan_symbols`；自选/持仓/仅计划三态；只读 |
| 通知历史 | **有**（薄） | 自选页风控卡片下方可折叠只读；共用 `notify_delivery_log`；无发送/删日志 |
| 持仓 Web 录入 | **有** | CRUD 同表；须先自选、整手、上限 20 |
| 自选信号名单编辑 | **有** | PG `signal_panel_symbols`；桌面本地偏好不同步（**不改 zak**，Web 自洽即可） |
| WebSocket 推送 | **有**（薄） | Redis notify → WS 推 seq；前端再拉 REST |

## 市场 · 板块 · 雷达

| 能力 | zak2 | 备注 |
|------|------|------|
| Redis 排行 / 连板情绪表 | **有** | |
| 情绪周期（五阶段） | **有**（薄） | 全局可调阈值（`app.meta`）+ 短 TTL 缓存 + `warm_market_summary` 预热；迟滞 + MA5 + 恐贪代理；非桌面全量 SentimentService |
| 板块资金日表 | **有** | Ops 可 sync |
| 雷达卡片（cache + 合成） | **有** | 含合成 leader_pick |
| 共振侧栏 | **有**（薄） | 跨卡共振；可调权重（按用户 meta）；Hub 配方 radar_resonance 可落 screener_runs；明细 ≥2 卡 ★ |
| 封板时间深度 | **有**（薄） | `limit_list_d` → PG；龙头/雷达/共振展示 `seal_time_label`；Ops `sync_limit_list` |

## AI · 运维 · 工程

| 能力 | zak2 | 备注 |
|------|------|------|
| 流式 chat + 只读工具 + 写操作确认卡 | **有** | 加/删自选、写备忘、记流水；持仓 upsert/delete、信号名单增删 |
| 投研团队编排（快速） | **有**（薄） | 预取+规则分+chief |
| 投研团队深度模式 | **有**（薄） | `mode=deep`；研报落 Web 自有表 |
| 写操作工具 / MCP / Skills 生态 | **薄** | 8 个写工具（原 4 + 持仓 upsert/delete、信号名单 add/remove）；MCP Streamable HTTP + diagnose 白名单；有内置 SKILL.md + list/read；薄 `run_skill`（同进程 + 软超时）：watchlist / screener / radar / market-emotion / notes 五 skill 可跑（notes 只读：list/get 或 skill 分流）；仍非桌面全量 Python registry |
| Web 投研研报 | **有**（薄） | `app.web_team_reports`；与桌面表分开 |
| 健康面板 / 调度开关 / 可跑 sync | **有** | 含 `sync_universe` / `sync_stock_industry`；健康含 quote_collector 心跳；可强制采一轮 |
| 内嵌 APScheduler / Redis job 锁 | **薄** | 覆盖全部可跑 job（cache/日历/板块/涨停/universe/行业映射/日 K/选股）；多副本经 Redis SET NX 防双跑；Redis 不可用则跳过定时 job（无选主） |
| 一键启动 / 验收脚本 / 本缺口表 | **有** | `scripts/` + 本文 |
| Docker 全家桶 | **薄** | `docker compose`：api+web+quote-collector；PG/Redis 用宿主机 zak |

---

## 范围约定

- **只改 zak2**（FastAPI + Vue），不调整 `zak` / `vnpy-*` 桌面代码。
- 与桌面「双端同步」类缺口（如信号名单本机偏好）**明确不做**；Web 侧自洽即可。
- 仍可**读**共用 PG/Redis；全市场行情由 zak2 **独立 collector 进程**写入（不进 API）；其它不可跑 job 仍可靠 CLI。

## 建议下一刀（非绑定，仅 zak2）

Tushare enrich 因子，或只读持仓/信号查询工具（`get_positions` / `get_signal_panel` 等）。

[联调清单](./smoke-checklist.md) · [架构 P1](./architecture-p1.md)
