import pytest

from ai import assistant


@pytest.mark.parametrize(
    ("question", "expected_tool"),
    [
        (
            "Which transport mode has the worst reporting completeness?",
            "get_reporting_completeness_by_transport_mode",
        ),
        (
            "Which RATP transport mode has the worst reporting completeness?",
            "get_reporting_completeness_by_transport_mode",
        ),
        (
            "Compare reporting completeness across all transport modes for SNCF.",
            "get_reporting_completeness_by_transport_mode",
        ),
        (
            "Which RATP transport mode has the highest missing-measurement rate among urgent alerts?",
            "get_alerts_by_transport_mode",
        ),
        (
            "Which transport modes have the lowest completeness?",
            "get_reporting_completeness_by_transport_mode",
        ),
    ],
)
def test_select_required_tool(question, expected_tool):
    assert assistant.select_required_tool(question) == expected_tool


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "Which transport mode has the worst reporting completeness?",
            {},
        ),
        (
            "Which RATP transport mode has the worst reporting completeness?",
            {"operator": "RATP"},
        ),
        (
            "Compare reporting completeness across all transport modes for SNCF.",
            {"operator": "SNCF"},
        ),
    ],
)
def test_extract_reporting_arguments(question, expected):
    tool = "get_reporting_completeness_by_transport_mode"

    assert assistant.extract_arguments(question, tool) == expected


def test_extract_urgent_alert_arguments():
    question = (
        "Which RATP transport mode has the highest "
        "missing-measurement rate among urgent alerts?"
    )

    assert assistant.extract_arguments(
        question,
        "get_alerts_by_transport_mode",
    ) == {"operator": "RATP"}


def test_format_reporting_completeness():
    data = [
        {
            "operator": "RATP",
            "transport_mode": "Métro",
            "overall_completeness_percentage": 87.5,
            "overall_missing_percentage": 12.5,
            "total_missing_records": 357,
            "total_records": 2855,
            "urgent_alert_count": 21,
            "urgent_total_records": 294,
            "urgent_missing_records": 246,
            "urgent_missing_percentage": 83.67,
        },
        {
            "operator": "SNCF",
            "transport_mode": "Bus",
            "overall_completeness_percentage": 100.0,
            "overall_missing_percentage": 0.0,
            "total_missing_records": 0,
            "total_records": 64,
            "urgent_alert_count": 0,
            "urgent_total_records": 0,
            "urgent_missing_records": 0,
            "urgent_missing_percentage": None,
        },
    ]

    result = assistant.format_fallback(
        "get_reporting_completeness_by_transport_mode",
        data,
    )

    assert "Lowest reporting completeness" in result
    assert "RATP Métro" in result
    assert "87.50% complete" in result
    assert "12.50% missing" in result
    assert "357 of 2855 records" in result
    assert "246 of 294 records" in result
    assert "83.67%" in result
    assert "SNCF | Bus" in result
    assert "urgent missing rate: Not available" in result
    assert "No urgent alerts does not mean 0% missing" in result
    assert "actual transport service quality" in result


def test_reporting_completeness_sorts_lowest_first():
    data = [
        {
            "operator": "SNCF",
            "transport_mode": "Bus",
            "overall_completeness_percentage": 100.0,
            "overall_missing_percentage": 0.0,
            "total_missing_records": 0,
            "total_records": 64,
            "urgent_alert_count": 0,
            "urgent_missing_percentage": None,
        },
        {
            "operator": "RATP",
            "transport_mode": "Métro",
            "overall_completeness_percentage": 87.5,
            "overall_missing_percentage": 12.5,
            "total_missing_records": 357,
            "total_records": 2855,
            "urgent_alert_count": 21,
            "urgent_missing_percentage": 83.67,
        },
    ]

    result = assistant.format_fallback(
        "get_reporting_completeness_by_transport_mode",
        data,
    )

    assert result.index("RATP | Métro") < result.index("SNCF | Bus")


def test_reporting_completeness_handles_null_completeness():
    data = [
        {
            "operator": "SNCF",
            "transport_mode": "Bus",
            "overall_completeness_percentage": None,
            "overall_missing_percentage": None,
            "total_missing_records": 0,
            "total_records": 0,
            "urgent_alert_count": 0,
            "urgent_missing_percentage": None,
        },
        {
            "operator": "RATP",
            "transport_mode": "Métro",
            "overall_completeness_percentage": 87.5,
            "overall_missing_percentage": 12.5,
            "total_missing_records": 357,
            "total_records": 2855,
            "urgent_alert_count": 21,
            "urgent_missing_percentage": 83.67,
        },
    ]

    result = assistant.format_fallback(
        "get_reporting_completeness_by_transport_mode",
        data,
    )

    assert result.index("RATP | Métro") < result.index("SNCF | Bus")
    assert "Not available complete" in result


def test_ask_uses_reporting_completeness_tool(monkeypatch):
    expected_data = [
        {
            "operator": "RATP",
            "transport_mode": "Métro",
            "overall_completeness_percentage": 87.5,
            "overall_missing_percentage": 12.5,
            "total_missing_records": 357,
            "total_records": 2855,
            "urgent_alert_count": 21,
            "urgent_total_records": 294,
            "urgent_missing_records": 246,
            "urgent_missing_percentage": 83.67,
        }
    ]

    monkeypatch.setitem(
        assistant.FUNCTIONS,
        "get_reporting_completeness_by_transport_mode",
        lambda **kwargs: expected_data,
    )

    result = assistant.ask(
        "Which RATP transport mode has the worst reporting completeness?"
    )

    assert "RATP | Métro" in result
    assert "87.50% complete" in result


def test_execute_tool_rejects_unsupported_arguments():
    result = assistant.execute_tool(
        "get_reporting_completeness_by_transport_mode",
        {"unexpected": "value"},
    )

    assert "error" in result