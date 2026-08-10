# AI Skill Python 薄运行时设计

日期：2026-08-10  
状态：已批准（方案 A：同进程 importlib + 超时；示范仅 market-emotion）  
范围：仅 zak2；不改 zak / vnpy-*；不移植桌面 registry

## 目标

1. 同进程薄执行器：加载 `skills/<id>/skill.py` 的 `run(ctx, args)`，超时默认 5s。  
2. Agent 工具 `run_skill(skill_id, args?)`；失败返回 `{error}`，不崩工具循环。  
3. 示范：仅 `market-emotion/skill.py`（只读，返回与 `_get_market_emotion` 同形）。

## 非目标

- 真沙箱 / subprocess / AST 沙箱  
- 搬桌面 `vnpy_*_skill.py` / `cli.py skills sync`  
- 五个内置 skill 全部补 `skill.py`（其余另刀）  
- 写操作经 skill（仍走确认卡写工具）  
- Ai 页 Skills 面板 / 上传编辑  
- `SKILLS_DIR` 外挂多根目录  

## 契约

```python
@dataclass
class SkillContext:
    db: Session
    user_id: str

# skills/<id>/skill.py
def run(ctx: SkillContext, args: dict) -> Any: ...
```

可选：`SkillContext` 提供只读 `call_tool(name, args)` 白名单（本刀示范可直接调 `app.services.market`，不强制 helper）。

## 模块

| 路径 | 职责 |
|------|------|
| `backend/app/services/skill_runtime.py` | `SKILL_TIMEOUT_SEC=5`；解析路径；importlib 加载；`ThreadPoolExecutor` 超时；包装错误 |
| `backend/app/skills/market-emotion/skill.py` | 示范 `run` |
| `backend/app/services/ai_tools.py` | 注册 `run_skill`；**不**进 `WRITE_TOOL_NAMES` |
| `backend/app/services/skills_catalog.py` | `list_skills` 项增 `runnable: bool`（目录存在 `skill.py`） |

安全：

- `skill_id` 规则同 catalog（`^[a-z0-9][a-z0-9_-]*$`）  
- `skill.py` resolve 后必须在 `skills_root/<id>/` 下  
- 仅调用模块属性 `run`；不 `exec` 源码字符串  
- 无文件 / 无 `run` / 超时 / 异常 → 工具侧 `{error: str}`  

## 示范 skill

`market-emotion/skill.py`：忽略或空 `args`；返回：

```json
{ "emotion": ..., "overview": ... }
```

与 `_get_market_emotion` 一致。`SKILL.md` 补一句：可用 `run_skill`。

## Agent 工具

| 工具 | 参数 | 行为 |
|------|------|------|
| `run_skill` | `skill_id: string`；`args?: object` | 调 runtime；成功返回 JSON 可序列化结果；失败 `{error}` |

只读；不进写工具集。

## 测试

- runtime：非法 id、缺 `skill.py`、超时、成功路径（tmp skill 或 demo）  
- `run_skill` 工具：成功 / error；断言不在 `WRITE_TOOL_NAMES`  
- demo：mock `market` 后含 `emotion`  
- 不打真网  

## 文档

- `docs/gap-vs-desktop.md`：Skills 行注明薄 `run_skill` + market-emotion 示范  
- `docs/smoke-checklist.md`：AI 节可选「run_skill market-emotion」  
- gap「建议下一刀」：其余 skill 补 `skill.py` 等  

## 验收

1. `run_skill(market-emotion)` 返回含 emotion  
2. 缺文件 / 超时 / 非法 id → `{error}`  
3. `run_skill` 不在写工具集  
4. 相关 pytest 绿（前端无强制改动）  
