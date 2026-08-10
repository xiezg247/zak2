# AI Skills 薄接入（内置 SKILL.md）设计

日期：2026-08-07  
状态：已批准（方案 A：内置目录 + list_skills / read_skill）  
范围：仅 zak2；不改 zak / vnpy-*；不执行桌面 Python Skill

## 目标

1. 随包分发 Web 向 `SKILL.md`（约 5 个），对齐 zak2 已有 Agent 工具。
2. Agent 可通过只读工具 `list_skills` / `read_skill` 按需加载说明。

## 非目标

- 运行桌面 `vnpy_skills` / `cli.py skills sync` / 任意 Skill Python 代码
- Ai 页 Skills 面板、上传/编辑
- 环境变量外挂 `SKILLS_DIR`、多根目录
- 新增选股/行情等业务能力；扩展 MCP 白名单

## 目录约定

根：`backend/app/skills/`（相对 `skills_catalog.py` 定位）。

结构：

```text
backend/app/skills/
├── watchlist/SKILL.md
├── market-emotion/SKILL.md
├── screener/SKILL.md
├── radar/SKILL.md
└── notes/SKILL.md
```

每个 `SKILL.md`：

```yaml
---
name: watchlist
description: 自选查看与加减；写操作须用户确认
---
```

正文：触发词、优先工具表、写操作须确认卡等短说明。**禁止**写通达信 MCP / TickFlow / 桌面专用工具名。

| id | 优先工具 |
|----|----------|
| watchlist | get_watchlist, add_watchlist, remove_watchlist |
| market-emotion | get_market_emotion |
| screener | get_recent_screening |
| radar | get_radar_snapshot |
| notes | upsert_note_memo, add_note_entry |

## 服务层

`backend/app/services/skills_catalog.py`：

- `skills_root() -> Path`
- `list_skills() -> list[dict]` — `{id, name, description}`，按 id 排序
- `read_skill(skill_id: str) -> dict` — `{id, name, description, content}`  
  - 非法 id / 路径穿越 → `ValueError` 中文  
  - `content` 截断上限：`MAX_SKILL_CHARS = 12000`

安全：

- `skill_id` 仅允许 `[a-z0-9][a-z0-9_-]*`（或等价严格规则）
- `resolve` 后必须在 `skills_root` 之下；只读该目录下的 `SKILL.md`

Frontmatter：简易解析（`---` 块内 `key: value`）；缺省 `name=id`，`description` 取正文首个非空行或空串。

## Agent 工具

挂到现有 `ai_tools`：

| 工具 | 参数 | 行为 |
|------|------|------|
| list_skills | 无 | 返回 catalog JSON |
| read_skill | skill_id: string | 成功返回全文；失败返回 `{error}`（不抛崩循环） |

均为只读；不进 `WRITE_TOOL_NAMES`。

## API / UI

- **无**新 REST（本刀）；不改 Ai 页导航
- 依赖 chat 已有 tool-calling 即可用

## 测试

- list 含 5 个 id
- read watchlist 含 frontmatter 字段与正文片段
- 路径穿越 / 非法 id → ValueError 或工具 error
- 截断：超长 content 被截（可用临时文件或 monkeypatch root 的 fixture）
- 不打真 LLM

## 文档

- gap：写操作工具 / MCP / Skills → 有内置 SKILL.md + list/read；仍无 Python Skill 运行时
- smoke：可选「Ai 可 list_skills」；以单测为准亦可

## 验收

1. `list_skills` 返回 5 个内置 skill  
2. `read_skill("watchlist")` 可读；穿越被拒  
3. pytest + `npm run build` 绿  
