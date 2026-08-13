# 独立演进 #1 收口：漏网文案 + 路线图划掉

日期：2026-08-13  
状态：已批准（方案 A：最小替换）

## 背景

总纲 [zak2-independent-evolution](./2026-08-11-zak2-independent-evolution-design.md) 的 Compose / Alembic / `zak2:` / 导入 / Ops 去 CLI hint 已落地，但路线图 #1 仍开着。审计发现 4 处 API `detail` 仍引导「zak 侧 / zak 下载」。

## 目标

1. 清除活代码中引导 zak 桌面/CLI 的用户可见错误文案。  
2. 将 `docs/product-roadmap.md` #1 标为已完成。  
3. smoke 补一条可选验收（文案不引导 zak）。

## 非目标

- 不跑 Compose / TickFlow / 导入手测。  
- 不抽公共 messages 模块。  
- 不改归档 docs、collector 行为、日 K 下载逻辑。

## 文案变更

| 文件 | 旧（含） | 新 |
|------|----------|-----|
| `backend/app/services/engine.py` | 请先在 zak 侧执行 collect_quotes | `行情快照为空，请启动 quote-collector（python -m app.quote_collector）` |
| `backend/app/services/pattern_screen.py` | 同上 | 同上 |
| `backend/app/services/backtest_engine.py` | 请先在 zak 下载日 K | `日 K 不足（{n}），请先在 Ops 补全日 K` |
| `backend/app/services/bars.py` | 或使用 zak 下载 | `无 K 线数据，请先在 Ops 补全日 K` |

## 测试

- 覆盖上述抛错路径（单元/现有测扩展）：`detail` 不含 `zak 侧`、`zak 下载`、`使用 zak`；行情空含 `quote-collector`；日 K 空含 `Ops`。  
- `./scripts/check.sh` 通过。

## 文档

**路线图 #1** 改为：

```markdown
1. ~~完成本独立演进落地~~（已完成 → [总纲](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)；收口 → [spec](./superpowers/specs/2026-08-13-independent-evolution-closeout-design.md)）
```

**smoke-checklist.md**：在选股/回测或前置区增加：

```markdown
- [ ] 选股空行情 / 回测或 K 线无日 K 时的错误文案引导 quote-collector 或 Ops，不出现「zak 侧」「zak 下载」
```

## 验收

- [ ] 四处 detail 已替换；全仓 `backend/app` 无「zak 侧」「zak 下载」「使用 zak」用户文案  
- [ ] 相关测试绿；`check.sh` 绿  
- [ ] 路线图 #1 已划掉并链接本 spec  
- [ ] smoke 有对应可选条  

## 风险

文案变更可能影响依赖精确 `detail` 字符串的前端分支——当前 frontend 无匹配；若有，改为展示后端 `detail` 即可。
