---
name: notes
description: 个股备忘与流水；写操作须用户确认
---

# 备忘

触发：备忘、笔记、流水、memo。

| 工具 | 用途 |
|------|------|
| list_note_symbols | 列出有笔记的标的 |
| get_stock_notes | 读备忘 + 近期流水 |
| run_skill | skill_id=notes；有 vt_symbol 则聚合，否则列表 |
| upsert_note_memo | 写/更新备忘（须确认卡） |
| add_note_entry | 追加流水条目（须确认卡） |
