# 真 MCP 客户端（薄 · Streamable HTTP）设计

日期：2026-08-06  
状态：已批准（方案 1）  
范围：仅 zak2；不 import vnpy_mcp

## 目标

单 server Streamable HTTP MCP；白名单只读工具注入 AI Agent；健康可探测连接。

## 非目标

多 server、stdio、写操作 MCP、Skills、team 自动诊断、依赖 zak vnpy_mcp。

## Settings

- `mcp_enabled`、`mcp_url`、`mcp_api_key`
- `mcp_tool_allowlist`（逗号分隔；空则默认名称含 `diagnose`）
- `mcp_command` 废弃/忽略

## 客户端

`app/services/mcp_client.py`：`mcp` SDK + 常驻 loop + 调用锁；`list_tools` / `call_tool`。

## Agent

- 远端工具 → Agent 名 `mcp_<name>`
- 白名单动态并入 `get_tool_definitions()`
- `execute_tool` 转发 `call_tool`；结果截断；失败中文串

## Ops

健康 status：已连接 / 失败原因 / 未启用；可选 `GET /ops/mcp/tools`。

## 测试

mock SDK；不打真网。
