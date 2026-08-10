# notes 只读工具 + skill.py 设计

日期：2026-08-10  
状态：已批准（方案 A：扩 ai_read_tools；聚合 + 列表；skill 按 vt_symbol 分流）  
范围：仅 zak2；不改 zak；不改 REST notes 契约语义（仅复用 service）

## 目标

1. Agent 只读工具：`list_note_symbols`、`get_stock_notes`。  
2. 实现落在 `ai_read_tools`，`ai_tools` 薄委托。  
3. `notes/skill.py`：有 `vt_symbol`/`symbol` → 聚合；否则 → 列表。

## 非目标

- 写操作经 skill（`upsert_note_memo` / `add_note_entry` 仍确认卡）  
- 改 REST `/notes/*` 路径或 schema  
- 研报 `notes/reports`  
- 改 skill_runtime / zak  

## 契约

### `list_note_symbols(db, user_id, args) -> dict`

- `limit`：默认 30，夹在 1–50  
- 调用 `notes.list_note_symbols`；截断后：

```json
{ "count": N, "symbols": [ /* NoteSymbolOut dump */ ] }
```

### `get_stock_notes(db, user_id, args) -> dict`

- 必填 `vt_symbol` 或 `symbol`（可选 `exchange`）；缺则 `{ "error": "..." }`  
- `entry_limit`：默认 20，夹在 1–50  
- `notes.get_memo` + `notes.list_entries`：

```json
{
  "memo": { /* NoteMemoOut dump */ },
  "entries": [ /* NoteEntryOut dump */ ],
  "entry_count": M
}
```

（`entry_count` 为本批返回条数，或与 list 长度一致即可。）

## 接线

| 位置 | 行为 |
|------|------|
| `ai_read_tools.py` | 两新函数 |
| `ai_tools.py` | `TOOL_HANDLERS` + `TOOL_DEFINITIONS`；不进 `WRITE_TOOL_NAMES` |
| `skills/notes/skill.py` | **新建** 分流 `run` |
| `skills/notes/SKILL.md` | 表加只读工具与 `run_skill` |

## 测试

- helper：mock `notes.*`；缺 symbol → error；limit 截断  
- 工具：不在写集合；`execute_tool` 成功路径  
- catalog：`notes.runnable is True`  
- skill：有/无 vt_symbol 两路径（mock helper）  
- 不打真网  

## 文档

- gap：五 skill 均可 run；建议下一刀 B 站 / Docker 等  
- smoke：notes 只读 / `run_skill notes`  

## 验收

1. 两工具只读、非写工具集  
2. skill 分流正确；`runnable=True`  
3. 相关 pytest 绿  
