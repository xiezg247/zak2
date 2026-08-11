"""将 Tushare 因子补丁写入已有 zak2:quote HASH，并刷新相关榜。

榜重建仅含本批成功补丁的 TF（applied-only）：先 delete 再 zadd，
会丢掉未出现在本批中的旧成员（本刀可接受）。
"""

from __future__ import annotations

from typing import Any

from app.core.redis_keys import (
    META_SEQ_KEY,
    NOTIFY_CHANNEL,
    QUOTE_KEY_FMT,
    RANK_KEY_FMT,
)

FACTOR_FIELDS = (
    "turnover_rate",
    "volume_ratio",
    "total_mv",
    "circ_mv",
    "net_mf_amount",
)


def apply_factor_patches(client: Any, patches: dict[str, dict[str, float]]) -> dict[str, Any]:
    if not patches:
        return {"updated": 0, "seq": None, "published": False}

    applied: dict[str, dict[str, float]] = {}
    for tf, fields in patches.items():
        key = QUOTE_KEY_FMT.format(symbol=tf)
        if not client.exists(key):
            continue
        mapping = {
            k: str(float(v))
            for k, v in fields.items()
            if k in FACTOR_FIELDS and v is not None
        }
        if not mapping:
            continue
        client.hset(key, mapping=mapping)
        applied[tf] = {k: float(mapping[k]) for k in mapping}

    if not applied:
        return {"updated": 0, "seq": None, "published": False}

    pipe = client.pipeline(transaction=False)
    rebuild_turnover = any("turnover_rate" in f for f in applied.values())
    rebuild_volume_ratio = any("volume_ratio" in f for f in applied.values())
    rebuild_net_mf = any("net_mf_amount" in f for f in applied.values())

    turn: dict[str, float] = {}
    vr: dict[str, float] = {}
    nmf: dict[str, float] = {}
    for tf, f in applied.items():
        if "turnover_rate" in f:
            turn[tf] = f["turnover_rate"]
        if "volume_ratio" in f and f["volume_ratio"] > 0:
            vr[tf] = f["volume_ratio"]
        if "net_mf_amount" in f and f["net_mf_amount"] != 0:
            nmf[tf] = f["net_mf_amount"]

    if rebuild_turnover:
        pipe.delete(RANK_KEY_FMT.format(field="turnover_rate"))
        if turn:
            pipe.zadd(RANK_KEY_FMT.format(field="turnover_rate"), turn)
    if rebuild_volume_ratio:
        pipe.delete(RANK_KEY_FMT.format(field="volume_ratio"))
        if vr:
            pipe.zadd(RANK_KEY_FMT.format(field="volume_ratio"), vr)
    if rebuild_net_mf:
        pipe.delete(RANK_KEY_FMT.format(field="net_mf_amount"))
        if nmf:
            pipe.zadd(RANK_KEY_FMT.format(field="net_mf_amount"), nmf)
    pipe.incr(META_SEQ_KEY)
    results = pipe.execute()
    new_seq = int(results[-1])
    client.publish(NOTIFY_CHANNEL, str(new_seq))
    return {"updated": len(applied), "seq": new_seq, "published": True}
