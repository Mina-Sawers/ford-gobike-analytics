import importlib
import pandas as pd
import plotly.express as px
import streamlit as st


from Dashboard import youssef_charts

try:
    from Dashboard import heba_charts
except ImportError:
    heba_charts = None

st.set_page_config(
    page_title="Ford GoBike Analytics",
    page_icon="https://img.icons8.com/?size=100&id=O6GtnaATHUol&format=png&color=12B886",
    layout="wide"
)

# --- تم تنظيف الكود وحذف الـ CSS الخاطئ تماماً لتختفي أي سطور غير مرغوب فيها ---
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,450,0,0" rel="stylesheet">
<style>
.material-symbols-rounded {
    font-family: 'Material Symbols Rounded';
    font-weight: normal;
    font-style: normal;
    font-size: 22px;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
    vertical-align: middle;
    color: #0f766e;
}
</style>
""", unsafe_allow_html=True)



TWO_TONE_COLORS = ["#0f766e", "#14b8a6"]

@st.cache_resource
def get_connection():
    return st.connection(
        "postgresql",
        type="sql",
        url="postgresql://postgres:123@localhost:5432/ford_gobike"
    )

@st.cache_data(ttl=600)
def load_filter_options():
    connection = get_connection()
    user_types = connection.query(
        "SELECT DISTINCT user_type::text AS value FROM dim_user ORDER BY value", ttl=600
    )["value"].tolist()
    genders = connection.query(
        "SELECT DISTINCT gender::text AS value FROM dim_user ORDER BY value", ttl=600
    )["value"].tolist()
    age_groups = connection.query(
        "SELECT DISTINCT age_group::text AS value FROM dim_user ORDER BY value", ttl=600
    )["value"].tolist()
    return user_types, genders, age_groups

def _in_clause(column, values, params, prefix):
    names = []
    for index, value in enumerate(values):
        key = f"{prefix}_{index}"
        names.append(f":{key}")
        params[key] = value
    return f"{column} IN ({', '.join(names)})"

def build_filter_clause(user_types, genders, age_groups):
    clauses, params = [], {}
    if user_types:
        clauses.append(_in_clause("u.user_type::text", user_types, params, "ut"))
    if genders:
        clauses.append(_in_clause("u.gender::text", genders, params, "g"))
    if age_groups:
        clauses.append(_in_clause("u.age_group::text", age_groups, params, "ag"))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params

@st.cache_data(ttl=300)
def load_dashboard_data(user_types=(), genders=(), age_groups=()):
    where, params = build_filter_clause(user_types, genders, age_groups)
    query = f"""
        SELECT
            t.trip_id,
            t.duration_sec,
            t.duration_minute,
            t.bike_id,
            ss.station_name AS start_station,
            ss.latitude AS start_lat,
            ss.longitude AS start_lon,
            es.station_name AS end_station,
            es.latitude AS end_lat,
            es.longitude AS end_lon,
            u.gender::text AS gender,
            u.gender::text AS member_gender,
            u.age AS age,
            u.age_group::text AS age_group,
            u.user_type::text AS user_type
        FROM fact_trips AS t
        JOIN dim_station AS ss ON ss.station_id = t.start_station_id
        JOIN dim_station AS es ON es.station_id = t.end_station_id
        JOIN dim_user AS u ON u.user_id = t.user_id
        {where}
    """
    return get_connection().query(query, params=params, ttl=300)

def render_sidebar(user_types, genders, age_groups, total_records):
    with st.sidebar:
        st.markdown(
            """<div style="text-align: center; padding: 10px 0;">
                <h3 style="margin: 0; color: #0f766e; font-size: 18px; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <span class="material-symbols-rounded">directions_bike</span>
                    GoBike Control Panel
                </h3>
                <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">Analytics & Filtering Hub</p>
            </div>""",
            unsafe_allow_html=True
        )
        st.divider()
        
        col_icon, col_btn = st.columns([1, 4])
        with col_icon:
            st.markdown(
                """<div style="padding-top: 5px;">
                    <span class="material-symbols-rounded" title="Reset Filters">restart_alt</span>
                </div>""",
                unsafe_allow_html=True
            )
        with col_btn:
            if st.button("Reset Filters", use_container_width=True):
                st.session_state.clear()
                st.rerun()
            
        st.divider()
        
        selected_user_types = st.multiselect("User type", user_types, default=user_types, key="ut_filter")
        selected_genders = st.multiselect("Gender", genders, default=genders, key="g_filter")
        selected_age_groups = st.multiselect("Age group", age_groups, default=age_groups, key="ag_filter")
        
        st.divider()
        st.markdown(
            """<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 5px;">
                <span class="material-symbols-rounded">dataset</span>
                <span style="font-weight: 600; font-size: 16px; color: #0f766e;">Dataset Summary</span>
            </div>""",
            unsafe_allow_html=True
        )
        st.info(f"Active Records: **{total_records:,}** trips")
        
    return tuple(selected_user_types), tuple(selected_genders), tuple(selected_age_groups)

def render_overview_section(data, total_raw_count):
    if data.empty:
        st.info("No trips match the selected filters.")
        return

    total_trips = len(data)
    average_duration = data["duration_minute"].mean()
    distinct_bikes = data["bike_id"].nunique()
    subscriber_share = (data["user_type"] == "Subscriber").mean() * 100
    
    filtered_percentage = (total_trips / total_raw_count) * 100 if total_raw_count > 0 else 100

    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(
            f"""<div style="padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0; background-color: #ffffff;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span class="material-symbols-rounded">directions_bike</span>
                    <span style="color: #555; font-size: 14px; font-weight: 600;">Total trips</span>
                </div>
                <div style="font-size: 26px; font-weight: bold; color: #111;">{total_trips:,}</div>
                <div style="font-size: 12px; color: #0f766e; margin-top: 4px;">↑ {filtered_percentage:.1f}% of total dataset</div>
            </div>""",
            unsafe_allow_html=True
        )
    with c2:
        st.markdown(
            f"""<div style="padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0; background-color: #ffffff;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span class="material-symbols-rounded">schedule</span>
                    <span style="color: #555; font-size: 14px; font-weight: 600;">Avg. duration</span>
                </div>
                <div style="font-size: 26px; font-weight: bold; color: #111;">{average_duration:.1f} min</div>
            </div>""",
            unsafe_allow_html=True
        )
    with c3:
        st.markdown(
            f"""<div style="padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0; background-color: #ffffff;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span class="material-symbols-rounded">directions_bike</span>
                    <span style="color: #555; font-size: 14px; font-weight: 600;">Distinct bikes</span>
                </div>
                <div style="font-size: 26px; font-weight: bold; color: #111;">{distinct_bikes:,}</div>
            </div>""",
            unsafe_allow_html=True
        )
    with c4:
        st.markdown(
            f"""<div style="padding: 12px; border-radius: 8px; border: 1px solid #e0e0e0; background-color: #ffffff;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                    <span class="material-symbols-rounded">groups</span>
                    <span style="color: #555; font-size: 14px; font-weight: 600;">Subscriber share</span>
                </div>
                <div style="font-size: 26px; font-weight: bold; color: #111;">{subscriber_share:.0f}%</div>
                <div style="width: 100%; background-color: #e0e0e0; border-radius: 4px; margin-top: 6px; height: 6px;">
                    <div style="width: {subscriber_share}%; background-color: #0f766e; height: 6px; border-radius: 4px;"></div>
                </div>
            </div>""",
            unsafe_allow_html=True
        )

def render_time_section(data):
    st.warning(
        "No usable date/time data exists in the database (see the sidebar "
        "note). Weekday/month breakdowns aren't possible with the current "
        "dataset. Showing duration distribution as a placeholder until a real "
        "time dimension is added."
    )
    if data.empty:
        return

    fig = px.histogram(
        data,
        x="duration_minute",
        nbins=40,
        title="Trip duration distribution (temporary stand-in)",
        labels={"duration_minute": "Duration (minutes)"},
        color_discrete_sequence=["#0f766e"]
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("⏱️ Duration & Time Insights")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(youssef_charts.fig_duration_histogram(data), use_container_width=True)
    with col2:
        st.plotly_chart(youssef_charts.fig_duration_by_user_type(data), use_container_width=True)

def render_user_section(data):
    if data.empty:
        st.info("No trips match the selected filters.")
        return

    demographics = (
        data.groupby(["age_group", "gender"], as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
    )
    age_gender_chart = px.bar(
        demographics,
        x="age_group",
        y="trip_count",
        color="gender",
        barmode="group",
        title="Trips by age group and gender",
        labels={"trip_count": "Trips", "age_group": "Age group", "gender": "Gender"},
        color_discrete_sequence=TWO_TONE_COLORS
    )

    user_type_counts = data["user_type"].value_counts().reset_index()
    user_type_counts.columns = ["user_type", "trip_count"]
    user_type_chart = px.pie(
        user_type_counts, names="user_type", values="trip_count", title="Subscriber vs Customer",
        color_discrete_sequence=TWO_TONE_COLORS
    )

    left, right = st.columns(2)
    left.plotly_chart(age_gender_chart, use_container_width=True)
    right.plotly_chart(user_type_chart, use_container_width=True)

    st.markdown("---")
    st.subheader("👥 Detailed User Demographics")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(youssef_charts.fig_user_type_donut(data), use_container_width=True)
        st.plotly_chart(youssef_charts.fig_gender_bar(data), use_container_width=True)
    with col2:
        st.plotly_chart(youssef_charts.fig_age_group_bar(data), use_container_width=True)
        st.plotly_chart(youssef_charts.fig_age_histogram(data), use_container_width=True)

def render_station_section(data):
    if data.empty:
        st.info("No trips match the selected filters.")
        return

    if heba_charts and hasattr(heba_charts, "render_station_tab"):
        #st.markdown("---")
        #st.subheader("📍 Spatial & Station Insights")
        try:
            heba_charts.render_station_tab(data)
            return
        except Exception as e:
            st.error(f"Error rendering Heba's charts: {e}")
    else:
        st.info("Waiting on Heba's station/spatial charts module.")

def main():
    st.markdown("### <span class='material-symbols-rounded' style='font-size:32px; margin-right:6px;'>directions_bike</span> Ford GoBike Analytics", unsafe_allow_html=True)
    st.caption("Interactive dashboard — February 2019 trip data")

    try:
        user_types, genders, age_groups = load_filter_options()
    except Exception as error:
        st.error(
            "Couldn't load filter options from PostgreSQL. Make sure Mina's "
            "schema and Shahd's connection are set up before running this app."
        )
        st.exception(error)
        return

    raw_data = load_dashboard_data(tuple(user_types), tuple(genders), tuple(age_groups))
    
    selected_user_types, selected_genders, selected_age_groups = render_sidebar(
        user_types, genders, age_groups, len(raw_data)
    )

    try:
        data = load_dashboard_data(selected_user_types, selected_genders, selected_age_groups)
    except Exception as error:
        st.error("Couldn't load trip data for the selected filters.")
        st.exception(error)
        return

    tab_overview, tab_time, tab_users, tab_stations = st.tabs(
        ["📈 Overview KPIs", "📅 Time Analysis", "👥 User Analysis", "🗺️ Station/Trip Analysis"]
    )
    with tab_overview:
        render_overview_section(data, len(raw_data))
    with tab_time:
        render_time_section(data)
    with tab_users:
        render_user_section(data)
    with tab_stations:
        render_station_section(data)

if __name__ == "__main__":
    main()