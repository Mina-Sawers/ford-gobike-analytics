import pandas as pd
from sqlalchemy import create_engine
import streamlit as st
import plotly.express as px
from app import load_dashboard_data


'''

#DB connection
DB_URL = "postgresql+psycopg2://postgres:123@localhost:5432/ford_gobike"

engine = create_engine(DB_URL)

#with engine.connect() as conn:
#    print("Connected successfully")
#------------------------------------
#Reading tables
dim_station = pd.read_sql(
    "SELECT * FROM dim_station",
    engine
)

fact_trips = pd.read_sql(
    "SELECT * FROM fact_trips",
    engine
)

print(dim_station.head())

start_df = fact_trips.merge(
    dim_station,
    left_on="start_station_id",
    right_on="station_id"
)

top_start = (
    fact_trips
    .groupby("start_station_id")
    .size()
    .reset_index(name="trip_count")
)
'''