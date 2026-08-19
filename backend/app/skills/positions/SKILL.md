---
name: positions
description: 持仓、信号名单与风控只读总览；写操作须用户确认
---

# 持仓与信号

触发：持仓、仓位、信号名单、风控。

| 工具 | 用途 |
|------|------|
| get_positions | 列出记账持仓 |
| get_signal_panel | 信号名单 |
| get_trading_risk | 风控偏好 + risk_summary |
| upsert_position / delete_position | 写持仓（须确认卡） |
| add_signal_panel / remove_signal_panel | 写信号名单（须确认卡） |
| run_skill | skill_id=positions；可 section=all\|positions\|signals\|risk |
