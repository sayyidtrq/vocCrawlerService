from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

from scripts import simulate_multitenant


def test_all_multitenant_scenarios_use_only_a_temporary_database(tmp_path, monkeypatch, capsys):
    configured_path = tmp_path / "configured-database-must-not-be-opened.sqlite3"
    configured_url = f"sqlite+pysqlite:///{configured_path}"
    monkeypatch.setenv("DATABASE_URL", configured_url)
    monkeypatch.setenv("ONEBOX_SITE_ID", "169")
    monkeypatch.setenv("ONEBOX_COMPANY_ID", "999")
    monkeypatch.setenv("APIFY_API_TOKENS", "private-sentinel-apify")
    monkeypatch.setenv("OPENAI_API_KEY", "private-sentinel-openai")
    started = monotonic()

    report = simulate_multitenant.run([])

    output = capsys.readouterr().out
    assert monotonic() - started < 60
    assert report.failed_checks == 0, output
    assert report.passed_checks > 0
    assert report.scenarios == dict.fromkeys(simulate_multitenant.SCENARIOS, True)
    temporary_path = Path(report.database_path)
    assert temporary_path != configured_path
    assert temporary_path.parent.name.startswith("multitenant-simulation-")
    assert report.engine_paths == [str(temporary_path)]
    assert report.database_removed and not temporary_path.parent.exists()
    assert not configured_path.exists()
    assert os.environ["DATABASE_URL"] == configured_url
    assert os.environ["ONEBOX_COMPANY_ID"] == "999"
    assert "private-sentinel" not in output and "[FAIL]" not in output
