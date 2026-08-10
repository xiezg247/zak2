"""B 站空间动态。"""

from __future__ import annotations

from typing import Any

from app.integrations.bilibili.client import BilibiliApiError, BilibiliClient

_SPACE_FEATURES = (
    "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,forwardListHidden,"
    "decorationCard,commentsNewVersion,onlyfansAssetsV2,ugcDelete,onlyfansQaCard"
)


def list_recent_dynamics(client: BilibiliClient, mid: str, *, count: int = 10) -> list[dict[str, Any]]:
    mid = str(mid).strip()
    if not mid:
        raise BilibiliApiError("mid 不能为空")
    count = max(1, min(int(count), 20))
    data = client.get_json(
        "/x/polymer/web-dynamic/v1/feed/space",
        params={
            "host_mid": mid,
            "offset": "",
            "platform": "web",
            "features": _SPACE_FEATURES,
        },
        signed=True,
    )
    items: list[dict[str, Any]] = []
    for item in data.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        items.append(item)
        if len(items) >= count:
            break
    return items
