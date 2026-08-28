r"""
Module Dự Báo Thông Minh Tích Hợp Khí Tượng Thời Tiết Xã Mỹ Hiệp / Phù Mỹ, Bình Định
và Bộ Tạo Thuyết Minh Vận Hành - Khí Tượng - Sản Lượng (Chuẩn Điều Độ EVN / A0 / A3)
"""

import json
import urllib.request
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List

from solar_engine import MyHiepSolarPlantConfig

# Tọa độ địa lý Nhà máy ĐMT Mỹ Hiệp (Phù Mỹ, Bình Định)
PLANT_LATITUDE = 14.165
PLANT_LONGITUDE = 109.030
PLANT_LOCATION_NAME = "Thôn Vạn Phước, Xã Phù Mỹ Nam, Tỉnh Gia Lai (SĐT: 0256 3856 667)"


def fetch_phu_my_weather_forecast(days: int = 7) -> Optional[Dict[str, Any]]:
    """
    Lấy dữ liệu dự báo thời tiết khí tượng số (NWP / ECMWF / GFS) 
    tại tọa độ Phù Mỹ, Bình Định từ Open-Meteo API
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={PLANT_LATITUDE}&longitude={PLANT_LONGITUDE}&"
        f"hourly=temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,"
        f"cloud_cover,cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
        f"shortwave_radiation,direct_normal_irradiance,diffuse_radiation,wind_speed_10m&"
        f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
        f"precipitation_probability_max,shortwave_radiation_sum,wind_speed_10m_max&"
        f"timezone=Asia%2FBangkok&forecast_days={days}"
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'MyHiepSolarForecasting/1.0'})
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Lỗi kết nối API thời tiết: {e}")
        return None


def convert_nwp_to_15min_dispatch(nwp_data: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Tuple[pd.DataFrame, pd.DataFrame, List[Dict[str, Any]]]:
    """
    Chuyển đổi dữ liệu thời tiết dự báo từng giờ thành 96 chu kỳ 15 phút mỗi ngày,
    tính toán sản lượng điện quang điện dựa trên đặc tính tấm pin Sharp NU-440 và quy tắc 1000W/m2 -> 40MW.
    """
    if params is None:
        params = {}
        
    hourly = nwp_data.get('hourly', {})
    if not hourly or 'time' not in hourly:
        return pd.DataFrame(), pd.DataFrame(), []

    df_h = pd.DataFrame(hourly)
    df_h['time'] = pd.to_datetime(df_h['time'])
    df_h.set_index('time', inplace=True)

    # Nội suy Spline bậc 3 sang chu kỳ 15 phút
    df_15m = df_h.resample('15min').interpolate(method='time')
    # Xử lý radiation: không âm
    df_15m['shortwave_radiation'] = df_15m['shortwave_radiation'].clip(lower=0.0)
    df_15m['cloud_cover'] = df_15m['cloud_cover'].clip(lower=0.0, upper=100.0)
    df_15m['precipitation_probability'] = df_15m['precipitation_probability'].clip(lower=0.0, upper=100.0)

    rows = []
    daily_summaries = []
    narratives = []

    # Nhóm theo từng ngày
    for date_val, group in df_15m.groupby(df_15m.index.date):
        d_str = date_val.strftime('%d/%m/%Y')
        day_name = date_val.strftime('%A')
        day_vn_name = f"Ngày {date_val.strftime('%d/%m')} ({'T' + str(date_val.weekday() + 2) if date_val.weekday() < 6 else 'CN'})"

        daily_e_mwh = 0.0
        daily_p_max = 0.0
        daily_irr_max = 0.0
        daily_clip_mwh = 0.0
        daily_temp_max = group['temperature_2m'].max()
        daily_temp_min = group['temperature_2m'].min()
        daily_cloud_avg = group['cloud_cover'].mean()
        daily_rain_prob_max = group['precipitation_probability'].max()
        daily_rain_sum = group['precipitation'].sum()

        interval_idx = 1
        for ts, r in group.iterrows():
            if interval_idx > 96:
                break

            start_t = ts
            end_t = ts + timedelta(minutes=15)
            irr = float(r['shortwave_radiation'])
            amb_temp = float(r['temperature_2m'])
            wind = float(r.get('wind_speed_10m', 2.5))
            cloud = float(r.get('cloud_cover', 20.0))
            rain_prob = float(r.get('precipitation_probability', 0.0))

            # Nhiệt độ cell tấm pin Sharp NU-440 (NOCT 45°C)
            if irr > 10.0:
                cell_temp = amb_temp + ((45.0 - 20.0) / 800.0) * irr * max(0.6, 1.0 - 0.03 * (wind - 1.0))
            else:
                cell_temp = amb_temp

            # Hệ số suy giảm nhiệt độ (-0.347%/°C)
            f_temp = max(0.70, min(1.05, 1.0 - 0.00347 * (cell_temp - 25.0)))

            # Quy tắc hiệu chuẩn Mỹ Hiệp: 1000 W/m2 -> 40.0 MW
            p_grid_raw = (irr / 1000.0) * 40.0 * f_temp
            p_grid = min(40.075, p_grid_raw)
            clipping_mw = max(0.0, p_grid_raw - 40.075)

            p_dc = (irr / 1000.0) * 50.0 * f_temp * 0.95
            e_mwh = p_grid * 0.25
            clip_mwh = clipping_mw * 0.25

            daily_energy_sum_val = e_mwh
            daily_e_mwh += e_mwh
            daily_clip_mwh += clip_mwh
            daily_p_max = max(daily_p_max, p_grid)
            daily_irr_max = max(daily_irr_max, irr)

            rows.append({
                'Date': d_str,
                'Interval_Index': interval_idx,
                'Start_Time': start_t.strftime('%H:%M'),
                'End_Time': end_t.strftime('%H:%M'),
                'Timestamp': start_t,
                'End_Timestamp': end_t,
                'Irradiance_Avg_Wm2': round(irr, 1),
                'Irradiance_Max_Wm2': round(irr * 1.05, 1),
                'Amb_Temp_Avg_C': round(amb_temp, 1),
                'Cell_Temp_Avg_C': round(cell_temp, 1),
                'Cloud_Cover_Pct': round(cloud, 1),
                'Rain_Probability_Pct': round(rain_prob, 1),
                'P_DC_Avg_MW': round(p_dc, 3),
                'P_AC_Raw_Avg_MW': round(p_grid_raw, 3),
                'P_AC_Inv_Avg_MW': round(p_grid, 3),
                'P_Grid_Avg_MW': round(p_grid, 3),
                'Energy_Grid_MWh': round(e_mwh, 4),
                'Clipping_Loss_Avg_MW': round(clipping_mw, 3),
                'Clipping_Loss_MWh': round(clip_mwh, 4)
            })
            interval_idx += 1

        daily_summaries.append({
            'Date': date_val,
            'Date_Str': d_str,
            'Day_Name': day_vn_name,
            'Energy_MWh': round(daily_e_mwh, 3),
            'Peak_Grid_MW': round(daily_p_max, 3),
            'Max_Irradiance_Wm2': round(daily_irr_max, 1),
            'Max_Temp_C': round(daily_temp_max, 1),
            'Min_Temp_C': round(daily_temp_min, 1),
            'Avg_Cloud_Pct': round(daily_cloud_avg, 1),
            'Max_Rain_Prob_Pct': round(daily_rain_prob_max, 1),
            'Rain_Sum_mm': round(daily_rain_sum, 1),
            'Clipping_Loss_MWh': round(daily_clip_mwh, 3),
            'Specific_Yield_kWh_kWp': round(daily_e_mwh * 1000.0 / 50000.0, 2)
        })

        # Tạo thuyết minh chuyên sâu cho từng ngày
        narratives.append(generate_daily_operational_narrative({
            'date_str': d_str,
            'day_name': day_vn_name,
            'energy_mwh': daily_e_mwh,
            'peak_p_mw': daily_p_max,
            'peak_irr': daily_irr_max,
            'temp_max': daily_temp_max,
            'temp_min': daily_temp_min,
            'cloud_avg': daily_cloud_avg,
            'rain_prob': daily_rain_prob_max,
            'rain_sum': daily_rain_sum,
            'clipping_mwh': daily_clip_mwh
        }))

    return pd.DataFrame(rows), pd.DataFrame(daily_summaries), narratives


def generate_daily_operational_narrative(day_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tạo bản thuyết minh vận hành khí tượng & sản lượng cho từng ngày
    phục vụ báo cáo điều độ nội bộ và đăng ký biểu đồ phụ tải phát điện EVN
    """
    d_str = day_data['date_str']
    day_name = day_data['day_name']
    e_mwh = day_data['energy_mwh']
    p_max = day_data['peak_p_mw']
    irr_max = day_data['peak_irr']
    t_max = day_data['temp_max']
    t_min = day_data['temp_min']
    cloud = day_data['cloud_avg']
    rain_prob = day_data['rain_prob']
    rain_mm = day_data['rain_sum']

    # 1. Đánh giá hình thế thời tiết
    if cloud < 25 and rain_prob < 30:
        weather_type = "Nắng tốt, trời quang mây (Clear Sky)"
        weather_desc = (
            f"Khu vực xã Mỹ Hiệp (Phù Mỹ) chịu ảnh hưởng của trường gió Tây Nam hoạt động ổn định, "
            f"độ che phủ mây thấp ({cloud:.1f}%), trời nắng mạnh từ sớm (khoảng 06:15) đến chiều muộn (17:45). "
            f"Bức xạ cực đại giữa trưa đạt mức cao ~{irr_max:.0f} W/m²."
        )
        impact_desc = (
            f"Điều kiện quang hóa rất lý tưởng. Sản lượng phát lưới ước đạt <b>{e_mwh:.2f} MWh</b>. "
            f"Công suất đỉnh P_Grid có thể chạm mức <b>{p_max:.2f} MW</b> vào khung giờ 11:30 - 12:45."
        )
    elif cloud < 55 and rain_prob < 50:
        weather_type = "Mây thay đổi, ngày nắng gián đoạn (Partly Cloudy)"
        weather_desc = (
            f"Khu vực Phù Mỹ có mây đối lưu nhiệt phát triển vào buổi chiều, độ che phủ mây trung bình {cloud:.1f}%. "
            f"Nắng tốt vào buổi sáng từ 07:00 đến 11:30, sau đó xuất hiện dải mây tầng trung làm dao động nhẹ bức xạ. "
            f"Xác suất mưa thấp ({rain_prob:.0f}%), lượng mưa dự báo {rain_mm:.1f} mm."
        )
        impact_desc = (
            f"Sản lượng đạt mức khá <b>{e_mwh:.2f} MWh</b>. Công suất đỉnh đạt khoảng <b>{p_max:.2f} MW</b>. "
            f"Có hiện tượng dao động công suất nhẹ trong khoảng 13:00 - 15:00 do các cụm mây trôi qua dàn pin."
        )
    else:
        weather_type = "Nhiều mây, có mưa rào & dông rải rác (Cloudy / Rainy)"
        weather_desc = (
            f"Hình thế rãnh áp thấp kết hợp gió mùa mang ẩm, độ che phủ mây cao ({cloud:.1f}%), "
            f"khả năng xuất hiện mưa rào và dông vào chiều tối (xác suất mưa {rain_prob:.0f}%, lượng mưa ~{rain_mm:.1f} mm). "
            f"Bức xạ mặt trời bị tán xạ mạnh, đỉnh bức xạ chỉ đạt khoảng {irr_max:.0f} W/m²."
        )
        impact_desc = (
            f"Sản lượng suy giảm đáng kể, ước đạt <b>{e_mwh:.2f} MWh</b> (suy giảm ~{(1 - e_mwh/170.0)*100:.1f}% so với ngày nắng chuẩn). "
            f"Công suất phát đỉnh chỉ đạt <b>{p_max:.2f} MW</b>."
        )

    # 2. Phân tích ảnh hưởng nhiệt độ tấm pin Sharp NU-440
    if t_max >= 36.0:
        thermal_analysis = (
            f"Nhiệt độ môi trường cực đại dự báo lên tới <b>{t_max:.1f}°C</b> vào giữa trưa. "
            f"Dưới bức xạ mạnh, nhiệt độ cell tấm pin Sharp NU-440 có thể tăng vọt lên <b>55°C - 62°C</b> "
            f"(cao hơn STC 25°C từ 30°C - 37°C). Với hệ số nhiệt độ γ = -0.347%/°C, "
            f"tổn thất do nhiệt độ làm suy giảm khoảng <b>10.5% - 12.8%</b> công suất danh định DC."
        )
    else:
        thermal_analysis = (
            f"Nhiệt độ môi trường cực đại dao động <b>{t_max:.1f}°C</b>, nhiệt độ cell duy trì khoảng <b>45°C - 52°C</b>. "
            f"Tổn thất nhiệt độ ở mức trung bình (~7% - 9%), hiệu suất chuyển đổi của dàn pin Sharp duy trì ổn định."
        )

    # 3. Khuyến nghị vận hành điều độ
    recommendations = [
        f"<b>Đăng ký công suất khả dụng:</b> Đăng ký biểu đồ công suất 96 chu kỳ ngày {d_str} với tổng sản lượng <b>{e_mwh:.2f} MWh</b> và đỉnh <b>{p_max:.2f} MW</b> gửi Điều độ A0 / A3.",
        f"<b>Giám sát nhiệt độ:</b> Theo dõi nhiệt độ dầu MBA chính 110kV và nhiệt độ phòng Inverter trong khung giờ cao điểm 11:00 - 13:30 do nhiệt độ ngoài trời đạt {t_max:.1f}°C.",
        f"<b>Chế độ điều độ công suất phản kháng:</b> Duy trì hệ số cos phi từ 0.95 đến 0.98 theo yêu cầu điều độ của A3."
    ]

    return {
        "date_str": d_str,
        "day_name": day_name,
        "weather_type": weather_type,
        "weather_desc": weather_desc,
        "impact_desc": impact_desc,
        "thermal_analysis": thermal_analysis,
        "recommendations": recommendations,
        "kpis": day_data
    }
