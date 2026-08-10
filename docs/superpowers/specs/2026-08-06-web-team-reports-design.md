# Web 投研研报落库 + MCP 预留设计

日期：2026-08-06  
状态：已批准（方案 3）  
范围：仅 zak2；与桌面数据完全分开，不做兼容/双写

## 目标

1. 投研团队流结束后，将综合研报写入 Web 自有表，笔记 + AI 可查看/跳转  
2. MCP 仅预留配置与健康展示「未接入」，本刀不实现客户端

## 非目标

- 桌面 `stock_analysis_reports` / `zak://`
- 真 MCP 调用、Skills、ReAct
- 研报编辑/删除 UI（可下刀）

## 表：`app.web_team_reports`

| 列 | 说明 |
|----|------|
| `id` | bigserial PK |
| `user_id` | UUID |
| `symbol` / `exchange` | VeighNa |
| `vt_symbol` | 冗余 |
| `title` / `body` / `summary` | 正文上限约 128k |
| `mode` | `fast` \| `deep` |
| `context_json` | 可选 |
| `created_at` | ISO |

`CREATE TABLE IF NOT EXISTS` 于首次写入/ensure。

## 触发

`stream_team_analysis` 在产出含「综合研判」的最终报告后静默 insert。  
失败只记日志。成功则 SSE：`{ type: "report_saved", report_id, title, vt_symbol }`。

## API

- `GET /api/v1/notes/{vt_symbol}/reports` → 列表  
- `GET /api/v1/notes/reports/{id}` → 详情（校验 user；404）

## 前端

- 笔记：研报列表 + 打开正文；query `report=` 可直达  
- AI：收到 `report_saved` → 提示 + 跳转 `/notes?symbol=&report=`

## MCP 预留

- settings：`mcp_enabled=False`，`mcp_command=""`  
- 健康：`mcp: { configured: false, status: "未接入" }`

## 测试 / 验收

见实现计划；pytest + build；与桌面表无关。
