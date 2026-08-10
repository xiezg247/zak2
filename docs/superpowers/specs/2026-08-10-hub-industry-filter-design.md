# Hub 硬过滤行业勾选下拉设计

日期：2026-08-10  
状态：已批准（方案 1：列表 API + resolve 模板 merge + checkbox）  
范围：仅 zak2；不改 zak；不改硬过滤算法本身

## 目标

1. 提供行业名列表 API（读 `app.stock_industry`）  
2. Hub 硬过滤旁可勾选行业白名单，运行时与模板 merge 后生效  
3. 方案可保存/恢复已选行业  

## 非目标

- L1 分组 UI、改 sync、写 Redis  
- 改 `apply_hard_filters` 语义（空 industry 仍按现逻辑放行）  
- 改 zak  

## 后端

### `list_industry_names(db) -> list[str]`

`stock_industry.py`：  
`SELECT DISTINCT industry FROM app.stock_industry WHERE TRIM(industry) <> '' ORDER BY industry`  
异常 → `[]`。

### API

`GET /api/v1/screener/industries` → `{ "items": ["白酒", ...] }`

### `resolve_hard_filter` merge

```text
若 prefs 与 template 皆无 → balanced 默认
若仅 prefs → prefs
若仅 template → 模板 prefs
若两者都有 → base = 模板 prefs.copy()
             overlay = prefs.model_dump(exclude_unset=True)
             base 上按 overlay 字段覆盖
```

Hub 只传 `hard_filter: { allowed_industries: "白酒,银行" }` + `hard_filter_template` 时：成交额/市值等仍来自模板，行业白名单为勾选项。

## 前端

### ScreenerHubView

- 加载 industries（失败不挡）  
- 可折叠 checkbox 列表；全不选 = 不限制  
- `buildHardFilterPayload()`：有勾选 → `{ allowed_industries: joined }`，否则 `undefined`  
- 条件/配方/形态/对标运行 body：保留 `hard_filter_template`，有 payload 时加 `hard_filter`  
- 方案 config：`allowed_industries` 字符串；恢复时解析勾选  

### API client

`screenerApi.industries()` → GET

## 测试

- list / API 空与有数据  
- resolve：仅 template；template + unset 覆盖 industries；仅 prefs  
- 不打真网  

## 文档

- gap：Hub 可勾选行业白名单  
- smoke：同步后 Hub 勾选并过滤；不勾选与现网一致  

## 验收

1. 勾选后结果行业落在白名单内（配合 enrich/行情）  
2. 不勾选行为不变  
3. pytest + `npm run build` 绿  
