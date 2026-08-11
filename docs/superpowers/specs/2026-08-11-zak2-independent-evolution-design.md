# zak2 独立演进总纲设计

日期：2026-08-11  
状态：已批准（方案 1：表形 fork + Redis 改前缀；基础设施现在拆库）  
范围：仅 zak2；不改 zak / vnpy-* 代码

## 背景与决策摘要

zak2 原以「共用 zak 的 PostgreSQL / Redis、Schema 主权在 zak Alembic、能力对照桌面缺口表」为主路径。现需 **单独演进**：运行时与产品路线不再绑桌面；基础设施默认自给。

| 项 | 决策 |
|----|------|
| 总纲范围 | Schema 主权 + 运行时自给 + 产品文档解绑 |
| 基础设施 | **现在拆库**：Compose / 默认 env 使用 zak2 自有 PG + Redis |
| 数据连续性 | **可选一次性导入**（`ZAK_IMPORT_DATABASE_URL` → 目标库）；之后分叉 |
| 表结构 | 第一刀 **fork 现 ORM/SQL 已用表形**；不绿场重设计 |
| Redis 键 | 行情等统一 **`zak2:*`**（不再兼容桌面 `zak:*`） |
| 产品文档 | **归档** `gap-vs-desktop`；新建 `docs/product-roadmap.md` 主导优先级 |

曾考虑「兼容优先可拆」与「仅拆 Redis」；已否决。曾考虑绿场 schema 重设计；因导入与工期风险，延后为后续刀。

## 目标

1. 日常开发与 Compose **不依赖** 宿主机 zak 实例即可登录、采行情、跑已有 RUNNABLE job。  
2. zak2 **自持 Alembic**，可独立加表/改表。  
3. 文档与 Ops **不再引导**「去跑 zak CLI」。  
4. 产品排期以 Web 价值为准，不再维护桌面缺口对照表。

## 非目标

- 不改 zak / vnpy-* 仓库代码  
- 不做持续 CDC / 双写同步  
- 不第一刀重设计表名或范式  
- 不一次实现桌面全量 job（enrich、prefetch_*、分钟线等）  
- 不做交易下单链路  
- 不从 zak Redis 迁行情键（由 collector 重填）  
- 不继续维护 `gap-vs-desktop` 作为排期依据  

## 架构

```text
[zak2 Compose / 本地]
  postgres (db: zak2) ──┐
  redis                 ├── api (FastAPI + embedded scheduler + Alembic on start)
                        ├── quote-collector (TickFlow → zak2:quote:* …)
                        └── web

[可选一次性]
  zak DATABASE ──import_from_zak.py──▶ zak2 DATABASE
```

与 zak 桌面可同机并存；**默认数据不通**。仅导入脚本读取旧库。

---

## 1. 基础设施边界

### Compose

服务：`postgres`、`redis`、`api`、`quote-collector`、`web`。

- PG：官方镜像；库名/用户建议 `zak2`；数据卷持久化  
- Redis：官方镜像；单 db  
- `api` / `quote-collector` 的 `DATABASE_URL` / `REDIS_URL` 指向 Compose 服务名，**默认不再** `host.docker.internal` → 宿主机 zak  
- 可选文档说明「高级：连外部已有库」，不作默认  

### 环境变量

| 变量 | 意图 |
|------|------|
| `DATABASE_URL` | 默认指向 zak2 库（本地 `localhost`，Compose 内 `postgres`） |
| `REDIS_URL` | 默认本实例 Redis |
| `ZAK_IMPORT_DATABASE_URL` | **仅导入脚本**；API 运行时不读 |
| `DOCKER_*` 指宿主机 zak 的默认路径 | 删除或弱化为非默认覆盖 |

### Redis 键前缀

| 现况 | 目标 |
|------|------|
| `zak:quote:*` / `zak:rank:*` / `zak:meta:*` / `zak:notify:quotes` | **`zak2:`** 同结构 |
| `zak2:collector:*` / `zak2:scheduler:lock:*` | 保持 |

读侧（`QuoteStore`、策略看盘、WS Hub）、写侧（collector writer）共用同一前缀常量；禁止再散落 `"zak:"` 行情键字面量。

拆库后无「与 zak CLI 双写互斥」约束；改为「**本实例内只跑一个 collector**」。

---

## 2. Schema 主权与导入

### Alembic

- 路径：`backend/alembic/`（或仓库约定等价位置）  
- 启动 / Compose：api 就绪前 `alembic upgrade head`  
- `search_path` 保持：`auth,app,chat,cache,system,public`  
- 将运行时旁路建表（如 `app.web_team_reports` 的 `CREATE TABLE IF NOT EXISTS`）**收进迁移**  

### 第一刀对象范围

以现有 ORM + raw SQL 引用为准，至少覆盖：

- **auth**：`users`、`user_preferences`  
- **app**：自选/分组/持仓、选股方案配方历史、笔记/Feed/计划/守则、universe、stock_industry、trade_calendar、板块/涨停/情绪相关、notify、meta、backtest、`web_team_reports` 等读侧已用表  
- **chat**：`sessions`、`messages`  
- **cache**：雷达快照及 purge 涉及的 cache 表（可空结构）  
- **system**：`scheduler_config`（若 Ops 依赖）  

`dbbardata`：Alembic **建结构**；默认 **不**从 zak 导入（体量大，靠 Web 日 K job 重拉）。

### 导入脚本

`scripts/import_from_zak.py`（或 backend 等价 CLI）：

| 项 | 约定 |
|----|------|
| 源 | `ZAK_IMPORT_DATABASE_URL` |
| 目标 | `DATABASE_URL`（须已 `upgrade`） |
| 默认拷贝 | 用户、偏好、自选/分组/持仓、笔记、Feed 订阅、计划、选股方案/配方/历史、守则相关、通知日志等业务态 |
| 默认跳过 | `dbbardata`；可再 sync 的行情衍生表（可选 `--with-market-sync-tables`） |
| 冲突 | 目标非空须 `--force`；策略写死为 **truncate 已选表再 copy**（避免半残 upsert） |
| 密码 | 原样拷 `password_hash`（算法已兼容） |
| 之后 | 两库分叉，无双向同步 |

绿场可不跑导入；可另加薄 `create_user`（非本刀必须）。

---

## 3. 运行时自给

### 进程

| 进程 | 职责 |
|------|------|
| `api` | REST/WS、RUNNABLE job、内嵌调度、健康 |
| `quote-collector` | 全市场快照；**不**进 `RUNNABLE_JOB_IDS` |
| `web` | 静态 + 反代 |

`dev.sh` / Compose 默认拉齐上述进程。

### Job 目录

| 类别 | 处理 |
|------|------|
| 现有 RUNNABLE（约 13 个） | 保持；文案去「共用 zak / CLI」 |
| `collect_quotes` | 仍非 RUNNABLE；`run_hint` 仅指向 `python -m app.quote_collector` |
| catalog 中未实现项 | 降为 **planned**：Ops 展示「未实现」；**禁止** `zak CLI` hint |
| 未来补齐 | 由 `product-roadmap` 排期，在 zak2 内实现后再进 RUNNABLE |

### 文案与 UI 必清项

- README、`.env.example`、`scripts/*`：去掉「先在 zak 侧 db upgrade」「勿与 zak CLI 双写」  
- `ops_scheduler` CLI hint 分支删除或改为 planned  
- Ops UI：`CLI` 标签 → `未实现` / collector 用 `独立进程`  

### 验收标准

仅 zak2（自有 PG+Redis）+ 有效 TickFlow（及业务所需 Token）即可：登录、collector 写入 `zak2:*`、跑已有 RUNNABLE；**不启动 zak 仓库**。

---

## 4. 产品文档

### 归档缺口表

- `docs/gap-vs-desktop.md` → `docs/archive/gap-vs-desktop.md`  
- 页顶注明已归档、不再维护  
- README / smoke / architecture 外链更新  

### 新产品路线

新建 `docs/product-roadmap.md`：

- 定位：独立 Web 终端；自有 PG/Redis；不依赖 zak 运行时  
- 当前基线能力摘要  
- 近期待办：① 本总纲基础设施 ② 去 CLI / planned 透明化 ③ 其后候选（enrich、AI 工具等）由后续立项  
- 明确不做：桌面双写、依赖 CLI、下单（除非单独立项）  

### 架构笔记

更新 `docs/architecture-p1.md` 决策表：自有实例、zak2 Alembic、排期以 roadmap 为准。  
`smoke-checklist.md`：去掉跨端「桌面同用户可见」类断言；增加 Alembic、自有库、`zak2:*` 检查。

---

## 分期落地

| 阶段 | 交付 | 验收 |
|------|------|------|
| P0 骨架 | Compose postgres/redis；env 默认 zak2；Alembic | `docker compose up` 无宿主机 zak 可起 |
| P1 键与采集 | Redis 前缀 `zak2:*`；读写侧一致 | 盘中有行情；不再读写 `zak:` 行情键 |
| P2 导入 | `import_from_zak.py` | 导入用户+自选后可登录 |
| P3 文档与 Ops | 归档 gap；roadmap；去 CLI；planned | 文档/Ops 无「去跑 zak」 |
| P4+ | enrich 等 | 只进 roadmap，本总纲不绑死 |

建议顺序：**P0 → P1 → P3（可与 P2 并行）→ P2**（绿场可跳过 P2）。

实现计划：`docs/superpowers/plans/2026-08-11-zak2-independent-evolution.md`。

## 风险

| 风险 | 对策 |
|------|------|
| Alembic 漏表 | 以 ORM + raw SQL 引用列清单；导入/pytest 冒烟补洞 |
| `dbbardata` 过大 | 默认不导入；Web 日 K job 重拉 |
| 前缀漏改 | 单一 `KEY_PREFIX` 常量；测试断言；禁散落 `"zak:"` 行情键 |
| 误连旧库 | 默认库名 `zak2`；导入 URL 单独变量 |

## 测试要点

- Compose 冷启动：无外部 zak → health 绿、迁移成功  
- collector 写 `zak2:quote:*` / notify；API 读侧一致  
- 前缀回归：代码与测试无行情 `zak:` 依赖  
- 导入：空目标库导入用户后 login 成功；`--force` 行为符合文档  
- Ops：未实现 job 无 CLI 文案；collector hint 正确  

## 文档交付物（本刀）

| 路径 | 动作 |
|------|------|
| 本 spec | 已批准总纲 |
| `docs/product-roadmap.md` | 新建 |
| `docs/archive/gap-vs-desktop.md` | 归档自 gap |
| `docs/architecture-p1.md`、`README.md`、`.env.example`、`smoke-checklist.md` | 按上节更新 |
| 实现 plan | 批准本 spec 后另写 |
