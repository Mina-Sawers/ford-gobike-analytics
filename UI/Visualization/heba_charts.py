import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Two-Tone Balanced Professional Palette (Calm Mid-Teal Tones)
COLORS = ["#0f766e", "#14b8a6"]

BASE_LAYOUT = dict(
    template="plotly_white",
    margin=dict(l=40, r=20, t=50, b=40),
    title_x=0.5,
)

def _empty_figure(message):
    """Placeholder figure when data is empty to prevent crashes."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, showarrow=False, font=dict(size=14, color="gray")
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(**BASE_LAYOUT)
    return fig


def render_station_charts(df):
    """
    Station and Spatial charts for Heba's section.
    """
    if df.empty:
        return [_empty_figure("No data for station analysis")]

    top_start = (
        df.groupby("start_station", as_index=False)
        .size()
        .rename(columns={"size": "trip_count"})
        .nlargest(10, "trip_count")
        .sort_values("trip_count", ascending=True)
    )
    
    fig_stations = px.bar(
        top_start,
        x="trip_count",
        y="start_station",
        orientation="h",
        title="Top 10 Start Stations",
        labels={"trip_count": "Trips", "start_station": ""},
        color="trip_count",
        color_discrete_sequence=COLORS 
    )
    fig_stations.update_layout(showlegend=False, **BASE_LAYOUT)

    return [fig_stations]