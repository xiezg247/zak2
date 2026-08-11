from unittest.mock import MagicMock

from app.services.quote_collect.models import QuoteSnapshot
from app.services.quote_collect.writer import RedisQuoteWriter


def test_write_empty_noop() -> None:
    client = MagicMock()
    assert RedisQuoteWriter(client).write_quotes({}) == 0
    client.pipeline.assert_not_called()
    client.publish.assert_not_called()


def test_write_quotes_pipeline_and_publish() -> None:
    client = MagicMock()
    pipe = MagicMock()
    client.pipeline.return_value = pipe
    pipe.execute.return_value = [7]  # seq from incr
    q = QuoteSnapshot(symbol="SHSE.600519", name="茅台", last_price=100.0, change_pct=1.5, amount=1e9)
    n = RedisQuoteWriter(client).write_quotes({"SHSE.600519": q})
    assert n == 1
    pipe.incr.assert_called()
    client.publish.assert_called_with("zak2:notify:quotes", "7")
