"""
All visual rendering for the Ford GoBike dashboard.
this module uses PyDeck for maps.
Every function here takes an already-filtered DataFrame and just renders it.
Density maps is carried by hexagon colour, flows by straight lines with teal origin / amber destination endpoints.
"""

import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st


TOP_N_FLOWS = 15  # max destination lines drawn per selected origin station

# Basemap options. "Streets" is CARTO's Voyager style: labeled roads, place
# names, distinguishable land/water - much more legible than a flat tile.
# "Dark" stays available as a fallback if Streets ever feels too busy next to
# the hexagon/line colours.
BASEMAP_STYLES = {
    "Streets": "road",
    "Dark": "dark",
}

# --- تم تحديث الألوان لتتطابق مع الـ Palette الجديدة (Rose / Near-black) ---
ORIGIN_COLOR = [239, 70, 118]       # Rose (بدلاً من Teal)
DESTINATION_COLOR = [42, 40, 48]   # Near-black/Ink (بدلاً من Amber)

# Line colour gradient: light rose -> dark ink
LINE_COLOR_LIGHT = (242, 166, 190)
LINE_COLOR_DARK = (21, 20, 26)
LINE_WIDTH_PIXELS = 3  # fixed width - trip count is now carried by colour, not thickness
CLICK_TARGET_RADIUS_METERS = 40    # size of each clickable station marker on the density map
NEIGHBORHOOD_RADIUS_METERS = 300   # matches the hexagon bin radius - defines "same area" on click


def _trip_count_to_color(trip_counts, alpha=210):
    """
    Map a Series of trip counts to an RGBA colour per row, interpolating between
    LINE_COLOR_LIGHT (fewest trips) and LINE_COLOR_DARK (most trips) - the same
    "darker = busier" logic as the hexagon density layer.
    """
    counts = trip_counts.astype(float)
    low, high = counts.min(), counts.max()
    if high == low:
        # Only one distinct count in this selection - render everything at full intensity.
        norm = counts * 0 + 1.0
    else:
        norm = (counts - low) / (high - low)

    colors = []
    for n in norm:
        rgb = [
            int(LINE_COLOR_LIGHT[i] + (LINE_COLOR_DARK[i] - LINE_COLOR_LIGHT[i]) * n)
            for i in range(3)
        ]
        colors.append(rgb + [alpha])
    return colors

# ------------------------------------------------------------------
# AREA BOOKMARKS
# ------------------------------------------------------------------
# Each entry filters the data AND positions the camera, so you only ever see
# one region at a time instead of two distant blobs on a zoomed-out map.
#
# [FLAG] You said two areas - I've included the three the Bay Wheels system
# normally covers. Delete whichever one your data doesn't contain, or adjust
# the bounds if your stations fall outside them.
AREA_PRESETS = {
    "San Francisco": {
        "lat_min": 37.70, "lat_max": 37.84,
        "lon_min": -122.53, "lon_max": -122.35,
        "zoom": 12.5,
    },
    "East Bay": {
        "lat_min": 37.74, "lat_max": 37.90,
        "lon_min": -122.34, "lon_max": -122.15,
        "zoom": 11.0,
    },
    "San Jose": {
        "lat_min": 37.26, "lat_max": 37.42,
        "lon_min": -122.00, "lon_max": -121.82,
        "zoom": 12.5,
    },
}


def area_names():
    """Options for the area selector in app.py."""
    return list(AREA_PRESETS.keys())


def basemap_names():
    """Options for the basemap selector in app.py."""
    return list(BASEMAP_STYLES.keys())


def filter_to_area(data, area_name):
    """Keep only trips whose START station falls inside the chosen area."""
    bounds = AREA_PRESETS[area_name]
    return data[
        data["start_lat"].between(bounds["lat_min"], bounds["lat_max"])
        & data["start_lon"].between(bounds["lon_min"], bounds["lon_max"])
    ]


def _as_float_positions(data, lon_col, lat_col):
    """
    Build an explicit [lon, lat] array column instead of relying on pydeck's
    list-of-column-names accessor. Also forces native float (not numpy/Decimal),
    which is what actually caused the runaway lines: PostgreSQL NUMERIC columns
    arrive as Python Decimal, which serializes badly and gets read by deck.gl
    as 0.0 for some rows - sending those points to (0, 0), way off the coast
    of Africa, which is the "line going to a far distance" you saw.
    """
    lon = data[lon_col].astype(float)
    lat = data[lat_col].astype(float)
    return list(zip(lon, lat))


def _flat_view(latitude, longitude, zoom):
    """A strictly top-down view. pitch=0 and bearing=0 keep the map 2D."""
    return pdk.ViewState(
        latitude=float(latitude),
        longitude=float(longitude),
        zoom=zoom,
        pitch=0,
        bearing=0,
    )


# ------------------------------------------------------------------
# CHARTS
# ------------------------------------------------------------------
def render_charts(data):
    top_stations = (
        data.groupby("start_station", as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
        .nlargest(10, "trip_count")
        .sort_values("trip_count")
    )
    station_chart = px.bar(
        top_stations,
        x="trip_count",
        y="start_station",
        orientation="h",
        title="Top 10 start stations",
        labels={"trip_count": "Trips", "start_station": ""},
        color="trip_count",
        color_continuous_scale=["#FDEAF0", "#EF4676"],  # تم التعديل لتتوافق مع الـ Palette
    )
    station_chart.update_layout(coloraxis_showscale=False, height=430)

    demographic_data = (
        data.groupby(["age_group", "gender"], as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
    )
    demographic_chart = px.bar(
        demographic_data,
        x="age_group",
        y="trip_count",
        color="gender",
        barmode="group",
        title="Trips by gender and age group",
        labels={"trip_count": "Trips", "age_group": "Age group", "gender": "Gender"},
        color_discrete_sequence=["#EF4676", "#2A2830"],  # تم التعديل لتتوافق مع الـ Palette
    )
    demographic_chart.update_layout(height=430)

    left, right = st.columns(2)
    left.plotly_chart(station_chart, use_container_width=True)
    right.plotly_chart(demographic_chart, use_container_width=True)


# ------------------------------------------------------------------
# MAP MODE 1: DENSITY (flat hexagons, colour = volume, click to drill in)
# ------------------------------------------------------------------
def _station_summary(data):
    """
    One row per start station with its total trip count. Feeding the map
    station-level rows (rather than one row per trip) means a clicked hexagon
    hands back real station names and counts, not thousands of bare points.
    """
    summary = (
        data.groupby(["start_station", "start_lat", "start_lon"], as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
    )
    summary["position"] = _as_float_positions(summary, "start_lon", "start_lat")
    return summary


def render_density_map(data, area_name, basemap="Streets"):
    st.subheader(f"Start station activity - {area_name}")
    st.caption(
        "Trips aggregated into hexagon bins, weighted by trip count. Colour intensity "
        "reflects total trips - darker bins are busier."
    )

    bounds = AREA_PRESETS[area_name]
    station_summary = _station_summary(data)

    
    hex_layer = pdk.Layer(
        "HexagonLayer",
        data=station_summary,
        get_position="position",
        get_color_weight="trip_count",
        color_aggregation=pdk.types.String("SUM"),
        radius=300,
        extruded=False,    
        opacity=0.70,       # lets the basemap streets read through
        coverage=0.95,
        pickable=True,
        auto_highligh=True,
        color_range=[
            [253, 234, 239],  # تدرجات متناسقة مع لون Rose
            [248, 178, 201],
            [243, 122, 162],
            [239, 70, 118],
            [214, 51, 95],
            [180, 36, 78],
            [146, 21, 61],
            [112, 10, 45],
            [78, 0, 30],      # داكن جداً
        ],
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[hex_layer],
            initial_view_state=_flat_view(
                data["start_lat"].mean(), data["start_lon"].mean(), bounds["zoom"]
            ),
            map_style=BASEMAP_STYLES[basemap],
            tooltip={"text": "{colorValue} trips in this area"},
        )
    )


# ------------------------------------------------------------------
# MAP MODE 3: ALL STATIONS - a trip-count range slider hides/shows stations
# ------------------------------------------------------------------
def render_all_stations_map(data, area_name, basemap="Streets"):
    st.subheader(f"All stations - {area_name}")

    station_summary = _station_summary(data)
    if station_summary.empty:
        st.info("No stations in this area match the current filters.")
        return

    bounds = AREA_PRESETS[area_name]
    min_trips = int(station_summary["trip_count"].min())
    max_trips = int(station_summary["trip_count"].max())

    if min_trips == max_trips:
        st.caption(f"Every station here has exactly {min_trips:,} trips - nothing to filter.")
        trip_range = (min_trips, max_trips)
    else:
        trip_range = st.slider(
            "Trip count range",
            min_value=min_trips,
            max_value=max_trips,
            value=(min_trips, max_trips),
            key="heba_station_trip_range",
        )

    visible = station_summary[
        station_summary["trip_count"].between(trip_range[0], trip_range[1])
    ]

    st.caption(
        f"Showing {len(visible)} of {len(station_summary)} stations with "
        f"{trip_range[0]:,}-{trip_range[1]:,} trips."
    )

    if visible.empty:
        st.info("No stations fall in that trip count range.")
        return

    station_layer = pdk.Layer(
        "ScatterplotLayer",
        data=visible,
        get_position="position",
        get_fill_color=ORIGIN_COLOR + [200],
        get_radius="trip_count",
        radius_scale=1,
        radius_min_pixels=4,
        radius_max_pixels=24,
        pickable=True,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[station_layer],
            initial_view_state=_flat_view(
                data["start_lat"].mean(), data["start_lon"].mean(), bounds["zoom"]
            ),
            map_style=BASEMAP_STYLES[basemap],
            tooltip={"text": "{start_station}: {trip_count} trips"},
        )
    )

# ------------------------------------------------------------------
# MAP MODE 2: FLOWS (straight 2D lines + coloured endpoints)
# ------------------------------------------------------------------
def render_flow_map(data, area_name, basemap="Streets"):
    st.subheader(f"Trip flows - {area_name}")

    station_options = sorted(data["start_station"].dropna().unique().tolist())
    if not station_options:
        st.info("No stations in this area match the current filters.")
        return

    selected_station = st.selectbox("Origin station", station_options)

    station_trips = data[data["start_station"] == selected_station]
    flow_counts = (
        station_trips.groupby(
            ["end_station", "start_lat", "start_lon", "end_lat", "end_lon"],
            as_index=False,
        )
        .size()
        .rename(columns={"size": "trip_count"})
        .nlargest(TOP_N_FLOWS, "trip_count")
    )

    if flow_counts.empty:
        st.info("No trips leave this station under the current filters.")
        return

    # Explicit [lon, lat] array columns - see _as_float_positions for why this
    # matters (Decimal-from-Postgres was sending some points to (0, 0)).
    flow_counts["source_position"] = _as_float_positions(flow_counts, "start_lon", "start_lat")
    flow_counts["target_position"] = _as_float_positions(flow_counts, "end_lon", "end_lat")
    flow_counts["line_color"] = _trip_count_to_color(flow_counts["trip_count"])

    # Straight lines, fixed width. Trip count is carried by colour intensity
    # (darker teal = more trips), matching the hexagon density layer's logic.
    line_layer = pdk.Layer(
        "LineLayer",
        data=flow_counts,
        get_source_position="source_position",
        get_target_position="target_position",
        get_color="line_color",
        get_width=LINE_WIDTH_PIXELS,
        width_min_pixels=1,
        width_max_pixels=3,
        width_units="pixels",
        pickable=True,
    )

    # Amber dots mark destinations.
    destination_layer = pdk.Layer(
        "ScatterplotLayer",
        data=flow_counts,
        get_position="target_position",
        get_fill_color=DESTINATION_COLOR + [200],
        get_radius=60,
        radius_min_pixels=4,
        radius_max_pixels=10,
        pickable=True,
    )

    # One larger teal dot marks the origin.
    origin_row = flow_counts.head(1)
    origin_layer = pdk.Layer(
        "ScatterplotLayer",
        data=origin_row,
        get_position="source_position",
        get_fill_color=ORIGIN_COLOR + [230],
        get_radius=110,
        radius_min_pixels=7,
        radius_max_pixels=16,
    )

    st.pydeck_chart(
        pdk.Deck(
            layers=[line_layer, destination_layer, origin_layer],
            initial_view_state=_flat_view(
                origin_row["start_lat"].iloc[0],
                origin_row["start_lon"].iloc[0],
                AREA_PRESETS[area_name]["zoom"],
            ),
            map_style=BASEMAP_STYLES[basemap],
            tooltip={"text": "{end_station}: {trip_count} trips"},
        )
    )

    st.caption(
        f"Top {len(flow_counts)} destinations from {selected_station}. "
        "The large teal dot is the origin, amber dots are destinations, and line "
        "colour reflects trip volume - darker teal means more trips."
    )

    with st.expander("See underlying numbers"):
        st.dataframe(
            flow_counts[["end_station", "trip_count"]].reset_index(drop=True),
            use_container_width=True,
        )


# ------------------------------------------------------------------
# TOP-10 STATIONS CHART - toggle between start stations and end stations
# ------------------------------------------------------------------
def render_top_stations_chart(data):
    """
    One bar chart, switchable between "Top 10 start stations" and
    "Top 10 end stations" via a radio toggle. Uses the full filtered dataset
    (not scoped to the map's selected area), so it reads as a network-wide
    ranking alongside the area-scoped map above it.
    """
    direction = st.radio(
        "Rank by",
        ["Start stations", "End stations"],
        horizontal=True,
        key="heba_top_station_direction",
    )
    group_col = "start_station" if direction == "Start stations" else "end_station"
    title = "Top 10 start stations" if direction == "Start stations" else "Top 10 end stations"

    top = (
        data.groupby(group_col, as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
        .nlargest(10, "trip_count")
        .sort_values("trip_count")
    )

    if top.empty:
        st.info("No stations match the current filters.")
        return

    chart = px.bar(
        top,
        x="trip_count",
        y=group_col,
        orientation="h",
        title=title,
        labels={"trip_count": "Trips", group_col: ""},
        color_discrete_sequence=["#EF4676"],  # تم التعديل لتتوافق مع الـ Palette
    )
    chart.update_layout(showlegend=False, height=430)
    st.plotly_chart(chart, use_container_width=True)


# ------------------------------------------------------------------
# MAP CONTROLS - area / mode / basemap, laid out under the tab header
# ------------------------------------------------------------------
def render_map_controls():
    """
    Previously used a blank spacer column to push these right, which left
    dead space. Now the left side carries a section title instead, so the
    row is fully used rather than partly empty.
    Returns (selected_area, map_mode, basemap).
    """
    area_col, mode_col = st.columns([1, 1])
    with area_col:
        selected_area = st.selectbox("Area", area_names(), key="heba_area_select")
    with mode_col:
        map_mode = st.selectbox(
            "Map mode",
            ["Station density", "Trip flows", "All stations"],
            key="heba_map_mode_select",
        )
    basemap = st.radio(
        "Basemap", basemap_names(), horizontal=True, key="heba_basemap_select"
    )
    return selected_area, map_mode, basemap


# ------------------------------------------------------------------
# FULL "Station/Trip Analysis" TAB - controls, then map, then top-10 chart
# ------------------------------------------------------------------
def render_station_tab(data):
    """
    Single entry point for app.py's Station/Trip Analysis tab:
      1. Area / map mode / basemap controls, top right
      2. The map itself (density or flows), scoped to the selected area
      3. A top-10 stations chart, toggle start <-> end

    app.py just needs: heba_charts.render_station_tab(data)
    """
    if data.empty:
        st.info("No trips match the selected filters.")
        return

    selected_area, map_mode, basemap = render_map_controls()

    area_data = filter_to_area(data, selected_area)
    if area_data.empty:
        st.info(f"No trips in {selected_area} match the selected filters.")
    elif map_mode == "Station density":
        render_density_map(area_data, selected_area, basemap)
    elif map_mode == "Trip flows":
        render_flow_map(area_data, selected_area, basemap)
    else:
        render_all_stations_map(area_data, selected_area, basemap)

    st.divider()
    render_top_stations_chart(data)