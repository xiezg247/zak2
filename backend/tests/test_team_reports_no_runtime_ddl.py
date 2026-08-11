from pathlib import Path

import app.services.team_reports as tr


def test_team_reports_has_no_create_table_ddl() -> None:
    src = Path(tr.__file__).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" not in src
