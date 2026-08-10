# 雷达共振权重 UI（按用户持久化）设计

日期：2026-08-07  
状态：已批准（方案 1：`app.meta` + 侧栏薄 UI）  
范围：仅 zak2；不改 zak / vnpy-*

## 目标

- 按登录用户持久化雷达共振卡片权重（PG `app.meta`）。
- 雷达侧栏可调：各可编卡数字输入 +「保存」+「恢复默认」；保存后立即重算共振列表。
- `GET /api/v1/radar/resonance` 使用该用户权重；无配置则回退现有 `CARD_WEIGHTS`。

## 非目标

- 「短线」一键预设、独立设置页/对话框
- Hub 雷达共振配方、情绪阶段自适应权重
- 与桌面 QSettings 双向同步
- 新表 / Alembic migration（沿用 `app.meta`）
- 改龙头评分权重

## 存储

- `app.meta.key` = `radar/resonance_weights/{user_id}`
- `value` = JSON 对象 `{ "<card_id>": <number> }`：写入时存**完整可编卡子集**（默认 >0 的 card_id 全部有值）；读时与 `CARD_WEIGHTS` merge（缺卡用默认，板块等仍为 0）
- 默认权重 = 现有 `CARD_WEIGHTS`（含 `sector_flow_hot` / `sector_theme` = 0）
- `PUT weights: {}` → **删除**该 meta 键（非写入空对象）

## 校验（写死）

- 只接受 `CARD_WEIGHTS` 中已有且**默认权重 > 0** 的 `card_id`（板块卡等不可编）
- 数值钳制到 `[0, 5]`，保留 2 位小数；`0` = 该卡不参与共振
- PUT 整包时：未知 card_id、非数字、越界 → **400** + 中文 detail
- 读路径坏 JSON / 缺键 → 静默用默认，不 500

## API

### `GET /api/v1/radar/resonance/weights`

需登录。返回：

```json
{
  "items": [
    {
      "card_id": "leader_pick",
      "title": "选股·龙头",
      "weight": 1.5,
      "default_weight": 1.5
    }
  ],
  "weights": { "leader_pick": 1.5 }
}
```

`items` 仅含默认可编卡（`default_weight > 0`）；`title` 用简洁中文标签表（与 card_id 对齐，缺省则用 card_id）。

### `PUT /api/v1/radar/resonance/weights`

Body：`{ "weights": { "<card_id>": <number> } }`

- 非空：校验后写入 meta（**完整可编卡子集**，见「存储」）
- **`weights: {}`**：删除该用户 meta 键（恢复全默认）
- 成功返回与 GET 相同结构

### `GET /api/v1/radar/resonance`

- 继续 `top_n` / `min_cards` query
- 鉴权用户 → `load_user_weights` → `compute_resonance(..., weights=merged)`

## 计算

- `compute_resonance` 增加可选参数 `weights: dict[str, float] | None`
- `None` 或未传 → 使用 `CARD_WEIGHTS`
- 公式不变：按卡累加权重；`weight <= 0` 跳过该卡

## 前端（雷达侧栏）

- 文案：「固定权重」→「可调权重」
- 可折叠「权重」区：可编卡标题 + `number`（min 0、max 5、step 0.1）
- 「保存」→ PUT 当前表单 → 刷新共振列表
- 「恢复默认」→ PUT `{ weights: {} }` → 重置表单并刷新
- 无短线预设、无独立对话框

## 错误与降级

| 情况 | 行为 |
|------|------|
| 无 meta / 坏 JSON | 默认 `CARD_WEIGHTS` |
| PUT 非法 | 400 中文 |
| 未登录 | 401（现有鉴权） |
| 保存失败 | 侧栏错误提示，保留本地编辑 |

## 测试

- merge / 钳制 / PUT `{}` 删键恢复默认
- `compute_resonance` 自定义权重改变排序或分数
- API/service 层覆盖读写；不打真网

## 文档

更新 `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`。

## 验收

1. 改权重保存后侧栏分数变化；刷新页面仍保留  
2. 恢复默认后与改前默认一致  
3. 全量 pytest + `npm run build` 绿  
