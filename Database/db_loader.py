import os
import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DB_USER = "postgres"
DB_PASS = "123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "ford_gobike"

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL)

def run_ddl_setup(sql_file_path: str):
    """Executes schema DDL statements."""
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"Setup SQL file not found at: {sql_file_path}")

    with engine.connect() as conn:
        schema_ready = conn.execute(text("""
            SELECT
                (SELECT COUNT(*) FROM information_schema.tables
                 WHERE table_schema = 'public'
                   AND table_name IN ('dim_user', 'dim_station', 'fact_trips')) = 3
                AND
                (SELECT COUNT(*) FROM pg_type
                 WHERE typnamespace = 'public'::regnamespace
                   AND typname IN ('gender_category', 'age_category', 'user_category')) = 3
        """)).scalar_one()
    if schema_ready:
        print("Database schema already exists; skipping DDL setup.")
        return
    
    with open(sql_file_path, "r", encoding="utf-8") as f:
        ddl_script = f.read()

    statements = ddl_script.split("-- ==========================================")[0]
    with engine.begin() as conn:
        conn.execute(text(statements))
    print("Database schema verified/initialized.")

def categorize_age(age):
    if pd.isna(age):
        return None
    if age < 30:
        return "Young"
    elif age < 55:
        return "Adult"
    return "Senior"

def populate_database_from_csv(csv_path: str):
    with engine.connect() as conn:
        existing_trips = conn.execute(text("SELECT COUNT(*) FROM fact_trips")).scalar_one()
    if existing_trips:
        print(f"Database already contains {existing_trips:,} trips; skipping duplicate import.")
        return

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset not found at: {csv_path}")

    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)

    # 1. Clean missing core keys using the actual cleaned columns
    df = df.dropna(subset=["start_station_id", "end_station_id", "age", "age_group", "member_gender"]).copy()
    
    # 2. Filter standard categories
    df["age"] = df["age"].astype(int)
    df = df[df["member_gender"].isin(["Male", "Female"])]
    df = df[df["user_type"].isin(["Subscriber", "Customer"])]

    # 3. Build dim_station
    starts = df[["start_station_id", "start_station_name", "start_station_latitude", "start_station_longitude"]].rename(
        columns={
            "start_station_id": "station_id",
            "start_station_name": "station_name",
            "start_station_latitude": "latitude",
            "start_station_longitude": "longitude",
        }
    )
    ends = df[["end_station_id", "end_station_name", "end_station_latitude", "end_station_longitude"]].rename(
        columns={
            "end_station_id": "station_id",
            "end_station_name": "station_name",
            "end_station_latitude": "latitude",
            "end_station_longitude": "longitude",
        }
    )
    dim_station = pd.concat([starts, ends]).drop_duplicates(subset=["station_id"]).dropna()
    dim_station["station_id"] = dim_station["station_id"].astype(int)

    # 4. Build dim_user
    dim_user = df[["age", "age_group", "member_gender", "user_type"]].drop_duplicates().rename(
        columns={"member_gender": "gender"}
    ).reset_index(drop=True)
    dim_user["user_id"] = dim_user.index + 1

    df = df.merge(
        dim_user,
        left_on=["age", "age_group", "member_gender", "user_type"],
        right_on=["age", "age_group", "gender", "user_type"],
        how="inner"
    )

    # 5. Build fact_trips
    fact_trips = df[[
        "duration_sec", "duration_minute", "bike_id",
        "start_station_id", "end_station_id", "user_id"
    ]].copy()
    fact_trips["start_station_id"] = fact_trips["start_station_id"].astype(int)
    fact_trips["end_station_id"] = fact_trips["end_station_id"].astype(int)

    # 6. Bulk Insert
    print("Writing records to PostgreSQL...")
    with engine.begin() as conn:
        dim_station.to_sql("dim_station", conn, if_exists="append", index=False)
        dim_user.to_sql("dim_user", conn, if_exists="append", index=False)
        fact_trips.to_sql("fact_trips", conn, if_exists="append", index=False)

    print("Data loading completed successfully.")

if __name__ == "__main__":
    sql_path = os.path.join(PROJECT_DIR, "Database", "database_setup.sql")
    csv_path = os.path.join(PROJECT_DIR, "Data_Cleaning", "cleaned_fordgobike.csv")

    run_ddl_setup(sql_path)
    populate_database_from_csv(csv_path)