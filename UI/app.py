import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Ford GoBike Analytics", page_icon=":bike:", layout="wide")


@st.cache_resource
def get_connection():
	return st.connection("postgresql", type="sql")


@st.cache_data(ttl=600)
def load_filter_options():
	connection = get_connection()
	user_types = connection.query(
		"SELECT DISTINCT user_type::text AS value FROM dim_user ORDER BY value",
		ttl=600,
	)["value"].tolist()
	age_groups = connection.query(
		"SELECT DISTINCT age_group::text AS value FROM dim_user ORDER BY value",
		ttl=600,
	)["value"].tolist()
	return user_types, age_groups


def build_filter_clause(user_types, age_groups):
	clauses = []
	params = {}

	if user_types:
		names = []
		for index, value in enumerate(user_types):
			name = f"user_type_{index}"
			names.append(f":{name}")
			params[name] = value
		clauses.append(f"u.user_type::text IN ({', '.join(names)})")

	if age_groups:
		names = []
		for index, value in enumerate(age_groups):
			name = f"age_group_{index}"
			names.append(f":{name}")
			params[name] = value
		clauses.append(f"u.age_group::text IN ({', '.join(names)})")

	where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
	return where, params


@st.cache_data(ttl=300)
def load_dashboard_data(user_types=(), age_groups=()):
	where, params = build_filter_clause(user_types, age_groups)
	query = f"""
		SELECT
			t.trip_id,
			t.duration_minute,
			t.bike_id,
			s.station_name AS start_station,
			s.latitude,
			s.longitude,
			u.gender::text AS gender,
			u.age_group::text AS age_group,
			u.user_type::text AS user_type
		FROM fact_trips AS t
		JOIN dim_station AS s ON s.station_id = t.start_station_id
		JOIN dim_user AS u ON u.user_id = t.user_id
		{where}
	"""
	return get_connection().query(query, params=params, ttl=300)


def render_sidebar(user_types, age_groups):
	with st.sidebar:
		st.header("Filters")
		selected_user_types = st.multiselect("User type", user_types, default=user_types)
		selected_age_groups = st.multiselect("Age group", age_groups, default=age_groups)
	return tuple(selected_user_types), tuple(selected_age_groups)


def render_kpis(data):
	total_trips = len(data)
	average_duration = data["duration_minute"].mean() if total_trips else 0
	distinct_bikes = data["bike_id"].nunique() if total_trips else 0
	first, second, third = st.columns(3)
	first.metric("Total trips", f"{total_trips:,}")
	second.metric("Average duration", f"{average_duration:.1f} min")
	third.metric("Distinct bikes", f"{distinct_bikes:,}")


def render_charts(data):
	if data.empty:
		st.info("No trips match the selected filters.")
		return

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
		color_continuous_scale="Teal",
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
		color_discrete_sequence=["#0f766e", "#f59e0b"],
	)
	demographic_chart.update_layout(height=430)

	left, right = st.columns(2)
	left.plotly_chart(station_chart, use_container_width=True)
	right.plotly_chart(demographic_chart, use_container_width=True)

	map_data = (
		data.groupby(["start_station", "latitude", "longitude"], as_index=False)
		.size()
		.rename(columns={"size": "trip_count"})
	)
	st.subheader("Start station activity")
	st.map(map_data, latitude="latitude", longitude="longitude", size="trip_count", zoom=11)


def main():
	st.title("Ford GoBike Analytics")
	st.caption("Trip activity across the selected rider segments")
	try:
		user_types, age_groups = load_filter_options()
		selected_user_types, selected_age_groups = render_sidebar(user_types, age_groups)
		data = load_dashboard_data(selected_user_types, selected_age_groups)
	except Exception as error:
		st.error("Unable to load dashboard data. Check the PostgreSQL connection settings.")
		st.exception(error)
		return

	render_kpis(data)
	st.divider()
	render_charts(data)


if __name__ == "__main__":
	main()
