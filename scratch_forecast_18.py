import pandas as pd
from solar_engine import forecast_rolling_intervals
from datetime import datetime

# Forecast 1: Current Real-time (14:15 -> 18:45)
df_afternoon, kpi_afternoon = forecast_rolling_intervals(
    start_time=datetime(2026, 8, 27, 14, 15),
    n_intervals=18
)

print('=== 18 CHU KY TU 14:15 (BUOI CHIEU) ===')
for idx, r in df_afternoon.iterrows():
    print(f"CK {int(r['Interval_Index']):02d} | {r['Start_Time']}-{r['End_Time']} | G={r['Irradiance_Avg_Wm2']:5.1f} W/m2 | Tcell={r['Cell_Temp_Avg_C']:4.1f}C | P_DC={r['P_DC_Avg_MW']:5.2f}MW | P_Grid={r['P_Grid_Avg_MW']:5.2f}MW | E={r['Energy_Grid_MWh']:5.3f}MWh")

print('\nKPI Afternoon Total Energy (MWh):', kpi_afternoon['total_energy_mwh'])
print('KPI Afternoon Peak Grid (MW):', kpi_afternoon['peak_grid_mw'])
