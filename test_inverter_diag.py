import sys
sys.stdout.reconfigure(encoding='utf-8')
import inverter_diagnostic_engine as ide
from data_harvester import DataHarvester, DEFAULT_SERVER_PATH

harvester = DataHarvester(DEFAULT_SERVER_PATH)
mgr = ide.InverterAnomalyManager(harvester)
res = mgr.analyze_timeframe('D-1')
df = res['inverter_table']
faults = df[df['Health_Status'] != 'NORMAL']

print(f"=== TỔNG HỢP {len(faults)} INVERTER BẤT THƯỜNG NGÀY D-1 (04/09/2026) ===")
for _, r in faults.iterrows():
    print(f"• {r['Inverter_ID']} ({r['Station']}): [{r['Health_Status']}] Sản lượng: {r['Energy_kWh']} kWh ({r['Ratio_Station_Pct']}% TB trạm) | Tổn thất: ~{r['Est_Loss_kWh']} kWh | {r['Anomaly_Type']}")
