# 形态选股子集 Implementation Plan

> **For agentic workers:** 按任务顺序实现。

**Goal:** Hub 形态选股 `ma_bull` / `w_bottom`；Redis∩日K，max_scan≈800。

**Architecture:** `pattern_rules` 纯函数 + `pattern_screen` 扫描；`POST /screener/runs/pattern` 异步 job 落库；Hub 第三 Tab。

**Tech Stack:** FastAPI、PG dbbardata、Redis QuoteStore、Vue ScreenerHub。

## Tasks

- [ ] Task 1: pattern_rules + 单测
- [ ] Task 2: pattern_screen + API job + schema
- [ ] Task 3: 前端 Tab + docs + pytest/build
