import json
import os
import re
from typing import Any

import duckdb
import requests

from ai.data_access import (
    get_alerts_by_transport_mode,
    get_data_quality_alerts,
    get_reporting_completeness_by_transport_mode,
    get_service_quality_summary,
    search_routes,
    search_stops,
)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434",
).rstrip("/")

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "gemma4:26b",
)

SYSTEM_PROMPT = """
You are OpenMobility AI, an assistant for public transport data analysis.

Rules:
- Answer using only the database results provided in the prompt.
- Never invent database results, numbers, routes, stops, or trends.
- For routes, report the route name, route ID and route type when available.
- GTFS route_type 3 means Bus. Do not describe it as Bus Rapid Transit
  unless the database explicitly supports that description.
- For stop searches, list matching stop names and stop IDs.
- For reporting alerts, report severity, indicator, period, missing
  percentage, sample size and recommended action when available.
- Clearly distinguish missing measurements from poor transport service.
- Overall reporting completeness measures the availability of reporting
  measurements, not actual transport service quality.
- Clearly distinguish overall reporting completeness from urgent-alert
  missing rates.
- An urgent-alert missing rate applies only to records belonging to
  urgent alert groups.
- If there are no urgent alert groups, report the urgent missing rate
  as unavailable, never as 0%.
- Do not interpret missing measurements as poor transport service.
- Interpret comparisons between operators cautiously because their
  reporting populations and indicators may differ.
- Mention small sample sizes when relevant and when the database
  provides this information.
- GTFS data describes scheduled service, not necessarily actual service
  or delays.
- If no records match, say so.
- Be concise and stay focused on the user's question.
"""


FUNCTIONS = {
    "get_service_quality_summary": get_service_quality_summary,
    "get_data_quality_alerts": get_data_quality_alerts,
    "get_alerts_by_transport_mode": get_alerts_by_transport_mode,
    "search_stops": search_stops,
    "search_routes": search_routes,
    "get_reporting_completeness_by_transport_mode":
        get_reporting_completeness_by_transport_mode,
}

ALLOWED_ARGUMENTS = {
    "get_service_quality_summary": {"operator", "year"},
    "get_data_quality_alerts": {
        "severity",
        "operator",
        "recommended_action",
    },
    "get_alerts_by_transport_mode": {"operator"},
    "search_stops": {"search_term"},
    "search_routes": {"search_term"},
    "get_reporting_completeness_by_transport_mode": {"operator"},
}


def select_required_tool(question: str) -> str | None:
    """Choose the appropriate database function for the question."""
    q = question.casefold()

    asks_about_modes = any(
        term in q
        for term in (
            "transport mode",
            "transport modes",
            "by mode",
            "which mode",
            "modes",
        )
    )

    asks_about_completeness = any(
        term in q
        for term in (
            "urgent",
            "urgently",
            "investigation",
            "investigate",
            "missing measurement",
            "missing measurements",
            "completeness",
            "reporting-completeness",
        )
    )

    asks_about_urgent_alerts = any(
        term in q
        for term in (
            "urgent",
            "urgently",
            "investigate",
            "investigation",
        )
    )

    if asks_about_modes and asks_about_completeness:
        if asks_about_urgent_alerts:
            return "get_alerts_by_transport_mode"

        return "get_reporting_completeness_by_transport_mode"

    if any(
        word in q
        for word in ("stop", "stops", "station", "stations")
    ):
        return "search_stops"

    if any(
        word in q
        for word in ("route", "routes", "bus number")
    ):
        return "search_routes"

    if any(
        word in q
        for word in (
            "alert",
            "alerts",
            "completeness",
            "reporting-completeness",
        )
    ):
        return "get_data_quality_alerts"

    if any(
        word in q
        for word in ("service quality", "reporting metrics")
    ):
        return "get_service_quality_summary"

    return None


def extract_arguments(
    question: str,
    tool_name: str,
) -> dict[str, Any]:
    """Extract supported search terms and filters from a question."""
    arguments: dict[str, Any] = {}

    operator_match = re.search(
        r"\b(RATP|SNCF)\b",
        question,
        re.IGNORECASE,
    )

    operator = (
        operator_match.group(1).upper()
        if operator_match
        else None
    )

    if tool_name == "search_routes":
        match = re.search(
            r"\b(?:bus\s+route|route|bus)\s+"
            r"(?:number\s+)?([A-Za-z0-9-]+)\b",
            question,
            re.IGNORECASE,
        )
        if match:
            arguments["search_term"] = match.group(1).strip()

    elif tool_name == "search_stops":
        match = re.search(
            r"\bwith\s+(.+?)\s+in\s+their\s+name\b",
            question,
            re.IGNORECASE,
        )

        if not match:
            match = re.search(
                r"\b(?:stop|station)\s+"
                r"(?:named|called)\s+(.+?)(?:[?.!]|$)",
                question,
                re.IGNORECASE,
            )

        if match:
            arguments["search_term"] = match.group(1).strip()

    elif tool_name == "get_data_quality_alerts":
        if operator:
            arguments["operator"] = operator

        severity_match = re.search(
            r"\b(critical|high|moderate|low)\b",
            question,
            re.IGNORECASE,
        )
        if severity_match:
            arguments["severity"] = severity_match.group(1).upper()

        if re.search(
            r"\b(?:urgent|urgently|requiring urgent investigation|"
            r"require urgent investigation)\b",
            question,
            re.IGNORECASE,
        ):
            arguments["recommended_action"] = "INVESTIGATE_URGENTLY"

        elif re.search(
            r"\b(?:small sample|low sample size)\b",
            question,
            re.IGNORECASE,
        ):
            arguments["recommended_action"] = "LOW_SAMPLE_SIZE"

    elif tool_name in {
        "get_alerts_by_transport_mode",
        "get_reporting_completeness_by_transport_mode",
    }:
        if operator:
            arguments["operator"] = operator

    elif tool_name == "get_service_quality_summary":
        if operator:
            arguments["operator"] = operator

        year_match = re.search(r"\b(20\d{2})\b", question)
        if year_match:
            arguments["year"] = int(year_match.group(1))

    return arguments


def execute_tool(name: str, arguments: Any) -> dict:
    """Validate and execute one approved read-only data function."""
    if name not in FUNCTIONS:
        return {"error": f"Tool not allowed: {name}"}

    if not isinstance(arguments, dict):
        return {"error": "Tool arguments must be a JSON object."}

    if set(arguments) - ALLOWED_ARGUMENTS[name]:
        return {"error": "Unsupported argument supplied to tool."}

    if name in {"search_stops", "search_routes"}:
        term = arguments.get("search_term")
        if not isinstance(term, str) or not term.strip():
            return {"error": "A non-empty search_term is required."}

    if name == "get_service_quality_summary":
        year = arguments.get("year")
        if year is not None and (
            isinstance(year, bool)
            or not isinstance(year, int)
            or not 2000 <= year <= 2100
        ):
            return {
                "error": "year must be an integer between 2000 and 2100."
            }

    if name == "get_data_quality_alerts":
        severity = arguments.get("severity")
        if severity is not None and severity not in {
            "CRITICAL",
            "HIGH",
            "MODERATE",
            "LOW",
        }:
            return {"error": "Invalid alert severity."}

        recommended_action = arguments.get("recommended_action")
        if recommended_action is not None and recommended_action not in {
            "INVESTIGATE_URGENTLY",
            "LOW_SAMPLE_SIZE",
        }:
            return {"error": "Invalid recommended action."}

    if name == "get_alerts_by_transport_mode":
        operator = arguments.get("operator")

        if operator is not None:
            if not isinstance(operator, str) or not operator.strip():
                return {"error": "operator must be a non-empty string."}

            operator = operator.strip()

        arguments = {"operator": operator}

    try:
        result = FUNCTIONS[name](**arguments)
        return {"ok": True, "data": result}
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    except duckdb.Error as exc:
        print(f"[OpenMobility AI] DuckDB query failed: {exc}")
        return {
            "error": "The database query failed. Check the application logs."
        }


def format_fallback(
    tool_name: str,
    data: Any,
) -> str:
    """Format database results deterministically without relying on Ollama."""
    if not data:
        return "No matching records were found in the database."

    if not isinstance(data, list):
        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    if tool_name == "search_routes":
        lines = ["Matching routes:"]
        for row in data[:10]:
            route_name = (
                row.get("route_short_name")
                or row.get("route_long_name")
                or "Unknown"
            )
            route_type = row.get("route_type", "Unknown")
            type_label = "Bus" if route_type == 3 else str(route_type)
            lines.append(
                f"- Route: {route_name}"
                f" | ID: {row.get('route_id', 'Unknown')}"
                f" | Type: {type_label}"
            )
        return "\n".join(lines)

    if tool_name == "search_stops":
        lines = ["Matching stops:"]
        for row in data[:10]:
            lines.append(
                f"- {row.get('stop_name', 'Unknown')}"
                f" | ID: {row.get('stop_id', 'Unknown')}"
            )
        return "\n".join(lines)

    if tool_name == "get_data_quality_alerts":
        lines = ["Reporting-completeness alerts:"]
        for row in data[:10]:
            sample_warning = (
                " | Small sample size"
                if row.get("small_sample_flag")
                else ""
            )
            lines.append(
                f"- {row.get('severity', 'Unknown')} | "
                f"{row.get('operator', 'Unknown')} | "
                f"{row.get('mode', 'Unknown')} | "
                f"{row.get('theme', 'Unknown')} | "
                f"{row.get('indicator', 'Unknown')} | "
                f"Year: {row.get('year', 'Unknown')} | "
                f"Quarter: {row.get('quarter', 'Unknown')} | "
                f"Missing: "
                f"{row.get('missing_both_percentage', 'Unknown')}% | "
                f"Records: "
                f"{row.get('source_record_count', 'Unknown')} | "
                f"Missing count: "
                f"{row.get('missing_both_measurements', 'Unknown')} | "
                f"Action: "
                f"{row.get('recommended_action', 'Unknown')}"
                f"{sample_warning}"
            )
        return "\n".join(lines)

    if tool_name == "get_alerts_by_transport_mode":
        lines = [
            "Urgent reporting-completeness alerts by operator and transport mode:"
        ]

        for row in data:
            operator = row.get("operator", "Unknown")
            mode = row.get("transport_mode", "Unknown")
            count = row.get("urgent_alert_count", 0)
            missing_records = row.get("total_missing_records", 0)
            total_records = row.get("total_records", 0)
            missing_percentage = row.get("weighted_missing_percentage")

            if count == 0:
                lines.append(
                    f"- {operator} | {mode}: No urgent alerts."
                )
            else:
                lines.append(
                    f"- {operator} | {mode}: "
                    f"{count} urgent alerts, "
                    f"{missing_records}/{total_records} records missing "
                    f"({missing_percentage:.2f}%)."
                )

        return "\n".join(lines)

    if tool_name == "get_reporting_completeness_by_transport_mode":
        sorted_data = sorted(
            data,
            key=lambda row: (
                row.get("overall_completeness_percentage") is None,
                (
                    row.get("overall_completeness_percentage")
                    if row.get("overall_completeness_percentage") is not None
                    else float("inf")
                ),
            ),
        )

        lines = [
            "Reporting completeness by transport mode:",
            "",
            ("This metric measures the availability of reporting "
            "measurements, not actual transport service quality."),
            "",
        ]

        worst = next(
            (
                row
                for row in sorted_data
                if row.get("overall_completeness_percentage") is not None
            ),
            None,
        )

        if worst:
            lines.append(
                "Lowest reporting completeness: "
                f"{worst.get('operator', 'Unknown')} "
                f"{worst.get('transport_mode', 'Unknown')} "
                f"({worst['overall_completeness_percentage']:.2f}% complete)."
            )
            lines.append("")

        for row in sorted_data:
            operator_name = row.get("operator", "Unknown")
            mode = row.get("transport_mode", "Unknown")

            completeness = row.get("overall_completeness_percentage")
            missing = row.get("overall_missing_percentage")

            total_records = row.get("total_records", 0)
            missing_records = row.get("total_missing_records", 0)

            urgent_count = row.get("urgent_alert_count", 0)
            urgent_missing = row.get("urgent_missing_percentage")

            completeness_text = (
                f"{completeness:.2f}%"
                if completeness is not None
                else "Not available"
            )

            missing_text = (
                f"{missing:.2f}%"
                if missing is not None
                else "Not available"
            )

            lines.append(
                f"- {operator_name} | {mode}: "
                f"{completeness_text} complete; "
                f"{missing_text} missing "
                f"({missing_records} of {total_records} records)."
            )

            if urgent_count > 0:
                urgent_total = row.get("urgent_total_records", 0)
                urgent_missing_records = row.get(
                    "urgent_missing_records",
                    0,
                )

                urgent_missing_text = (
                    f"{urgent_missing:.2f}%"
                    if urgent_missing is not None
                    else "Not available"
                )

                lines.append(
                    f"  Urgent alerts: {urgent_count}; "
                    f"{urgent_missing_records} of {urgent_total} "
                    f"records missing both measurements "
                    f"({urgent_missing_text})."
                )
            else:
                lines.append(
                    "  Urgent alerts: None; "
                    "urgent missing rate: Not available."
                )

        lines.extend([
            "",
            "Interpretation:",
            "- Overall completeness measures reporting data availability.",
            ("- Urgent missing rate applies only to records within "
            "urgent alert groups."),
            "- No urgent alerts does not mean 0% missing.",
            ("- Cross-operator comparisons should be interpreted "
            "cautiously because reporting populations and indicators "
            "may differ."),
        ])

        return "\n".join(lines)

    return json.dumps(
        data[:10],
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def ask(question: str) -> str:
    """Answer using selected database results; use Ollama for summaries."""
    if not isinstance(question, str) or not question.strip():
        return "Please enter a question."

    question = question.strip()
    tool_name = select_required_tool(question)

    if tool_name is None:
        return (
            "I can currently answer questions about routes, stops, "
            "service-quality reporting metrics, and data-quality alerts."
        )

    arguments = extract_arguments(question, tool_name)

    if (
        tool_name in {"search_routes", "search_stops"}
        and not arguments.get("search_term")
    ):
        return (
            "Please specify the route number or stop name "
            "you want to search for."
        )

    print(f"[OpenMobility AI] Tool selected: {tool_name}")
    print(f"[OpenMobility AI] Arguments: {arguments}")

    result = execute_tool(tool_name, arguments)

    if "error" in result:
        return f"The database query failed: {result['error']}"

    data = result.get("data", [])

    if not data:
        return "No matching records were found in the database."

    # These tools have deterministic outputs: no LLM is needed to count,
    # filter, or list their database results.
    deterministic_tools = {
        "search_routes",
        "search_stops",
        "get_data_quality_alerts",
        "get_alerts_by_transport_mode",
        "get_reporting_completeness_by_transport_mode",
    }

    if tool_name in deterministic_tools:
        return format_fallback(tool_name, data)

    # Use Ollama to explain the service-quality summary, grounded only in
    # the selected database results.
    prompt = (
        f"User question:\n{question}\n\n"
        f"Database tool: {tool_name}\n"
        f"Database results (JSON):\n"
        f"{json.dumps(data[:50], ensure_ascii=False, default=str)}\n\n"
        "Answer the user's question using only these results. "
        "Do not invent facts or discuss unrelated topics. "
        "Clearly distinguish measurement completeness from actual "
        "transport service quality. Mention limited periods or samples "
        "when the data indicates them."
    )

    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=300,
        )
        response.raise_for_status()

        message = response.json().get("message", {})
        answer = message.get("content", "").strip()

        if answer:
            return answer

        print(
            "[OpenMobility AI] Empty model response; "
            "using database-results fallback."
        )
        return format_fallback(tool_name, data)

    except (requests.RequestException, ValueError) as exc:
        print(f"[OpenMobility AI] Ollama request failed: {exc}")
        return format_fallback(tool_name, data)