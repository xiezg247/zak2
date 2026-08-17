"""投研团队编排：预取 + 规则分；fast=首席一次 LLM；deep=三分析师并行 LLM + 首席。"""

from __future__ import annotations

import json
import queue
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.services import llm as llm_svc
from app.services.team_prefetch import prefetch_team
from app.services.team_scoring import compute_team_scores

TeamMode = Literal["fast", "deep"]

AGENT_LABELS = {
    "financial": "财务",
    "risk": "风险",
    "strategy": "策略",
    "chief": "首席",
}

_SUB_AGENTS = ("financial", "risk", "strategy")

_AGENT_SYSTEM = {
    "financial": (
        "你是财务分析师。仅基于给定预取 JSON 中的估值与财务字段，用中文写简洁要点（≤250字）。"
        "禁止编造未出现的指标；禁止具体买卖点位或收益保证。可用短列表。"
    ),
    "risk": (
        "你是风险分析师。仅基于波动、回撤等风险预取字段，用中文写简洁要点（≤250字）。"
        "禁止编造；禁止具体买卖点位或收益保证。"
    ),
    "strategy": (
        "你是策略与情绪分析师。仅基于均线/信号/情绪阶段等预取字段，用中文写简洁要点（≤250字）。"
        "须点明情绪阶段含义；禁止编造；禁止具体买卖点位或收益保证。"
    ),
}


def _slice_prefetch(prefetch: dict[str, Any], agent: str) -> dict[str, Any]:
    base = {
        "vt_symbol": prefetch.get("vt_symbol"),
        "name": prefetch.get("name"),
        "last_price": prefetch.get("last_price"),
        "change_pct": prefetch.get("change_pct"),
    }
    if agent == "financial":
        return {**base, "financial": prefetch.get("financial"), "bars": prefetch.get("bars")}
    if agent == "risk":
        return {**base, "risk": prefetch.get("risk"), "bars": prefetch.get("bars")}
    return {
        **base,
        "strategy": prefetch.get("strategy"),
        "emotion": prefetch.get("emotion"),
        "bars": prefetch.get("bars"),
    }


def _agent_messages(
    agent: str,
    prefetch: dict[str, Any],
    scores: dict[str, Any],
) -> list[dict[str, Any]]:
    block = scores.get(agent) or {}
    payload = {
        **_slice_prefetch(prefetch, agent),
        "rule_score": block.get("score"),
        "rule_summary": block.get("summary"),
        "highlights": block.get("highlights") or [],
        "risks": block.get("risks") or [],
    }
    user = (
        f"标的 {prefetch.get('name') or ''} {prefetch.get('vt_symbol') or ''}。"
        f"规则分 {block.get('score')}：{block.get('summary') or ''}。"
        f"请解读以下 JSON：\n```json\n{json.dumps(payload, ensure_ascii=False, default=str)[:4000]}\n```"
    )
    return [
        {"role": "system", "content": _AGENT_SYSTEM[agent]},
        {"role": "user", "content": user},
    ]


def _chief_messages(
    prefetch: dict[str, Any],
    scores: dict[str, Any],
    *,
    analyst_texts: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    vt = prefetch.get("vt_symbol") or ""
    name = prefetch.get("name") or ""
    emotion = prefetch.get("emotion") or {}
    payload: dict[str, Any] = {
        "vt_symbol": vt,
        "name": name,
        "last_price": prefetch.get("last_price"),
        "change_pct": prefetch.get("change_pct"),
        "scores": scores,
        "financial": prefetch.get("financial"),
        "risk": prefetch.get("risk"),
        "strategy": prefetch.get("strategy"),
        "emotion": emotion,
        "bars": prefetch.get("bars"),
    }
    if analyst_texts:
        payload["analyst_reports"] = analyst_texts
    limit = 800 if analyst_texts else 600
    system = (
        "你是投研首席分析师。根据给定的三维规则评分、预取事实"
        + ("与三分析师正文" if analyst_texts else "")
        + "，输出简洁中文研报。"
        "必须包含 Markdown 二级标题「## 综合研判」，以及：①综合判断与加权分引用 "
        "②财务要点 ③风险要点 ④策略/情绪要点 ⑤短线环境（情绪阶段）。"
        "禁止给出具体买卖点位或保证收益。"
        f"用 Markdown 小标题，控制在 {limit} 字以内。"
    )
    user = (
        f"标的 {name} {vt}。请汇总以下 JSON：\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, default=str)[:8000]}\n```"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _rule_fallback_text(agent: str, scores: dict[str, Any]) -> str:
    block = scores.get(agent) or {}
    parts = [str(block.get("summary") or "（无规则摘要）")]
    for h in block.get("highlights") or []:
        parts.append(f"- {h}")
    for r in block.get("risks") or []:
        parts.append(f"- 风险：{r}")
    return "\n".join(parts)


def _emit_scores(scores: dict[str, Any], prefetch: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for agent in _SUB_AGENTS:
        yield {
            "type": "team",
            "agent": agent,
            "kind": "started",
            "label": AGENT_LABELS[agent],
        }
        block = scores.get(agent) or {}
        yield {
            "type": "team",
            "agent": agent,
            "kind": "score",
            "label": AGENT_LABELS[agent],
            "score": block.get("score"),
            "summary": block.get("summary"),
            "highlights": block.get("highlights") or [],
            "risks": block.get("risks") or [],
        }
    yield {
        "type": "team",
        "agent": "system",
        "kind": "score",
        "weighted": scores.get("weighted"),
        "weights": scores.get("weights"),
        "vt_symbol": prefetch.get("vt_symbol"),
        "name": prefetch.get("name") or "",
    }


def _stream_chief(
    prefetch: dict[str, Any],
    scores: dict[str, Any],
    *,
    analyst_texts: dict[str, str] | None = None,
    mode: TeamMode = "fast",
) -> Iterator[dict[str, Any]]:
    yield {"type": "team", "agent": "chief", "kind": "started", "label": AGENT_LABELS["chief"]}
    chunks: list[str] = []
    try:
        for piece in llm_svc.stream_completion(_chief_messages(prefetch, scores, analyst_texts=analyst_texts)):
            chunks.append(piece)
            yield {"type": "team", "agent": "chief", "kind": "delta", "content": piece}
    except Exception as exc:  # noqa: BLE001
        fallback = _fallback_report(prefetch, scores, analyst_texts=analyst_texts)
        chunks.append(fallback)
        yield {"type": "team", "agent": "chief", "kind": "delta", "content": fallback}
        yield {
            "type": "team",
            "agent": "chief",
            "kind": "done",
            "content": fallback,
            "fallback": True,
            "detail": str(exc),
        }
        yield {
            "type": "team",
            "agent": "system",
            "kind": "done",
            "vt_symbol": prefetch.get("vt_symbol"),
            "name": prefetch.get("name") or "",
            "weighted": scores.get("weighted"),
            "scores": {a: scores.get(a) for a in _SUB_AGENTS},
            "report": fallback,
            "mode": mode,
        }
        return

    report = "".join(chunks)
    yield {"type": "team", "agent": "chief", "kind": "done", "content": report}
    yield {
        "type": "team",
        "agent": "system",
        "kind": "done",
        "vt_symbol": prefetch.get("vt_symbol"),
        "name": prefetch.get("name") or "",
        "weighted": scores.get("weighted"),
        "scores": {a: scores.get(a) for a in _SUB_AGENTS},
        "report": report,
        "mode": mode,
    }


def _stream_deep_analysts(
    prefetch: dict[str, Any],
    scores: dict[str, Any],
) -> tuple[Iterator[dict[str, Any]], dict[str, str]]:
    """返回 (事件迭代器, 待填充的 analyst_texts 容器)。容器在迭代结束后填好。"""
    texts_buf: dict[str, list[str]] = {a: [] for a in _SUB_AGENTS}
    analyst_texts: dict[str, str] = {}
    fallbacks: dict[str, bool] = {}
    q: queue.Queue[dict[str, Any]] = queue.Queue()

    def worker(agent: str) -> None:
        try:
            for piece in llm_svc.stream_completion(_agent_messages(agent, prefetch, scores)):
                texts_buf[agent].append(piece)
                q.put(
                    {
                        "type": "team",
                        "agent": agent,
                        "kind": "delta",
                        "label": AGENT_LABELS[agent],
                        "content": piece,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            fb = _rule_fallback_text(agent, scores)
            texts_buf[agent] = [fb]
            fallbacks[agent] = True
            q.put(
                {
                    "type": "team",
                    "agent": agent,
                    "kind": "delta",
                    "label": AGENT_LABELS[agent],
                    "content": fb,
                    "fallback": True,
                    "detail": str(exc),
                }
            )
        q.put(
            {
                "type": "team",
                "agent": agent,
                "kind": "done",
                "label": AGENT_LABELS[agent],
                "content": "".join(texts_buf[agent]),
                "fallback": bool(fallbacks.get(agent)),
            }
        )

    def gen() -> Iterator[dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [pool.submit(worker, a) for a in _SUB_AGENTS]
            remaining = len(_SUB_AGENTS)
            while remaining:
                ev = q.get()
                yield ev
                if ev.get("kind") == "done" and ev.get("agent") in _SUB_AGENTS:
                    remaining -= 1
            for f in futs:
                f.result()
        analyst_texts.update({a: "".join(texts_buf[a]) for a in _SUB_AGENTS})

    return gen(), analyst_texts


def stream_team_analysis(
    db: Session,
    user_id: str,
    vt_symbol: str,
    *,
    mode: TeamMode = "fast",
) -> Iterator[dict[str, Any]]:
    """
    yield SSE 友好事件：
    - type=team, agent, kind=started|score|delta|done|error
    """
    mode_norm: TeamMode = "deep" if str(mode).lower() == "deep" else "fast"
    yield {
        "type": "team",
        "agent": "system",
        "kind": "started",
        "vt_symbol": vt_symbol,
        "mode": mode_norm,
    }

    prefetch = prefetch_team(db, user_id, vt_symbol)
    if prefetch.get("error"):
        yield {
            "type": "team",
            "agent": "system",
            "kind": "error",
            "detail": str(prefetch["error"]),
        }
        return

    scores = compute_team_scores(prefetch)
    yield from _emit_scores(scores, prefetch)

    if mode_norm == "fast":
        for agent in _SUB_AGENTS:
            yield {
                "type": "team",
                "agent": agent,
                "kind": "done",
                "label": AGENT_LABELS[agent],
            }
        yield from _stream_chief(prefetch, scores, analyst_texts=None, mode="fast")
    else:
        events, analyst_texts = _stream_deep_analysts(prefetch, scores)
        yield from events
        yield from _stream_chief(prefetch, scores, analyst_texts=analyst_texts, mode="deep")


def stream_team_analysis_with_persist(
    db: Session,
    user_id: str,
    vt_symbol: str,
    *,
    mode: TeamMode = "fast",
) -> Iterator[dict[str, Any]]:
    """stream_team_analysis + 结束后静默落库。"""
    from app.services import team_reports

    last_done: dict[str, Any] | None = None
    for ev in stream_team_analysis(db, user_id, vt_symbol, mode=mode):
        yield ev
        if ev.get("type") == "team" and ev.get("agent") == "system" and ev.get("kind") == "done":
            last_done = ev
    if not last_done:
        return
    report = str(last_done.get("report") or "")
    try:
        saved = team_reports.persist_team_report(
            db,
            user_id,
            vt_symbol=str(last_done.get("vt_symbol") or vt_symbol),
            name=str(last_done.get("name") or ""),
            body=report,
            mode=str(last_done.get("mode") or mode),
            context={
                "weighted": last_done.get("weighted"),
                "scores": last_done.get("scores") or {},
            },
        )
    except Exception:  # noqa: BLE001
        _logger = __import__("logging").getLogger(__name__)
        _logger.exception("team report persist failed")
        return
    if saved:
        yield {
            "type": "report_saved",
            "report_id": saved["id"],
            "title": saved["title"],
            "vt_symbol": saved["vt_symbol"],
        }


def _fallback_report(
    prefetch: dict[str, Any],
    scores: dict[str, Any],
    *,
    analyst_texts: dict[str, str] | None = None,
) -> str:
    vt = prefetch.get("vt_symbol") or ""
    name = prefetch.get("name") or vt
    emo = prefetch.get("emotion") or {}
    lines = [
        f"## {name}（{vt}）团队快评",
        f"**加权分** {scores.get('weighted')}（财务/风险/策略规则分）",
        "",
        "## 综合研判",
        "规则/分析师兜底摘要，供参考。",
        "",
        "### 财务",
        (analyst_texts or {}).get("financial") or str((scores.get("financial") or {}).get("summary") or "—"),
        "",
        "### 风险",
        (analyst_texts or {}).get("risk") or str((scores.get("risk") or {}).get("summary") or "—"),
        "",
        "### 策略与情绪",
        (analyst_texts or {}).get("strategy") or str((scores.get("strategy") or {}).get("summary") or "—"),
        f"情绪阶段：{emo.get('stage_label') or emo.get('stage') or '—'}",
        "",
        "> 未调用 LLM 或首席失败，以上为规则/分析师兜底摘要。禁止视为买卖建议。",
    ]
    return "\n".join(lines)


def run_team_analysis(
    db: Session,
    user_id: str,
    vt_symbol: str,
    *,
    mode: TeamMode = "fast",
) -> dict[str, Any]:
    """非流式：收集最终结果。"""
    out: dict[str, Any] = {"vt_symbol": vt_symbol, "scores": {}, "report": "", "mode": mode}
    for ev in stream_team_analysis(db, user_id, vt_symbol, mode=mode):
        if ev.get("agent") == "system" and ev.get("kind") == "done":
            out["vt_symbol"] = ev.get("vt_symbol") or vt_symbol
            out["name"] = ev.get("name") or ""
            out["weighted"] = ev.get("weighted")
            out["scores"] = ev.get("scores") or {}
            out["report"] = ev.get("report") or ""
            out["mode"] = ev.get("mode") or mode
        if ev.get("kind") == "error":
            out["error"] = ev.get("detail")
    return out
