"""
Script to create complete historical_meter_daily_energy.csv for My Hiep Solar Plant (2020-12-01 to 2026-07-31)
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime

OUT_CSV = os.path.join(os.path.dirname(__file__), "historical_meter_daily_energy.csv")

def parse_block(text_block):
    records = []
    for line in text_block.strip().split('\n'):
        line = line.strip()
        if not line or 'Ngày' in line or 'MH_171' in line:
            continue
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        if len(parts) < 2:
            parts = [p.strip() for p in line.split() if p.strip()]
        if len(parts) >= 5:
            date_str = parts[0]
            val_171c = parts[1]
            val_dp1 = parts[2]
            val_dp2 = parts[3]
            val_431 = parts[4]
            
            try:
                dt = datetime.strptime(date_str, "%d-%b-%y")
                d_fmt = dt.strftime("%Y-%m-%d")
                
                def parse_val(v):
                    if v == "-" or v == "" or v == "NaN":
                        return np.nan
                    try:
                        return float(v.replace(",", ""))
                    except:
                        return np.nan

                c_val = parse_val(val_171c)
                dp1_val = parse_val(val_dp1)
                dp2_val = parse_val(val_dp2)
                m431_val = parse_val(val_431)
                
                candidates = [v for v in [c_val, dp1_val, dp2_val] if not np.isnan(v)]
                primary_mwh = c_val if not np.isnan(c_val) else (np.mean(candidates) if candidates else np.nan)
                
                records.append({
                    "Date": d_fmt,
                    "Year": dt.year,
                    "Month": dt.month,
                    "Day": dt.day,
                    "DayOfWeek": dt.strftime("%A"),
                    "MH_171C_MWh": c_val,
                    "MH_171DP1_MWh": dp1_val,
                    "MH_171DP2_MWh": dp2_val,
                    "MH_431_MWh": m431_val,
                    "Primary_Energy_MWh": primary_mwh,
                    "Specific_Yield_Psh": round(primary_mwh / 50.0, 3) if not np.isnan(primary_mwh) else np.nan
                })
            except Exception as e:
                continue
    return records
