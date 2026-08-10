# 超短配方权重可编辑设计

日期：2026-08-07  
状态：已批准（扩现有 recipe_weights 体系）  
范围：仅 zak2；配方 `ultra_short_unified`；复用盘中/盘后权重 API/UI/归一化

## 目标

Hub 选「超短统一」时可编辑因子权重，按用户持久化，跑选股生效。

## 非目标

- 新 API/新面板形态、新因子库  
- `radar_leader` 权重  
- 改 zak  

## 默认权重（对齐现 `engine._score_ultra_short`）

| key | label | default |
|-----|-------|---------|
| board | 连板 | 0.40 |
| momentum | 动量 | 0.35 |
| turnover | 换手 | 0.25 |

## 改动点

1. **`recipe_weights.py`**  
   - `EDITABLE_RECIPES` 加入 `ultra_short_unified`  
   - `DEFAULT_WEIGHTS` / `FACTOR_LABELS` 增加上表  

2. **`engine.py`**  
   - `_score_ultra_short(row, weights=None)`：与盘中同，用 `weights or DEFAULT`  
   - `run_recipe_screen` 已对 `EDITABLE_RECIPES` 统一 load；无需新分支（确认 scorer 调用传 `weights`）  

3. **前端**  
   - `WEIGHT_EDITABLE` 加入 `ultra_short_unified`  

4. **测试**  
   - normalize/defaults 含超短  
   - API GET/PUT 超短 200  
   - scorer：自定义权重可翻转排序（mock `limit_times` / `change_pct`）  

5. **文档**  
   - gap：多因子权重含超短；smoke：Hub 超短可改权重  

## 持久化 / API / 校验

与既有 spec `2026-08-07-screener-recipe-weights-design.md` 相同：  
`app.meta` key `screener/recipe_weights/{user_id}`；GET/PUT `/screener/recipes/{recipe_id}/weights`；≥0 归一化；`{}` 恢复默认。

## 验收

1. 选超短可见权重面板；保存后刷新仍在  
2. 跑选股使用用户权重  
3. pytest + `npm run build` 绿  
