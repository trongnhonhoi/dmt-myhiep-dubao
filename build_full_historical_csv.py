"""
Script to build historical_meter_daily_energy.csv from parts
"""
import pandas as pd
from data_part_2020_2021 import get_2020_2021_records
from data_part_2022_2023 import get_2022_2023_records
from data_part_2024_2026 import get_2024_2026_records

def build_csv():
    r1 = get_2020_2021_records()
    r2 = get_2022_2023_records()
    r3 = get_2024_2026_records()
    
    all_records = r1 + r2 + r3
    df = pd.DataFrame(all_records)
    
    # Sort and remove duplicates if any
    df['date_dt'] = pd.to_datetime(df['Date'])
    df = df.sort_values('date_dt').drop_duplicates(subset=['Date']).reset_index(drop=True)
    df = df.drop(columns=['date_dt'])
    
    output_path = 'historical_meter_daily_energy.csv'
    df.to_csv(output_path, index=False)
    print(f"Successfully generated {output_path} with {len(df)} daily records.")
    print(f"Date range: {df['Date'].iloc[0]} to {df['Date'].iloc[-1]}")
    print(df.info())
    print("\nSample Monthly Averages (Primary MWh/day):")
    df['Month'] = pd.to_datetime(df['Date']).dt.month
    print(df.groupby('Month')['Primary_Energy_MWh'].agg(['count', 'mean', 'std', 'min', 'max']))

if __name__ == '__main__':
    build_csv()
