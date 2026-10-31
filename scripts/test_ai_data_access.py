from ai.data_access import (
    get_service_quality_summary,
    get_data_quality_alerts,
    search_stops,
    search_routes,
)


def show_result(label, rows):
    print(f"\n--- {label} ({len(rows)} rows) ---")
    for row in rows[:3]:
        print(row)


def main():
    show_result(
        "Service-quality summary",
        get_service_quality_summary(),
    )
    show_result(
        "Critical alerts",
        get_data_quality_alerts(severity="CRITICAL"),
    )
    show_result(
        "Stop search",
        search_stops("Nation"),
    )
    show_result(
        "Route search",
        search_routes("N34"),
    )


if __name__ == "__main__":
    main()
