from ai.data_access import (
    get_data_quality_alerts,
    get_service_quality_summary,
    search_routes,
    search_stops,
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
