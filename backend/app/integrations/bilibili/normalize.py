"""B 站 API 响应 → FeedItemDraft。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class FeedItemDraft:
    external_id: str
    item_type: str
    title: str
    summary: str
    url: str
    author_name: str
    published_at: str  # ISO
    payload: dict


def normalize_dynamic(raw: dict[str, Any], *, author_name: str) -> FeedItemDraft | None:
    modules = raw.get("modules") or {}
    module_dynamic = modules.get("module_dynamic") or {}
    major = module_dynamic.get("major") or {}
    desc = module_dynamic.get("desc") or {}
    id_str = str(raw.get("id_str") or raw.get("id") or "").strip()
    if not id_str:
        return None

    title = ""
    summary = ""
    item_type = "dynamic"
    url = f"https://t.bilibili.com/{id_str}"
    cover_url = ""
    dynamic_type = str(raw.get("type") or "")

    archive = major.get("archive") or {}
    if archive:
        item_type = "video"
        bvid = str(archive.get("bvid") or "").strip()
        title = str(archive.get("title") or "").strip()
        summary = str(archive.get("desc") or "").strip() or _extract_rich_block(desc)
        if bvid:
            url = f"https://www.bilibili.com/video/{bvid}"
        cover_url = str(archive.get("cover") or "")
    else:
        opus = major.get("opus") or {}
        if opus:
            title = str(opus.get("title") or "").strip()
            summary = _extract_rich_block(opus.get("summary")) or _extract_rich_block(desc)
            cover_url = _first_image(opus)
        else:
            summary = _extract_rich_block(desc)
            draw = major.get("draw") or {}
            items = draw.get("items") or []
            if items and isinstance(items[0], dict):
                cover_url = str(items[0].get("src") or items[0].get("url") or "")
            if not summary and items:
                summary = f"图片动态（{len(items)} 张）"

    if not title:
        title = _first_line(summary) if summary else "新动态"

    pub_ts = int((modules.get("module_author") or {}).get("pub_ts") or 0)
    if pub_ts <= 0:
        pub_ts = int(raw.get("pub_ts") or 0)

    return FeedItemDraft(
        external_id=id_str,
        item_type=item_type,
        title=title,
        summary=summary[:500],
        url=url,
        author_name=author_name,
        published_at=_iso_from_unix(pub_ts),
        payload={
            "cover_url": cover_url,
            "dynamic_type": dynamic_type,
            "raw_pubdate": pub_ts,
        },
    )


def _extract_rich_block(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        text = str(value.get("text") or "").strip()
        nodes = _rich_text_nodes_to_text(value.get("rich_text_nodes"))
        return text or nodes
    if isinstance(value, list):
        return "\n".join(part for part in (_extract_rich_block(item) for item in value) if part)
    return ""


def _rich_text_nodes_to_text(nodes: Any) -> str:
    if not isinstance(nodes, list):
        return ""
    parts: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        piece = str(node.get("orig_text") or node.get("text") or "").strip()
        if piece:
            parts.append(piece)
    return "".join(parts)


def _first_line(text: str, max_len: int = 80) -> str:
    line = text.strip().split("\n", 1)[0].strip()
    if len(line) <= max_len:
        return line
    return f"{line[: max_len - 1]}…"


def _first_image(opus: dict[str, Any]) -> str:
    pics = opus.get("pics") or []
    if pics and isinstance(pics[0], dict):
        return str(pics[0].get("url") or pics[0].get("src") or "")
    return ""


def _iso_from_unix(ts: int) -> str:
    if ts <= 0:
        return datetime.now().isoformat(timespec="seconds")
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
