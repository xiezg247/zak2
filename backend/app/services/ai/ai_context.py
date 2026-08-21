"""组装投研上下文，供系统提示注入（非完整 Agent）。"""

from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.backtest import BacktestRun
from app.models.screener import ScreenerRun
from app.models.watchlist import WatchlistItem
from app.domains.market import overview as market_svc


def build_context_brief(db: Session, user_id: str) -> str:
    parts: list[str] = []

    wl = list(
        db.scalars(
            select(WatchlistItem).where(WatchlistItem.user_id == user_id).order_by(WatchlistItem.sort_order).limit(20)
        )
    )
    if wl:
        items = ", ".join(f"{i.symbol}.{i.exchange}({i.name or ''})" for i in wl[:15])
        parts.append(f"自选池（{len(wl)}，截取前15）：{items}")

    emotion = market_svc.load_emotion(db)
    if emotion:
        parts.append(
            f"连板情绪 {emotion.trade_date}：最高 {emotion.max_limit_times} 板，"
            f"龙头 {emotion.max_board_vt_symbol}，关联 {emotion.linked_board_count} 只"
        )

    run = db.scalar(
        select(ScreenerRun).where(ScreenerRun.user_id == user_id).order_by(desc(ScreenerRun.created_at)).limit(1)
    )
    if run:
        parts.append(f"最近选股：{run.condition} / {run.source}，命中 {run.row_count}，时间 {run.created_at}")

    bt = db.scalar(
        select(BacktestRun).where(BacktestRun.user_id == user_id).order_by(desc(BacktestRun.created_at)).limit(1)
    )
    if bt:
        parts.append(
            f"最近回测：{bt.vt_symbol} {bt.strategy} 收益 {bt.total_return}% 回撤 {bt.max_drawdown}% "
            f"夏普 {bt.sharpe_ratio}（{bt.created_at}）"
        )

    if not parts:
        return "（暂无用户侧上下文）"
    return "\n".join(f"- {p}" for p in parts)


SYSTEM_PROMPT = """你是 zak2 A 股投研助手。回答简洁、可执行，优先给出结论与风险。
你可以使用工具查询真实数据：自选、连板情绪、最近选股、雷达卡片、单票日 K 摘要、最近回测。
需要事实数据时先调用工具，再基于工具结果作答；不要编造行情或选股结果。
重要约束：
1. 不构成投资建议；提醒用户自行决策与风控。
2. 退潮/冰点环境避免鼓动追板。
3. 若工具结果不足，明确说明缺什么数据（如需下载日 K、刷新行情）。
4. 可用 Markdown 短列表。
"""
