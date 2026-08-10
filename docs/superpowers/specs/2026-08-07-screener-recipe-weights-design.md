# 选股多因子权重编辑设计

日期：2026-08-07  
状态：已批准（方案 A：app.meta 持久化 + Hub 编辑 + engine 生效）  
范围：仅 zak2；不改 zak；覆盖 `intraday_multi` / `post_close_multi`

## 目标

1. 用户可编辑盘中/盘后多因子配方权重，按用户持久化。
2. 跑选股时用已存权重打分；可恢复内置默认。

## 非目标

- `ultra_short_unified` / `radar_leader` / 形态 / 对标权重
- 扩因子库、改桌面选股
- 自动选股 cron 专用权重 UI（跑时可读用户权重即可）
- 下单

## 默认权重（与现 `engine.py` 硬编码一致）

### `intraday_multi`

| key | label | default |
|-----|-------|---------|
| momentum | 动量 | 0.35 |
| turnover | 换手 | 0.25 |
| volume_ratio | 量比 | 0.25 |
| surge | 成交额 | 0.15 |

### `post_close_multi`

| key | label | default |
|-----|-------|---------|
| moneyflow | 资金 | 0.40 |
| momentum | 动量 | 0.30 |
| turnover | 换手 | 0.20 |
| valuation | 估值 | 0.10 |

## 持久化

- 表：`app.meta`
- key：`screener/recipe_weights/{user_id}`
- value JSON 示例：

```json
{
  "intraday_multi": {
    "momentum": 0.4,
    "turnover": 0.2,
    "volume_ratio": 0.2,
    "surge": 0.2
  }
}
```

仅存用户改过的 recipe；未出现的 recipe 用默认。

## API

### `GET /api/v1/screener/recipes/{recipe_id}/weights`

- `recipe_id` ∈ {`intraday_multi`, `post_close_multi`}，否则 400 中文
- 响应：

```json
{
  "recipe_id": "intraday_multi",
  "items": [
    {"key": "momentum", "label": "动量", "weight": 0.35, "default_weight": 0.35}
  ],
  "weights": {"momentum": 0.35, "turnover": 0.25, "volume_ratio": 0.25, "surge": 0.15}
}
```

### `PUT /api/v1/screener/recipes/{recipe_id}/weights`

- Body：`{ "weights": { "momentum": 0.5, ... } }`
- `weights == {}`：删除该 recipe 覆盖，恢复默认
- 校验：
  - 必须是对象；未知 key → 400
  - 每个值有限数且 ≥ 0；全 0 → 400
  - **归一化**：`w_i / sum(w)`，存四舍五入到合理精度（如 4 位）
- 非法 → 400 中文

## Engine

- 抽出默认权重常量与「加权打分」函数；`_score_intraday_multi` / `_score_post_close_multi` 接受可选 `weights: dict[str, float] | None`
- `run_recipe_screen`：对两配方 `load_user_recipe_weights(db, user_id, recipe_id)` 后打分
- 其它 recipe 不变
- 因子归一化分（0–1 clamp）逻辑保持现状，仅权重可配

## 前端（ScreenerHubView 配方 Tab）

- 选中盘中/盘后时显示权重面板；其它配方隐藏
- GET 当前配方权重 → number 输入；保存 PUT；恢复默认 PUT `{}`
- 空 draft 禁止误保存清空（仅恢复默认可 `{}`）
- 切配方重新加载；跑选股流程不变

## 测试

- 默认 / merge / 归一化 / 未知键 / 全 0 / PUT `{}` 恢复
- engine：自定义权重改变排序相对默认（mock quotes）
- API GET/PUT 400/200
- 不打真网

## 文档

- gap：形态/多因子行 → 盘中/盘后可编辑权重
- smoke：Hub 可改多因子权重并跑选股

## 验收

1. 改盘中权重保存后刷新仍在；选股使用新权重  
2. 恢复默认回到内置比例  
3. pytest + `npm run build` 绿  
