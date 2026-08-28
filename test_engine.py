"""
Kiểm thử tự động các thuật toán và bộ parser SCADA TXT ĐMT Mỹ Hiệp
"""

import unittest
import pandas as pd
import numpy as np
from solar_engine import (
    MyHiepSolarPlantConfig,
    calculate_cell_temperature,
    calculate_solar_output,
    detect_and_parse_input_data,
    parse_scada_weather_txt_advanced,
    process_1min_to_15min_forecast,
    generate_synthetic_1min_data,
    generate_scada_txt_sample_content
)
from exporter import prepare_export_dataframe, export_to_excel_bytes, export_to_csv_bytes


class TestSolarForecastingEngine(unittest.TestCase):

    def test_plant_specs(self):
        """Kiểm tra cấu hình nhà máy ĐMT Mỹ Hiệp"""
        self.assertEqual(MyHiepSolarPlantConfig.DC_CAPACITY_MWP, 50.0)
        self.assertEqual(MyHiepSolarPlantConfig.AC_CAPACITY_MW, 40.075)
        self.assertAlmostEqual(MyHiepSolarPlantConfig.TEMP_COEFF_PMP, -0.00347, places=5)
        self.assertEqual(MyHiepSolarPlantConfig.NOCT_C, 45.0)

    def test_user_scada_txt_parsing(self):
        """Kiểm tra chính xác định dạng TXT của người dùng cung cấp"""
        raw_user_snippet = """WEATHER STATION;PLANT;;;;STATION-02-;WEATHER STAT;ION;;;;;;;STATION-06-;WEATHER STAT;ION;;;;
Parameter;PERFORMANCE;WIND DIRECTION;WIND SPEED;GHI-01 IRRADIANCE;GHI-02 IRRADIANCE;AIR PRESSURE;AIR TEMPERATURE;HUMIDITY;RAIN;PV TEMPERATURE;WIND DIRECTION;WIND SPEED;GHI-01 IRRADIANCE;GHI-02 IRRADIANCE;AIR PRESSURE;AIR TEMPERATURE;HUMIDITY;RAIN;PV TEMPERATURE;
;(%);(deg);(m/s);(W/m2);(W/m2);(mBar);(oC);(%);(mm);(oC);(deg);(m/s);(W/m2);(W/m2);(mBar);(oC);(%);(mm);(oC);
26/08/26 00:00;0.000;0.000;6.950;0.037;-0.021;1076.410;30.575;70.324;0.000;0.000;263.528;3.950;0.058;0.094;1076.410;30.508;70.188;0.000;25.550;
26/08/26 00:01;0.000;0.000;4.700;0.159;0.171;1076.530;30.559;70.193;0.000;0.000;285.156;2.450;0.172;0.228;1076.530;30.508;70.261;0.000;25.879;
26/08/26 
"""
        df_parsed, meta = detect_and_parse_input_data(raw_user_snippet)
        self.assertEqual(len(df_parsed), 2)
        self.assertIn('Timestamp', df_parsed.columns)
        self.assertIn('Irradiance', df_parsed.columns)
        self.assertIn('Temperature', df_parsed.columns)
        self.assertIn('PV_Temperature', df_parsed.columns)
        
        # Kiểm tra timestamp
        self.assertEqual(df_parsed['Timestamp'].iloc[0], pd.Timestamp('2026-08-26 00:00:00'))
        self.assertEqual(df_parsed['Timestamp'].iloc[1], pd.Timestamp('2026-08-26 00:01:00'))
        
        # Kiểm tra trung bình 4 cảm biến GHI
        self.assertGreaterEqual(df_parsed['Irradiance'].iloc[0], 0.0)
        self.assertGreater(df_parsed['PV_Temperature'].iloc[0], 0.0)

    def test_full_scada_sample_generation_and_process(self):
        """Kiểm tra xử lý trọn vẹn 1440 phút dạng TXT SCADA thành 96 chu kỳ 15 phút"""
        txt_content = generate_scada_txt_sample_content()
        df_parsed, meta = detect_and_parse_input_data(txt_content)
        
        self.assertEqual(len(df_parsed), 1440)
        
        df_1min, df_15min, kpi = process_1min_to_15min_forecast(df_parsed)
        self.assertEqual(len(df_15min), 96)
        self.assertGreater(kpi['total_energy_mwh'], 0.0)
        self.assertLessEqual(kpi['peak_grid_mw'], 40.075)

    def test_inverter_clipping(self):
        """Kiểm tra thuật toán cắt công suất Inverter ở ngưỡng 40.075 MW"""
        irr = pd.Series([1150.0])
        cell_temp = pd.Series([30.0])
        
        out = calculate_solar_output(
            irradiance_wm2=irr,
            cell_temp_c=cell_temp,
            dc_capacity_mwp=50.0,
            ac_capacity_mw=40.075,
            soiling_loss=0.0,
            dc_cable_loss=0.0,
            mismatch_loss=0.0,
            inverter_eff=0.99
        )
        
        self.assertGreater(out['p_ac_raw_mw'].iloc[0], 40.075)
        self.assertAlmostEqual(out['p_ac_inv_mw'].iloc[0], 40.075, places=3)
        self.assertGreater(out['clipping_loss_mw'].iloc[0], 0.0)


if __name__ == '__main__':
    unittest.main()
