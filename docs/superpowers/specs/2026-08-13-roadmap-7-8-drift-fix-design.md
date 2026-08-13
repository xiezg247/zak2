# 路线图 #7/#8「恒 skipped」漂移纠偏

日期：2026-08-13  
状态：已批准（方案 A：历史定格 + 指针）

## 背景

`docs/product-roadmap.md` #7 / #8 仍写 `warm_watchlist_strategy_cache` / `scan_horizon_outlook` / `prefetch_concept_board` / `fill_focus_pool_minute` 为「可跑占位（恒 skipped）」。后续 #26/#27/#29/#30 已做实这些 job，活路线图摘要会误导读者。smoke 与实现已对齐；归档 batch3/4 spec·plan 保留当时完成态，不在本刀改写。

## 目标

1. 仅修正路线图 #7/#8 摘要，去掉「恒 skipped」误导。  
2. 保留第三/四批作为「当时注册可跑占位」的里程碑，并指针到后续做实条目。  
3. 不改代码、smoke、归档 spec/plan。

## 非目标

- 不扫改其它活文档或归档脚注（方案 A 范围）。  
- 不改 job 行为、catalog、测试。  
- 不重编号 #7/#8 或合并到 #26–30。

## 方案

**改文件：** `docs/product-roadmap.md` 两行。

**#7 拟文案：**

```markdown
7. ~~Ops planned 第三批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch3-design.md)）：`warm_watchlist_strategy_cache` / `scan_horizon_outlook` 当时注册为可跑占位；现状见 #26 / #29（展望/策略启发式）
```

**#8 拟文案：**

```markdown
8. ~~Ops planned 第四批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch4-design.md)）：`prefetch_concept_board` / `fill_focus_pool_minute` 当时注册为可跑占位（catalog 已无 planned）；现状见 #27 / #30
```

说明：#7 链 batch3；现状 #26=展望启发式、#29=策略双均线。#8 链 batch4；现状 #27=薄做实（含 concept）、#30=1m 真下载。

## 验收

- [ ] #7/#8 正文不再出现「恒 skipped」  
- [ ] 仍分别链接 batch3 / batch4 原 spec  
- [ ] 含「当时注册为可跑占位」与「现状见 #…」  
- [ ] 仅 `product-roadmap.md` 变更（本刀实现 commit）

## 风险

无运行时风险。读者若只读 #7/#8 不跟指针，仍可能低估现状——靠「现状见」缓解；详细能力以 #26–30 为准。
