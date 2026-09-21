import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ---------------------------------------------------------------
# Two-Tone Professional Palette (Rose & Near-black / Ink)
# ---------------------------------------------------------------
COLORS = {
    "Subscriber": "#EF4676",
    "Customer": "#2A2830",
    "Male": "#EF4676",
    "Female": "#2A2830",
    "Young": "#EF4676",
    "Adult": "#2A2830",
    "Senior": "#F2A6BE",
}

BASE_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=40, r=20, t=50, b=40),
    title_x=0.5,
)


def _empty_figure(message):
    """Empty placeholder figure with a message — used when a filter
    returns zero rows, so the dashboard doesn't crash."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False, font=dict(size=14, color="gray")
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(**BASE_LAYOUT)
    return fig


# ===============================================================
# 1. KPIs (the big numbers at the top)
# ===============================================================
def get_kpis(df):
    """
    Returns a dictionary of Overview KPI numbers.
    Neamat will drop these into html.H2 or card components in the layout.
    """
    if df.empty:
        return {
            "total_trips": "0",
            "avg_duration": "0.0 mins",
            "active_bikes": "0",
            "top_station": "-",
        }

    return {
        "total_trips": f"{len(df):,}",
        "avg_duration": f"{df['duration_minute'].mean():.1f} mins",
        "active_bikes": f"{df['bike_id'].nunique():,}",
        "top_station": df["start_station_name"].mode()[0],
    }


# ===============================================================
# 2. Subscriber vs Customer (donut chart)
# ===============================================================
def fig_user_type_donut(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    counts = df["user_type"].value_counts().reset_index()
    counts.columns = ["user_type", "trips"]

    fig = px.pie(
        counts,
        names="user_type",
        values="trips",
        hole=0.55,
        color="user_type",
        color_discrete_map=COLORS,
        title="Subscriber vs Customer",
    )
    fig.update_traces(textinfo="percent", textfont_size=14)
    fig.update_layout(**BASE_LAYOUT)
    return fig


# ===============================================================
# 3. Gender distribution
# ===============================================================
def fig_gender_bar(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    counts = df["member_gender"].value_counts().reset_index()
    counts.columns = ["gender", "trips"]

    fig = px.bar(
        counts,
        x="gender",
        y="trips",
        color="gender",
        color_discrete_map=COLORS,
        title="Trips by Gender",
        text="trips",
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Trips",
                      **BASE_LAYOUT)
    return fig


# ===============================================================
# 4. Age groups
# ===============================================================
def fig_age_group_bar(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    order = ["Young", "Adult", "Senior"]
    counts = df["age_group"].value_counts().reindex(order).fillna(0).reset_index()
    counts.columns = ["age_group", "trips"]

    fig = px.bar(
        counts,
        x="age_group",
        y="trips",
        color="age_group",
        color_discrete_map=COLORS,
        category_orders={"age_group": order},
        title="Trips by Age Group",
        text="trips",
    )
    fig.update_traces(texttemplate="%{text:,}", textposition="outside")
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Trips",
                      **BASE_LAYOUT)
    return fig


# ===============================================================
# 5. Rider age distribution (histogram)
# ===============================================================
def fig_age_histogram(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    fig = px.histogram(
        df,
        x="age",
        nbins=30,
        title="Age Distribution of Riders",
        color_discrete_sequence=["#EF4676"],
    )
    fig.update_layout(xaxis_title="Age", yaxis_title="Trips", bargap=0.05,
                      **BASE_LAYOUT)
    return fig


# ===============================================================
# 6. Trip duration distribution (Converted to Smooth Area Wave Chart)
# ===============================================================
def fig_duration_histogram(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    trend_data = df.groupby([df["duration_minute"].round(0), "user_type"], as_index=False).size()
    trend_data.columns = ["duration_minute", "user_type", "trips"]

    fig = px.area(
        trend_data,
        x="duration_minute",
        y="trips",
        color="user_type",
        line_shape="spline",
        title="Trip Duration Wave Trends",
        labels={"duration_minute": "Duration (minutes)", "trips": "Trips", "user_type": "User Type"},
        color_discrete_map=COLORS,
    )
    fig.update_traces(line=dict(width=2.5), opacity=0.75)
    fig.update_layout(
        xaxis_title="Duration (minutes)", 
        yaxis_title="Trips",
        hovermode="x unified",
        **BASE_LAYOUT
    )
    return fig


# ===============================================================
# 7. Trip duration comparison: Subscriber vs Customer (box plot)
# ===============================================================
def fig_duration_by_user_type(df):
    if df.empty:
        return _empty_figure("No data for this filter")

    fig = px.box(
        df,
        x="user_type",
        y="duration_minute",
        color="user_type",
        color_discrete_map=COLORS,
        title="Trip Duration by User Type",
    )
    fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Minutes",
                      **BASE_LAYOUT)
    return fig


# ===============================================================
# Test area — does NOT run when Neamat imports this file
# ===============================================================
if __name__ == "__main__":
    df = pd.read_csv("cleaned_fordgobike.csv")

    print("Rows:", len(df))
    print("KPIs:", get_kpis(df))

    fig_user_type_donut(df).show()