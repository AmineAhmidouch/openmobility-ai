
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
    assert captured["sql"].count(
        "LOWER(TRIM(operator)) = LOWER(?)"
    ) == 2


@pytest.mark.parametrize("operator", ["", "   ", 123])
def test_reporting_completeness_rejects_invalid_operator(operator):
    with pytest.raises(
        ValueError,
        match="operator must be a non-empty string",
    ):
        data_access.get_reporting_completeness_by_transport_mode(operator)


def test_reporting_completeness_allows_no_operator():
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


def test_urgent_alert_query_all_operators(monkeypatch):
    captured = {}

    expected_results = [
        {"operator": "RATP", "transport_mode": "Métro"},
        {"operator": "SNCF", "transport_mode": "Train"},
        {"operator": "KEOLIS", "transport_mode": "Tram"},
    ]

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return expected_results

    monkeypatch.setattr(data_access, "_query", fake_query)

    results = data_access.get_alerts_by_transport_mode()

    assert results == expected_results
    assert captured["params"] == []
    assert "SELECT DISTINCT" in captured["sql"]
    assert "GROUP BY operator, mode" in captured["sql"]

    operators = {row["operator"] for row in results}

    assert operators == {"RATP", "SNCF", "KEOLIS"}


def test_urgent_alert_query_filters_operator(monkeypatch):
    captured = {}

    expected_results = [
        {"operator": "RATP", "transport_mode": "Métro"},
    ]

    def fake_query(sql, params=None):
        captured["sql"] = sql
        captured["params"] = params
        return expected_results

    monkeypatch.setattr(data_access, "_query", fake_query)

    results = data_access.get_alerts_by_transport_mode("RATP")

    assert results == expected_results
    assert captured["params"] == ["RATP", "RATP"]
    assert captured["sql"].count(
        "LOWER(TRIM(operator)) = LOWER(?)"
    ) == 2
    assert all(row["operator"] == "RATP" for row in results)


@pytest.mark.parametrize("operator", ["", "   ", 123])
def test_urgent_alert_query_rejects_invalid_operator(operator):
    with pytest.raises(
        ValueError,
        match="operator must be a non-empty string",
    ):
        data_access.get_alerts_by_transport_mode(operator)
