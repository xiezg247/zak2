"""股票代码格式转换（vt / exchange+symbol / TickFlow）。"""

from __future__ import annotations

# VeighNa exchange.name ↔ TickFlow 前缀
_VT_TO_TF = {"SSE": "SHSE", "SZSE": "SZSE", "BSE": "BJSE"}
_TF_TO_VT = {v: k for k, v in _VT_TO_TF.items()}
# TickFlow 官方 SDK 符号后缀（代码.SH / .SZ / .BJ）
_TF_TO_TC = {"SHSE": "SH", "SZSE": "SZ", "BJSE": "BJ"}
_TC_TO_TF = {v: k for k, v in _TF_TO_TC.items()}


def normalize_exchange(exchange: str) -> str:
    raw = (exchange or "").strip().upper()
    if raw in _VT_TO_TF:
        return raw
    if raw in _TF_TO_VT:
        return _TF_TO_VT[raw]
    if raw in {"SH", "SHA", "SHSE"}:
        return "SSE"
    if raw in {"SZ", "SZA"}:
        return "SZSE"
    if raw in {"BJ", "BJSE"}:
        return "BSE"
    return raw


def to_tf_symbol(symbol: str, exchange: str) -> str:
    code = symbol.strip()
    exch = normalize_exchange(exchange)
    return f"{_VT_TO_TF.get(exch, exch)}.{code}"


def to_vt_symbol(symbol: str, exchange: str) -> str:
    return f"{symbol.strip()}.{normalize_exchange(exchange)}"


def parse_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    """600519.SSE → (600519, SSE)。"""
    text = vt_symbol.strip().upper()
    if "." not in text:
        raise ValueError(f"无效 vt_symbol：{vt_symbol}")
    code, exch = text.rsplit(".", 1)
    return code, normalize_exchange(exch)


def to_tickflow_symbol(tf_symbol: str) -> str:
    """SHSE.600519 → 600519.SH（TickFlow 官方 SDK 符号格式）。"""
    text = (tf_symbol or "").strip()
    if "." not in text:
        return text
    exchange, code = text.split(".", 1)
    return f"{code}.{_TF_TO_TC.get(exchange, exchange)}"


def from_tickflow_symbol(tc_symbol: str) -> str:
    """600519.SH → SHSE.600519（zak2 内部 tf_symbol 格式）。"""
    text = (tc_symbol or "").strip()
    if "." not in text:
        return text
    code, exchange = text.split(".", 1)
    return f"{_TC_TO_TF.get(exchange, exchange)}.{code}"


def parse_flexible_symbol(raw: str) -> tuple[str, str]:
    """支持 600519.SSE / SHSE.600519 / 600519（默认 SSE/SZSE 按首位推断）。"""
    text = raw.strip().upper()
    if not text:
        raise ValueError("代码为空")
    if "." in text:
        left, right = text.split(".", 1)
        if left in _TF_TO_VT or left in {"SHSE", "SZSE", "BJSE"}:
            return right, normalize_exchange(left)
        return left, normalize_exchange(right)
    # 裸代码
    if text.startswith(("6", "9")):
        return text, "SSE"
    if text.startswith(("0", "3")):
        return text, "SZSE"
    if text.startswith(("4", "8")):
        return text, "BSE"
    return text, "SSE"
