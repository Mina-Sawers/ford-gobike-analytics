import pandas as pd
import numpy as np

def load_data(filepath):
    """
    Loads the raw dataset from a CSV file.
    """
    print(f"Loading raw dataset from {filepath}...")
    return pd.read_csv(filepath)

def clean_missing_and_duplicates(df):
    """
    Removes duplicate rows and drops nulls from critical demographic and station columns.
    """
    print("Cleaning nulls and duplicates...")
    df.drop_duplicates(inplace=True)
    
    critical_cols = ['member_gender', 'member_birth_year', 'start_station_name', 'end_station_name']
    df.dropna(subset=critical_cols, inplace=True)

    df = df[df['member_gender']!='Other']

    return df

def filter_iqr(df, column_name):
    """
    Filters out extreme outliers from a specified column using the IQR method.
    """
    print(f"Applying IQR filter to remove outliers in '{column_name}'...")
    Q1 = df[column_name].quantile(0.25)
    Q3 = df[column_name].quantile(0.75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    return df[(df[column_name] >= lower_bound) & (df[column_name] <= upper_bound)]

def engineer_age(df, current_year=2019):
    """
    Calculates age, removes age outliers via IQR, creates age groups, and drops the birth year column.
    """
    print("Engineering age and filtering age outliers...")
    df['age'] = current_year - df['member_birth_year']
    
    # Filter age outliers mathematically using IQR
    df = filter_iqr(df, 'age')
    
    # Create Age Groups
    df['age_group'] = pd.cut(df['age'], bins=[0, 29, 50, 150], labels=['Young', 'Adult', 'Senior'])
    
    # Drop the original birth year column
    df.drop(columns=['member_birth_year'], inplace=True)
    return df

def engineer_duration(df):
    """
    Converts duration to minutes, removes outliers via IQR, and drops the seconds column.
    """
    print("Engineering duration and filtering duration outliers...")
    df['duration_minute'] = df['duration_sec'] / 60.0
    df['duration_minute'] = df['duration_minute'].round(2)
    
    # Drop the original seconds column
    # df.drop(columns=['duration_sec'], inplace=True)
    
    # Filter duration outliers mathematically using IQR
    df = filter_iqr(df, 'duration_minute')
    
    return df

def final_cleanup(df):
    # I noticed the time is 12 AM for all rows, so I think the best solution is to drop these columns
    print("Dropping corrupted time columns to adjust to the new ERD...")
    cols_to_drop = ['start_time', 'end_time']
    df.drop(columns=cols_to_drop, inplace=True)
    return df



def main():
    """
    Main orchestration function to run the preprocessing pipeline and export the clean dataset.
    """
    # 1. Load Data
    raw_file = 'fordgobike-tripdataFor201902.csv'
    df = load_data(raw_file)
    
    # 2. Execute Preprocessing Steps
    df = clean_missing_and_duplicates(df)
    df = engineer_age(df)
    df = engineer_duration(df)
    df = final_cleanup(df)
    
    # Final Data Quality Check ---
    print("\n--- Final Data Quality Check ---")
    print(f"Total remaining duplicates: {df.duplicated().sum()}")
    print("Total remaining nulls per column:")
    print(df.isnull().sum())
    print("--------------------------------\n")
    print(df.info())
    print("--------------------------------\n")
    print(df.describe())
    
    # 3. Export Clean Data
    output_file = 'cleaned_fordgobike.csv'
    df.to_csv(output_file, index=False)
    print(f"Success! Cleaned dataset saved to {output_file} with {df.shape[0]} rows.")

# Call the main function to run the script
if __name__ == "__main__":
    main()