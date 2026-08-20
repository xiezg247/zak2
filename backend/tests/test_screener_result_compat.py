"""选股结果读取端兼容：早期版本曾把 rows 列表直接存入 result_json。"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.domains.screener.service import _run_detail
from app.repositories import screener as repo


def _run(result_json: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="r1",
        condition="涨幅榜",
        source="tushare",
        row_count=2,
        total_scanned=100,
        created_at="2026-07-01 10:00:00",
        config_json='{"preset": "涨幅榜"}',
        result_json=result_json,
    )


def test_runs_to_csv_compat_with_list() -> None:
    legacy = [
        {"symbol": "600000", "name": "浦发银行", "last_price": 10.0},
        {"symbol": "000001", "name": "平安银行", "last_price": 12.5},
    ]
    text = repo.runs_to_csv(legacy)
    assert "浦发银行" in text
    assert "平安银行" in text
    lines = text.strip().splitlines()
    assert lines[0].startswith("symbol")


def test_runs_to_csv_compat_with_rows_dict() -> None:
    data = {"rows": [{"symbol": "600000", "name": "浦发银行"}], "row_count": 1}
    text = repo.runs_to_csv(data)
    assert "浦发银行" in text


def test_runs_to_csv_compat_with_empty() -> None:
    # 历史边界：None/非 dict 输入不再抛异常
    assert repo.runs_to_csv(None).startswith("symbol")
    assert repo.runs_to_csv("").startswith("symbol")


def test_run_detail_normalizes_legacy_list() -> None:
    row = _run(json.dumps([{"symbol": "600000", "name": "浦发银行"}]))
    detail = _run_detail(row)
    assert isinstance(detail.result, dict)
    assert detail.result["rows"] == [{"symbol": "600000", "name": "浦发银行"}]
    assert detail.row_count == 2  # 保留原始列


def test_run_detail_passthrough_dict() -> None:
    payload = {"rows": [{"symbol": "600000"}], "row_count": 1}
    row = _run(json.dumps(payload))
    detail = _run_detail(row)
    assert detail.result == payload
