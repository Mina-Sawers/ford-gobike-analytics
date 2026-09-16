-- 1. Create the ENUM Categories
CREATE TYPE gender_category AS ENUM ('Male', 'Female');
CREATE TYPE age_category AS ENUM ('Young', 'Adult', 'Senior');
CREATE TYPE user_category AS ENUM ('Subscriber', 'Customer');

-- 2. Create Dimension Tables
CREATE TABLE dim_user(
    user_id SERIAL PRIMARY KEY, 
    age INT,
    age_group age_category,
    gender gender_category,
    user_type user_category
);

CREATE TABLE dim_station(
    station_id INT PRIMARY KEY,
    station_name VARCHAR(255), 
    latitude FLOAT,
    longitude FLOAT
);

-- 3. Create the Fact Table 
CREATE TABLE fact_trips(
    trip_id SERIAL PRIMARY KEY, 
    duration_sec INT,
    duration_minute FLOAT,
    bike_id INT,
    start_station_id INT REFERENCES dim_station(station_id),
    end_station_id INT REFERENCES dim_station(station_id),
    user_id INT REFERENCES dim_user(user_id)
);



-- ==========================================
-- SAMPLE DATA INSERTION (5 TEST ROWS)
-- ==========================================

-- 1. Insert into dim_station (Start and End stations combined)
INSERT INTO dim_station (station_id, station_name, latitude, longitude)
VALUES 
    (300, 'Palm St at Willow St', 37.3172979, -121.884995),
    (312, 'San Jose Diridon Station', 37.329732, -121.901782),
    (19, 'Post St at Kearny St', 37.788975, -122.403452),
    (121, 'Mission Playground', 37.7592103, -122.4213392),
    (370, 'Jones St at Post St', 37.78732677, -122.4132782),
    (43, 'San Francisco Public Library (Grove St at Hyde St)', 37.7787677, -122.4159292),
    (44, 'Civic Center/UN Plaza BART Station (Market St at McAllister St)', 37.7810737, -122.4117382),
    (343, 'Bryant St at 2nd St', 37.78317199, -122.393572),
    (127, 'Valencia St at 21st St', 37.7567083, -122.421025),
    (323, 'Broadway at Kearny', 37.79801364, -122.4059504);

-- 2. Insert into dim_user 
-- (Notice we skip user_id because SERIAL generates it automatically as 1, 2, 3, 4, 5)
INSERT INTO dim_user (age, age_group, gender, user_type)
VALUES 
    (36, 'Adult', 'Female', 'Subscriber'),
    (27, 'Young', 'Male', 'Subscriber'),
    (23, 'Young', 'Female', 'Subscriber'),
    (26, 'Young', 'Male', 'Subscriber'),
    (29, 'Young', 'Male', 'Customer');

-- 3. Insert into fact_trips
-- (Notice we use user_id 1 through 5, matching the users we just created above)
INSERT INTO fact_trips (duration_sec, duration_minute, bike_id, start_station_id, end_station_id, user_id)
VALUES 
    (1147, 19.12, 3803, 300, 312, 1),
    (1049, 17.48, 6488, 19, 121, 2),
    (458, 7.63, 5318, 370, 43, 3),
    (506, 8.43, 5848, 44, 343, 4),
    (1176, 19.60, 5328, 127, 323, 5);