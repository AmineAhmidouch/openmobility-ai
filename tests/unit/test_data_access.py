
import pytest

from ai import data_access


def test_reporting_completeness_query_all_operators(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(data_access, "_query", fake_query)

    result = data_access.get_reporting_completeness_by_transport_mode()

    assert result == []
    assert captured["params"] == []
    assert "FROM mart_service_quality__summary" in captured["sql"]
    assert "FROM mart_service_quality__data_quality_alerts" in captured["sql"]
    assert "GROUP BY operator, mode" in captured["sql"]
    assert "overall_missing_percentage DESC NULLS LAST" in captured["sql"]


def test_reporting_completeness_query_filters_operator(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(data_access, "_query", fake_query)

    data_access.get_reporting_completeness_by_transport_mode("SNCF")

    assert captured["params"] == ["SNCF", "SNCF"]
    assert captured["sql"].count("LOWER(TRIM(operator)) = LOWER(?)") == 2


@pytest.mark.parametrize("operator", ["", "   ", None, 123])
def test_reporting_completeness_rejects_invalid_operator(operator):
    if operator is None:
        return

    with pytest.raises(ValueError, match="operator must be a non-empty string"):
        data_access.get_reporting_completeness_by_transport_mode(operator)


def test_reporting_completeness_allows_no_operator():
    # No operator filter is valid: this is the all-operator comparison.
    assert callable(data_access.get_reporting_completeness_by_transport_mode)


def test_urgent_alert_query_uses_weighted_percentage(monkeypatch):
    captured = {}

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(data_access, "_query", fake_query)

    data_access.get_alerts_by_transport_mode("RATP")

    assert captured["params"] == ["RATP", "RATP"]
    assert "INVESTIGATE_URGENTLY" in captured["sql"]
    assert "SUM(missing_both_measurements)" in captured["sql"]
    assert "SUM(source_record_count)" in captured["sql"]

def test_urgent_alert_query_all_operators():
    from ai.data_access import get_alerts_by_transport_mode

    results = get_alerts_by_transport_mode()

    assert results
    assert all("operator" in row for row in results)

    operators = {row["operator"] for row in results}

    assert "RATP" in operators
    assert "SNCF" in operators
    assert "KEOLIS" in operators


def test_urgent_alert_query_filters_operator():
    from ai.data_access import get_alerts_by_transport_mode

    results = get_alerts_by_transport_mode("RATP")

    assert results
    assert all(row["operator"] == "RATP" for row in results)


def test_urgent_alert_query_rejects_invalid_operator():
    import pytest

    from ai.data_access import get_alerts_by_transport_mode

    with pytest.raises(ValueError):
        get_alerts_by_transport_mode("   ")