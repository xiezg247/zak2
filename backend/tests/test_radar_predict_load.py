from unittest.mock import MagicMock

from app.services.radar_predict import load_predict


def test_load_predict_empty():
    db = MagicMock()
    db.execute.return_value.mappings.return_value.first.return_value = None
    out = load_predict(db)
    assert out.empty is True
    assert out.rows == []
    assert out.label.startswith("规则预测")
