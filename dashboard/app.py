
from pathlib import Path
import unicodedata

import duckdb
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "storage" / "processed" / "openmobility.duckdb"

st.set_page_config(
    page_title="OpenMobility AI",
    page_icon="🚌",
    layout="wide",
)

st.title("🚌 OpenMobility AI")
st.caption(
    "Public transport analytics | Reporting quality and scheduled service"
)


# ---------------------------------------------------------
# Database access
# ---------------------------------------------------------
if not DB_PATH.exists():
    st.error(f"DuckDB database not found: {DB_PATH}")
    st.stop()


@st.cache_data(ttl=60)
def get_tables():
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        return {
            row[0]
            for row in conn.execute("SHOW TABLES").fetchall()
        }


@st.cache_data(ttl=60)
def read_query(query):
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        return conn.execute(query).fetchdf()


tables = get_tables()

required_tables = {
    "mart_service_quality__summary",
    "mart_service_quality__quarterly",
    "mart_service_quality__data_quality_alerts",
}

missing_tables = required_tables - tables

if missing_tables:
    st.error(
        f"Missing required marts: {', '.join(sorted(missing_tables))}"
    )
    st.info("Run dbt build to create the required marts.")
    st.stop()


# ---------------------------------------------------------
# Load service-quality data
# ---------------------------------------------------------
summary = read_query(
    "SELECT * FROM mart_service_quality__summary"
)
quarterly = read_query(
    "SELECT * FROM mart_service_quality__quarterly"
)
alerts = read_query(
    "SELECT * FROM mart_service_quality__data_quality_alerts"
)


# ---------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------
st.sidebar.title("Dashboard filters")

operators = sorted(summary["operator"].dropna().unique().tolist())
modes = sorted(summary["mode"].dropna().unique().tolist())
themes = sorted(summary["theme"].dropna().unique().tolist())
years = sorted(
    summary["year"].dropna().astype(int).unique().tolist(),
    reverse=True,
)

selected_operators = st.sidebar.multiselect(
    "Transport operator",
    operators,
    default=operators,
)
selected_modes = st.sidebar.multiselect(
    "Transport mode",
    modes,
    default=modes,
)
selected_themes = st.sidebar.multiselect(
    "Service theme",
    themes,
    default=themes,
)
selected_years = st.sidebar.multiselect(
    "Reporting year",
    years,
    default=years,
)


def apply_filters(df):
    result = df.copy()

    filters = {
        "operator": selected_operators,
        "mode": selected_modes,
        "theme": selected_themes,
        "year": selected_years,
    }

    for column, selected_values in filters.items():
        if column in result.columns:
            result = result[
                result[column].astype(str).isin(
                    [str(value) for value in selected_values]
                )
            ]

    return result


summary_f = apply_filters(summary)
quarterly_f = apply_filters(quarterly)
alerts_f = apply_filters(alerts)


# ---------------------------------------------------------
# Dashboard tabs
# ---------------------------------------------------------
overview, trends, operators_tab, alerts_tab, gtfs_tab, map_tab = (
    st.tabs(
        [
            "Overview",
            "Reporting trends",
            "Operator comparison",
            "Data-quality alerts",
            "GTFS schedule",
            "Transport map",
        ]
    )
)


# ---------------------------------------------------------
# 1. Overview
# ---------------------------------------------------------
with overview:
    if summary_f.empty:
        st.warning("No data matches the selected filters.")
    else:
        source_records = int(
            summary_f["source_record_count"].sum()
        )
        missing_both = int(
            summary_f["missing_both_measurements"].sum()
        )

        missing_rate = (
            100 * missing_both / source_records
            if source_records
            else 0
        )
        completeness = 100 - missing_rate

        critical_alerts = int(
            summary_f["critical_alert_group_count"].sum()
        )
        high_alerts = int(
            summary_f["high_alert_group_count"].sum()
        )

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("Source records", f"{source_records:,}")
        c2.metric(
            "Measurement completeness",
            f"{completeness:.2f}%",
        )
        c3.metric(
            "Missing both measurements",
            f"{missing_both:,}",
        )
        c4.metric("Critical alert groups", f"{critical_alerts:,}")
        c5.metric("High alert groups", f"{high_alerts:,}")

        st.caption(
            "Reporting-quality indicators only. Missing measurements "
            "do not necessarily mean poor transport service."
        )

        st.subheader("Missing measurements by service theme")

        theme_data = (
            summary_f.groupby("theme", as_index=False)
            .agg(
                source_records=("source_record_count", "sum"),
                missing_records=(
                    "missing_both_measurements",
                    "sum",
                ),
            )
        )

        theme_data["missing_percentage"] = (
            100
            * theme_data["missing_records"]
            / theme_data["source_records"].replace(0, pd.NA)
        )

        theme_data = theme_data.sort_values(
            "missing_percentage",
            ascending=False,
        )

        fig = px.bar(
            theme_data,
            x="theme",
            y="missing_percentage",
            hover_data=["source_records", "missing_records"],
            labels={
                "theme": "Service theme",
                "missing_percentage": "Missing both measurements (%)",
                "source_records": "Source records",
                "missing_records": "Records missing both",
            },
            title="Reporting gaps by theme",
        )
        fig.update_layout(xaxis_tickangle=-35)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Annual summary")
        st.dataframe(
            summary_f.sort_values(
                "missing_both_percentage",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export summary to CSV",
            data=summary_f.to_csv(index=False).encode("utf-8"),
            file_name="openmobility_summary.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------
# 2. Reporting trends
# ---------------------------------------------------------
with trends:
    st.subheader("Quarterly reporting completeness")

    if quarterly_f.empty:
        st.info("No quarterly data matches these filters.")
    else:
        trend = (
            quarterly_f.groupby(
                ["year", "quarter"],
                as_index=False,
            )
            .agg(
                source_records=("record_count", "sum"),
                missing_records=(
                    "missing_both_measurements",
                    "sum",
                ),
            )
        )

        quarter_order = {
            "T1": 1,
            "T2": 2,
            "T3": 3,
            "T4": 4,
        }

        trend["quarter_number"] = trend["quarter"].map(
            quarter_order
        )
        trend["period"] = (
            trend["year"].astype(str) + " " + trend["quarter"]
        )
        trend = trend.sort_values(
            ["year", "quarter_number"]
        )

        trend["missing_percentage"] = (
            100
            * trend["missing_records"]
            / trend["source_records"].replace(0, pd.NA)
        )

        fig = px.line(
            trend,
            x="period",
            y="missing_percentage",
            markers=True,
            hover_data=["source_records", "missing_records"],
            labels={
                "period": "Reporting period",
                "missing_percentage": "Missing both measurements (%)",
            },
            title="Quarterly reporting gaps over time",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            trend.drop(columns=["quarter_number"]),
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# 3. Operator comparison
# ---------------------------------------------------------
with operators_tab:
    st.subheader("Reporting completeness by operator")

    if summary_f.empty:
        st.info("No data matches these filters.")
    else:
        operator_data = (
            summary_f.groupby("operator", as_index=False)
            .agg(
                source_records=("source_record_count", "sum"),
                missing_records=(
                    "missing_both_measurements",
                    "sum",
                ),
                critical_alerts=(
                    "critical_alert_group_count",
                    "sum",
                ),
                high_alerts=(
                    "high_alert_group_count",
                    "sum",
                ),
            )
        )

        operator_data["missing_percentage"] = (
            100
            * operator_data["missing_records"]
            / operator_data["source_records"].replace(0, pd.NA)
        )

        fig = px.bar(
            operator_data.sort_values(
                "missing_percentage",
                ascending=False,
            ),
            x="operator",
            y="missing_percentage",
            hover_data=[
                "source_records",
                "missing_records",
                "critical_alerts",
                "high_alerts",
            ],
            labels={
                "operator": "Operator",
                "missing_percentage": "Missing both measurements (%)",
            },
            title="Missing-measurement rate by operator",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            operator_data,
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------
# 4. Data-quality alerts
# ---------------------------------------------------------
with alerts_tab:
    st.subheader("Reporting-quality alerts")

    if alerts_f.empty:
        st.success("No alerts match the selected filters.")
    else:
        severity_data = (
            alerts_f.groupby(
                ["severity", "recommended_action"],
                as_index=False,
            )
            .size()
            .rename(columns={"size": "alert_groups"})
        )

        fig = px.bar(
            severity_data,
            x="severity",
            y="alert_groups",
            color="recommended_action",
            category_orders={
                "severity": [
                    "CRITICAL",
                    "HIGH",
                    "MODERATE",
                    "LOW",
                ]
            },
            labels={
                "severity": "Severity",
                "alert_groups": "Number of alert groups",
                "recommended_action": "Recommended action",
            },
            title="Alerts by severity and recommended action",
        )
        st.plotly_chart(fig, use_container_width=True)

        display_columns = [
            "operator",
            "mode",
            "theme",
            "indicator",
            "year",
            "quarter",
            "source_record_count",
            "missing_both_measurements",
            "missing_both_percentage",
            "severity",
            "small_sample_flag",
            "recommended_action",
        ]

        display_columns = [
            column
            for column in display_columns
            if column in alerts_f.columns
        ]

        st.dataframe(
            alerts_f[display_columns].sort_values(
                "missing_both_percentage",
                ascending=False,
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download alerts to CSV",
            data=alerts_f[display_columns].to_csv(
                index=False
            ).encode("utf-8"),
            file_name="openmobility_alerts.csv",
            mime="text/csv",
        )


# ---------------------------------------------------------
# 5. GTFS scheduled service
# ---------------------------------------------------------
with gtfs_tab:
    st.subheader("Scheduled service analytics")

    gtfs_marts = [
        "mart_gtfs__route_schedule_profile",
        "mart_gtfs__daily_route_service",
        "mart_gtfs__daily_service_quality",
    ]

    available_gtfs = [
        table for table in gtfs_marts
        if table in tables
    ]

    if not available_gtfs:
        st.info("No GTFS marts were found in the database.")
    else:
        selected_mart = st.selectbox(
            "Select GTFS mart",
            available_gtfs,
        )

        # Table name comes from the fixed allowlist above.
        gtfs_data = read_query(
            f'SELECT * FROM "{selected_mart}" LIMIT 5000'
        )

        st.caption(
            f"Showing up to 5,000 rows from {selected_mart}."
        )
        st.dataframe(
            gtfs_data,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download displayed GTFS data",
            data=gtfs_data.to_csv(index=False).encode("utf-8"),
            file_name=f"{selected_mart}.csv",
            mime="text/csv",
        )



# ---------------------------------------------------------
# 6. Interactive transport map
# ---------------------------------------------------------
with map_tab:
    st.subheader("Île-de-France transport stops")

    def normalize_text(value):
        """Normalize accents so searches like Defense match Défense."""
        return "".join(
            char
            for char in unicodedata.normalize("NFKD", str(value))
            if not unicodedata.combining(char)
        ).casefold()

    @st.cache_data(ttl=300)
    def load_stops():
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            return conn.execute("""
                SELECT
                    stop_id,
                    stop_name,
                    stop_longitude,
                    stop_latitude,
                    location_type,
                    wheelchair_boarding
                FROM stg_gtfs__stops
                WHERE stop_latitude BETWEEN 48.0 AND 49.3
                  AND stop_longitude BETWEEN 1.4 AND 3.6
                  AND stop_latitude IS NOT NULL
                  AND stop_longitude IS NOT NULL
            """).fetchdf()

    @st.cache_data(ttl=300)
    def load_routes():
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            return conn.execute("""
                SELECT DISTINCT
                    route_id,
                    COALESCE(NULLIF(TRIM(route_short_name), ''), route_id) AS route_short_name,
                    COALESCE(NULLIF(TRIM(route_long_name), ''), '') AS route_long_name,
                    route_type,
                    NULLIF(route_color, '') AS route_color,
                    NULLIF(route_text_color, '') AS route_text_color
                FROM stg_gtfs__routes
                ORDER BY route_type, route_short_name, route_long_name, route_id
            """).fetchdf()

    @st.cache_data(ttl=300)
    def load_route_stops(route_id):
        """Return stops served by a route, ordered by their minimum sequence."""
        with duckdb.connect(str(DB_PATH), read_only=True) as conn:
            return conn.execute("""
                SELECT
                    r.route_id,
                    r.route_short_name,
                    r.route_long_name,
                    r.route_type,
                    r.route_color,
                    t.trip_id,
                    st.stop_id,
                    MIN(st.stop_sequence) AS stop_sequence,
                    s.stop_name,
                    s.stop_longitude,
                    s.stop_latitude,
                    s.wheelchair_boarding
                FROM stg_gtfs__routes r
                JOIN stg_gtfs__trips t
                  ON t.route_id = r.route_id
                JOIN stg_gtfs__stop_times st
                  ON st.trip_id = t.trip_id
                JOIN stg_gtfs__stops s
                  ON s.stop_id = st.stop_id
                WHERE r.route_id = ?
                  AND s.stop_latitude IS NOT NULL
                  AND s.stop_longitude IS NOT NULL
                GROUP BY
                    r.route_id, r.route_short_name, r.route_long_name,
                    r.route_type, r.route_color, t.trip_id, st.stop_id,
                    s.stop_name, s.stop_longitude, s.stop_latitude,
                    s.wheelchair_boarding
                ORDER BY t.trip_id, stop_sequence
            """, [route_id]).fetchdf()

    stops = load_stops()
    routes = load_routes()

    mode_labels = {
        0: "Tram",
        1: "Metro",
        2: "RER / Train",
        3: "Bus",
        4: "Ferry",
        5: "Cable tram",
        6: "Cable car",
        7: "Funicular",
    }

    st.caption(
        f"{len(stops):,} stops available. Search is accent-insensitive; "
        "you can also select a transport mode and line."
    )

    search = st.text_input(
        "Find a stop or station",
        placeholder="e.g. La Défense, La Defense, Nation, Châtelet",
        key="map_stop_search",
    )

    map_stops = stops.copy()
    center_lat, center_lon, zoom_level = 48.8566, 2.3522, 9

    if search.strip():
        normalized_search = normalize_text(search.strip())
        normalized_names = map_stops["stop_name"].fillna("").map(normalize_text)
        matching = normalized_names.str.contains(normalized_search, regex=False)

        if matching.any():
            matched_stops = map_stops.loc[matching]
            center_lat = float(matched_stops["stop_latitude"].median())
            center_lon = float(matched_stops["stop_longitude"].median())
            nearby = (
                map_stops["stop_latitude"].between(center_lat - 0.025, center_lat + 0.025)
                & map_stops["stop_longitude"].between(center_lon - 0.035, center_lon + 0.035)
            )
            map_stops = map_stops.loc[matching | nearby].copy()
            zoom_level = 13
        else:
            st.warning(
                "No matching stop name was found. The search ignores accents, "
                "so try a shorter name such as 'Defense' or 'Nation'."
            )

    st.markdown("#### Explore a transport line")
    available_routes = routes.copy()
    available_routes["mode_label"] = available_routes["route_type"].map(mode_labels).fillna("Other")
    selected_mode = st.selectbox(
        "Transport mode",
        options=["All modes"] + sorted(available_routes["mode_label"].dropna().unique().tolist()),
        index=0,
        key="map_transport_mode",
    )
    if selected_mode != "All modes":
        available_routes = available_routes[available_routes["mode_label"] == selected_mode]

    available_routes["route_label"] = available_routes.apply(
        lambda row: (
            f"{row['route_short_name']} — {row['route_long_name']} "
            f"[{row['route_id']}]" if row["route_long_name"] and
            row["route_long_name"] != row["route_short_name"]
            else f"{row['route_short_name']} [{row['route_id']}]"
        ),
        axis=1,
    )
    route_options = available_routes[["route_id", "route_label"]].drop_duplicates()
    route_labels = route_options["route_label"].tolist()
    selected_route_label = st.selectbox(
        "Line / route",
        options=["No line selected"] + route_labels,
        key="map_selected_route",
    )

    selected_route_color = "FF4B4B"
    route_stops = pd.DataFrame()
    if selected_route_label != "No line selected":
        selected_route_id = route_options.loc[
            route_options["route_label"] == selected_route_label, "route_id"
        ].iloc[0]
        selected_route = available_routes.loc[available_routes["route_id"] == selected_route_id].iloc[0]
        route_stops = load_route_stops(selected_route_id)
        color_hex = str(selected_route.get("route_color") or "FF4B4B").strip().lstrip("#")
        if len(color_hex) == 6 and all(c in "0123456789ABCDEFabcdef" for c in color_hex):
            selected_route_color = color_hex.upper()
        route_rgb = [int(selected_route_color[i:i + 2], 16) for i in (0, 2, 4)]

        if route_stops.empty:
            st.warning("No stops were found for this route in the current GTFS tables.")
        else:
            # Focus map on the selected route and its stop sequence.
            map_stops = route_stops.drop_duplicates("stop_id").copy()
            center_lat = float(map_stops["stop_latitude"].median())
            center_lon = float(map_stops["stop_longitude"].median())
            zoom_level = 11
            st.caption(
                f"Selected route: {selected_route_label} · "
                f"{map_stops['stop_id'].nunique():,} distinct stops. "
                "Stop order is shown per scheduled trip because a route may have "
                "different directions or variants."
            )
            display_route_stops = route_stops[[
                "trip_id", "stop_sequence", "stop_name", "stop_id",
                "stop_longitude", "stop_latitude", "wheelchair_boarding"
            ]].copy()
            display_route_stops = display_route_stops.rename(columns={
                "trip_id": "Trip ID",
                "stop_sequence": "Stop sequence",
                "stop_name": "Stop name",
                "stop_id": "Stop ID",
                "stop_longitude": "Longitude",
                "stop_latitude": "Latitude",
                "wheelchair_boarding": "Wheelchair boarding",
            })
            with st.expander("View ordered stops by scheduled trip", expanded=True):
                st.dataframe(display_route_stops, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download route stops to CSV",
                    data=display_route_stops.to_csv(index=False).encode("utf-8"),
                    file_name="openmobility_route_stops.csv",
                    mime="text/csv",
                )
    else:
        route_rgb = [255, 75, 75]

    st.write(f"Stops displayed on map: {len(map_stops):,}")

    if not map_stops.empty:
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_stops,
            get_position="[stop_longitude, stop_latitude]",
            get_radius=100,
            radius_units="meters",
            radius_min_pixels=5,
            radius_max_pixels=12,
            get_fill_color=route_rgb,
            get_line_color=[255, 255, 255, 255],
            line_width_min_pixels=1,
            stroked=True,
            filled=True,
            opacity=0.9,
            pickable=True,
            auto_highlight=True,
        )

        deck = pdk.Deck(
            layers=[layer],
            initial_view_state=pdk.ViewState(
                latitude=float(center_lat),
                longitude=float(center_lon),
                zoom=zoom_level,
                pitch=0,
            ),
            map_style="light",
            tooltip={
                "html": (
                    "<b>{stop_name}</b><br/>"
                    "Stop ID: {stop_id}<br/>"
                    "Wheelchair boarding: {wheelchair_boarding}"
                ),
                "style": {"backgroundColor": "white", "color": "black"},
            },
        )
        st.pydeck_chart(deck, use_container_width=True)

        st.subheader("Stop details")
        detail_columns = [
            column for column in [
                "stop_name", "stop_id", "stop_sequence", "stop_longitude",
                "stop_latitude", "wheelchair_boarding"
            ] if column in map_stops.columns
        ]
        st.dataframe(
            map_stops[detail_columns].sort_values(
                "stop_sequence" if "stop_sequence" in detail_columns else "stop_name"
            ).head(100),
            use_container_width=True,
            hide_index=True,
        )
        if len(map_stops) > 100:
            st.caption("The table shows the first 100 stops; the map shows all matching stops.")


# Footer
# ---------------------------------------------------------
st.divider()
st.caption(
    "OpenMobility AI | Local analytics prototype | "
    "Scheduled service is not the same as observed service."
)
