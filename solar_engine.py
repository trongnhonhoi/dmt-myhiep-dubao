"""
Engine tính toán và dự báo sản lượng điện mặt trời chu kỳ 15 phút
Nhà máy Điện mặt trời Mỹ Hiệp (50MWp / 40.075MW - Tấm pin Sharp NU-440)
Bộ Parser Đa Tầng Siêu Cấp: Hỗ trợ cả File Bức Xạ Trạm Thời Tiết & File Công Suất Điện Lực SCADA (110kV / 22kV / 7 Trạm Inverter)
"""

import io
import re
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional, List, Union


class MyHiepSolarPlantConfig:
    """Cấu hình thông số kỹ thuật tiêu chuẩn của Nhà máy ĐMT Mỹ Hiệp"""
    PLANT_NAME = "Nhà máy Điện mặt trời Mỹ Hiệp"
    PLANT_ADDRESS = "Thôn Vạn Phước, Xã Phù Mỹ Nam, Tỉnh Gia Lai"
    PLANT_PHONE = "0256 3856 667"
    DISPATCH_CENTERS = "Điều Độ Quốc Gia (A0) & Điều Độ Miền Trung (A3)"
    DC_CAPACITY_MWP = 50.00          # Công suất lắp đặt DC tấm pin: 50 MWp
    AC_CAPACITY_MW = 40.075          # Công suất giới hạn Inverter AC: 40.075 MW
    
    # Thông số tấm pin Sharp NU-440 (Monocrystalline)
    MODULE_MODEL = "Sharp NU-440"
    MODULE_PMP_STC_W = 440.0         # Công suất danh định STC 440Wp
    TEMP_COEFF_PMP = -0.00347        # Hệ số suy giảm công suất theo nhiệt độ: -0.347%/°C
    NOCT_C = 45.0                    # Nhiệt độ cell danh định NOCT: 45°C
    STC_IRRADIANCE = 1000.0          # Bức xạ chuẩn STC: 1000 W/m2
    STC_TEMP_C = 25.0                # Nhiệt độ cell chuẩn STC: 25°C
    
    # Các hệ số tổn hao mặc định của hệ thống
    DEFAULT_SOILING_LOSS = 0.020     # Tổn hao bụi bẩn: 2.0%
    DEFAULT_DC_CABLE_LOSS = 0.015    # Tổn hao cáp DC: 1.5%
    DEFAULT_MISMATCH_LID_LOSS = 0.015# Tổn hao mismatch & suy giảm ban đầu LID: 1.5%
    DEFAULT_INVERTER_EFF = 0.986     # Hiệu suất Inverter danh định: 98.6%
    DEFAULT_AC_TRAFO_LOSS = 0.012    # Tổn thất máy biến áp và cáp AC trung thế: 1.2%
    DEFAULT_AUX_LOSS = 0.003         # Tự dùng trạm và phụ tải phụ: 0.3%


def robust_decode_bytes(b: bytes) -> str:
    """
    Giải mã mảng byte cực kỳ an toàn, tự động nhận diện chuẩn mã hóa Windows UTF-16, UTF-8-BOM, CP1258...
    """
    if b.startswith(b'\xff\xfe') or b.startswith(b'\xfe\xff'):
        try:
            return b.decode('utf-16').replace('\x00', '')
        except Exception:
            pass
            
    if b.startswith(b'\xef\xbb\xbf'):
        try:
            return b.decode('utf-8-sig').replace('\x00', '')
        except Exception:
            pass
            
    for enc in ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'cp1258', 'cp1252', 'latin-1']:
        try:
            decoded = b.decode(enc)
            if '\x00' not in decoded and len(decoded.strip()) > 0:
                return decoded
        except Exception:
            continue
            
    try:
        return b.decode('utf-16', errors='ignore').replace('\x00', '')
    except Exception:
        return b.decode('latin-1', errors='ignore').replace('\x00', '')


def calculate_cell_temperature(
    irradiance_wm2: pd.Series, 
    amb_temp_c: pd.Series, 
    measured_pv_temp_c: Optional[pd.Series] = None,
    noct_c: float = MyHiepSolarPlantConfig.NOCT_C
) -> pd.Series:
    """
    Tính nhiệt độ cell quang điện:
    - Nếu có đo thực tế nhiệt độ tấm pin (PV Temperature) từ trạm thời tiết (> 0°C), ưu tiên dùng trực tiếp.
    - Nếu không, tính theo mô hình NOCT tiêu chuẩn (King/Evans formula):
      T_cell = T_ambient + ((NOCT - 20) / 800) * Irradiance
    """
    irradiance_clean = irradiance_wm2.clip(lower=0)
    t_cell_noct = amb_temp_c + ((noct_c - 20.0) / 800.0) * irradiance_clean
    
    if measured_pv_temp_c is not None:
        pv_temp_clean = pd.to_numeric(measured_pv_temp_c, errors='coerce')
        is_valid_pv_temp = (pv_temp_clean > 5.0) & (pv_temp_clean < 85.0)
        if is_valid_pv_temp.sum() > 0:
            t_cell_result = np.where(is_valid_pv_temp, pv_temp_clean + 1.5, t_cell_noct)
            return pd.Series(t_cell_result, index=irradiance_wm2.index)
        
    return t_cell_noct


def calculate_solar_output(
    irradiance_wm2: pd.Series,
    cell_temp_c: pd.Series,
    dc_capacity_mwp: float = MyHiepSolarPlantConfig.DC_CAPACITY_MWP,
    ac_capacity_mw: float = MyHiepSolarPlantConfig.AC_CAPACITY_MW,
    temp_coeff: float = MyHiepSolarPlantConfig.TEMP_COEFF_PMP,
    soiling_loss: float = MyHiepSolarPlantConfig.DEFAULT_SOILING_LOSS,
    dc_cable_loss: float = MyHiepSolarPlantConfig.DEFAULT_DC_CABLE_LOSS,
    mismatch_loss: float = MyHiepSolarPlantConfig.DEFAULT_MISMATCH_LID_LOSS,
    inverter_eff: float = MyHiepSolarPlantConfig.DEFAULT_INVERTER_EFF,
    ac_trafo_loss: float = MyHiepSolarPlantConfig.DEFAULT_AC_TRAFO_LOSS,
    aux_loss: float = MyHiepSolarPlantConfig.DEFAULT_AUX_LOSS
) -> Dict[str, pd.Series]:
    """
    Tính toán chi tiết công suất phát theo mô hình quang điện vật lý & giới hạn Inverter Mỹ Hiệp.
    """
    temp_derating = 1.0 + temp_coeff * (cell_temp_c - MyHiepSolarPlantConfig.STC_TEMP_C)
    temp_derating = temp_derating.clip(lower=0.5, upper=1.2)
    
    # Hệ số hiệu chuẩn vận hành thực tế Nhà máy ĐMT Mỹ Hiệp (1000 W/m2 -> 40.0 MW)
    plant_calibration_factor = 0.8252
    dc_derate_factor = (1.0 - soiling_loss) * (1.0 - dc_cable_loss) * (1.0 - mismatch_loss) * plant_calibration_factor
    
    irradiance_clean = irradiance_wm2.clip(lower=0)
    p_dc_mw = dc_capacity_mwp * (irradiance_clean / MyHiepSolarPlantConfig.STC_IRRADIANCE) * temp_derating * dc_derate_factor
    p_dc_mw = p_dc_mw.clip(lower=0)
    
    p_ac_raw_mw = p_dc_mw * inverter_eff
    p_ac_inv_mw = p_ac_raw_mw.clip(upper=ac_capacity_mw)
    clipping_loss_mw = (p_ac_raw_mw - ac_capacity_mw).clip(lower=0)
    
    grid_delivery_factor = (1.0 - ac_trafo_loss) * (1.0 - aux_loss)
    p_grid_mw = p_ac_inv_mw * grid_delivery_factor
    
    return {
        "p_dc_mw": p_dc_mw,
        "p_ac_raw_mw": p_ac_raw_mw,
        "p_ac_inv_mw": p_ac_inv_mw,
        "clipping_loss_mw": clipping_loss_mw,
        "p_grid_mw": p_grid_mw,
        "temp_derating": temp_derating
    }


def parse_timestamp_series(series: pd.Series) -> pd.Series:
    """
    Chuyển đổi chuỗi ngày giờ linh hoạt với mọi định dạng:
    DD/MM/YY HH:MM, DD/MM/YYYY HH:MM, YYYY-MM-DD HH:MM:SS, DD-MM-YYYY...
    """
    ts1 = pd.to_datetime(series, dayfirst=True, format='mixed', errors='coerce')
    if ts1.notna().sum() > 0:
        return ts1
        
    ts2 = pd.to_datetime(series, format='%d/%m/%y %H:%M', errors='coerce')
    if ts2.notna().sum() > 0:
        return ts2
        
    ts3 = pd.to_datetime(series, format='%d/%m/%Y %H:%M', errors='coerce')
    if ts3.notna().sum() > 0:
        return ts3
        
    return ts1


def parse_scada_weather_txt_advanced(text_content: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Parser đa tầng cho file TXT trạm SCADA Thời Tiết Mỹ Hiệp
    """
    clean_text = text_content.replace('\x00', '')
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Nội dung dữ liệu quá ngắn!")

    data_start_idx = -1
    ts_regex = re.compile(r'\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}')
    
    for idx in range(min(20, len(lines))):
        line_cur = lines[idx]
        tokens = line_cur.split(';') if ';' in line_cur else line_cur.split(',')
        first_token = tokens[0].strip() if tokens else ""
        if ts_regex.search(first_token) and (':' in first_token or ':' in line_cur):
            data_start_idx = idx
            break
            
    if data_start_idx == -1:
        for idx in range(min(20, len(lines))):
            if ':' in lines[idx] and any(c.isdigit() for c in lines[idx]):
                data_start_idx = idx
                break
                
    if data_start_idx <= 0:
        data_start_idx = 1

    header_lines = lines[:data_start_idx]
    data_lines = lines[data_start_idx:]
    
    sep = ';' if ';' in lines[data_start_idx] else (',' if ',' in lines[data_start_idx] else '\t')
    
    col_names = []
    if len(header_lines) >= 2:
        station_tokens = [t.strip() for t in header_lines[0].split(sep)]
        param_tokens = [t.strip() for t in header_lines[1].split(sep)]
        
        current_station = "MAIN"
        max_len = max(len(station_tokens), len(param_tokens))
        station_tokens += [''] * (max_len - len(station_tokens))
        param_tokens += [''] * (max_len - len(param_tokens))
        
        for i in range(max_len):
            s = station_tokens[i]
            p = param_tokens[i]
            if s and any(k in s.upper() for k in ['STATION', 'TRAM', 'WS', 'PLANT']):
                current_station = re.sub(r'[^A-Za-z0-9_-]', '', s)
            if i == 0:
                col_names.append("Timestamp")
            elif p:
                col_names.append(f"{current_station}_{p}" if current_station != "MAIN" else p)
            else:
                col_names.append(f"Col_{i}")
    elif len(header_lines) == 1:
        tokens = [t.strip() for t in header_lines[0].split(sep)]
        col_names = ["Timestamp" if i == 0 else (tokens[i] if tokens[i] else f"Col_{i}") for i in range(len(tokens))]
    else:
        first_row_len = len(data_lines[0].split(sep))
        col_names = ["Timestamp"] + [f"Col_{i}" for i in range(1, first_row_len)]

    parsed_rows = []
    for line in data_lines:
        tokens = [t.strip() for t in line.split(sep)]
        if len(tokens) <= 1 or not tokens[0]:
            continue
        if not ts_regex.search(tokens[0]):
            continue
        parsed_rows.append(tokens)
        
    if not parsed_rows:
        raise ValueError("Không tìm thấy dòng dữ liệu ngày giờ hợp lệ trong file TXT!")
        
    max_cols = max(len(r) for r in parsed_rows)
    if len(col_names) < max_cols:
        col_names += [f"Col_{i}" for i in range(len(col_names), max_cols)]
        
    df_raw = pd.DataFrame(parsed_rows)
    df_raw.columns = col_names[:df_raw.shape[1]]
    
    ts_col = df_raw.columns[0]
    df_raw['Timestamp'] = parse_timestamp_series(df_raw[ts_col])
    df_raw = df_raw.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)
    
    if len(df_raw) == 0:
        raise ValueError("Không thể nhận diện định dạng ngày giờ hợp lệ trong cột thời gian!")

    ghi_cols = [c for c in df_raw.columns if c != 'Timestamp' and any(k in c.upper() for k in ['GHI', 'IRRADIANCE', 'BUC_XA', 'POA', 'RAD', 'SOLAR', 'W/M2', 'WM2'])]
    for c in ghi_cols:
        df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce').fillna(0.0).clip(lower=0)
        
    if ghi_cols:
        df_raw['Irradiance'] = df_raw[ghi_cols].mean(axis=1).round(2)
    else:
        candidate_cols = []
        for c in df_raw.columns:
            if c != 'Timestamp':
                s_num = pd.to_numeric(df_raw[c], errors='coerce').dropna()
                if len(s_num) > 0 and s_num.max() > 10.0 and s_num.max() < 1600.0:
                    candidate_cols.append(c)
        if candidate_cols:
            df_raw['Irradiance'] = df_raw[candidate_cols].apply(pd.to_numeric, errors='coerce').fillna(0.0).clip(lower=0).mean(axis=1).round(2)
            ghi_cols = candidate_cols
        else:
            df_raw['Irradiance'] = 0.0

    air_temp_cols = [c for c in df_raw.columns if c != 'Timestamp' and any(k in c.upper() for k in ['AIR TEMP', 'AIR TEMPERATURE', 'T_AMB', 'TAMB', 'NHIET_DO_KK'])]
    for c in air_temp_cols:
        df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce')
        
    if air_temp_cols:
        df_raw['Air_Temperature'] = df_raw[air_temp_cols].mean(axis=1).interpolate().fillna(30.0).round(2)
    else:
        df_raw['Air_Temperature'] = 24.0 + (df_raw['Irradiance'] / 1000.0) * 10.0

    pv_temp_cols = [c for c in df_raw.columns if c != 'Timestamp' and any(k in c.upper() for k in ['PV TEMP', 'PV TEMPERATURE', 'T_MOD', 'MODULE TEMP', 'NHIET_DO_PIN'])]
    for c in pv_temp_cols:
        df_raw[c] = pd.to_numeric(df_raw[c], errors='coerce')
        # Lọc bỏ các mã lỗi âm cực lớn của cảm biến (ví dụ: -470783000)
        df_raw.loc[(df_raw[c] < -10.0) | (df_raw[c] > 95.0), c] = np.nan
        
    if pv_temp_cols:
        df_raw['PV_Temperature'] = df_raw[pv_temp_cols].mean(axis=1).interpolate().round(2)
    else:
        df_raw['PV_Temperature'] = None

    metadata = {
        "format": "SCADA_WEATHER_TXT",
        "ghi_sensor_count": len(ghi_cols),
        "ghi_sensor_names": ghi_cols,
        "pv_temp_sensor_count": len(pv_temp_cols),
        "pv_temp_sensor_names": pv_temp_cols,
        "air_temp_sensor_count": len(air_temp_cols),
        "air_temp_sensor_names": air_temp_cols,
        "total_rows": len(df_raw),
        "start_ts": df_raw['Timestamp'].min(),
        "end_ts": df_raw['Timestamp'].max()
    }
    
    res_df = pd.DataFrame({
        'Timestamp': df_raw['Timestamp'],
        'Irradiance': df_raw['Irradiance'],
        'Temperature': df_raw['Air_Temperature']
    })
    if 'PV_Temperature' in df_raw and df_raw['PV_Temperature'] is not None:
        res_df['PV_Temperature'] = df_raw['PV_Temperature']
        
    return res_df, metadata


def parse_scada_power_txt_advanced(text_content: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Parser chuyên dụng cho file TXT SCADA Công Suất Điện Lực Mỹ Hiệp:
    Cột 110KV_P(MW), 110KV_Q(MVAr), 110KV_U(kV), 110KV_F(Hz), 22KV, và 7 Trạm Inverter STATION-01..07
    """
    clean_text = text_content.replace('\x00', '')
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Nội dung file công suất quá ngắn!")

    data_start_idx = -1
    ts_regex = re.compile(r'\d{1,4}[/.-]\d{1,2}[/.-]\d{1,4}')
    
    for idx in range(min(20, len(lines))):
        line_cur = lines[idx]
        tokens = line_cur.split(';') if ';' in line_cur else line_cur.split(',')
        first_token = tokens[0].strip() if tokens else ""
        if ts_regex.search(first_token) and (':' in first_token or ':' in line_cur):
            data_start_idx = idx
            break
            
    if data_start_idx == -1:
        for idx in range(min(20, len(lines))):
            if ':' in lines[idx] and any(c.isdigit() for c in lines[idx]):
                data_start_idx = idx
                break
                
    if data_start_idx <= 0:
        data_start_idx = 2

    header_lines = lines[:data_start_idx]
    data_lines = lines[data_start_idx:]
    sep = ';' if ';' in lines[data_start_idx] else (',' if ',' in lines[data_start_idx] else '\t')
    
    col_names = []
    if len(header_lines) >= 2:
        station_tokens = [t.strip() for t in header_lines[0].split(sep)]
        param_tokens = [t.strip() for t in header_lines[1].split(sep)]
        
        current_sec = "PLANT"
        max_len = max(len(station_tokens), len(param_tokens))
        station_tokens += [''] * (max_len - len(station_tokens))
        param_tokens += [''] * (max_len - len(param_tokens))
        
        for i in range(max_len):
            s = station_tokens[i]
            p = param_tokens[i]
            if s and s.upper() != 'SOLAR' and s.upper() != 'PLANT':
                current_sec = re.sub(r'[^A-Za-z0-9_-]', '', s)
            if i == 0:
                col_names.append("Timestamp")
            elif p:
                col_names.append(f"{current_sec}_{p}")
            else:
                col_names.append(f"Col_{i}")
    else:
        tokens = [t.strip() for t in header_lines[0].split(sep)]
        col_names = ["Timestamp" if i == 0 else tokens[i] for i in range(len(tokens))]

    parsed_rows = []
    for line in data_lines:
        tokens = [t.strip() for t in line.split(sep)]
        if len(tokens) <= 1 or not tokens[0]:
            continue
        if not ts_regex.search(tokens[0]):
            continue
        parsed_rows.append(tokens)
        
    if not parsed_rows:
        raise ValueError("Không tìm thấy dòng dữ liệu công suất hợp lệ trong file!")

    max_cols = max(len(r) for r in parsed_rows)
    if len(col_names) < max_cols:
        col_names += [f"Col_{i}" for i in range(len(col_names), max_cols)]
        
    df_raw = pd.DataFrame(parsed_rows)
    df_raw.columns = col_names[:df_raw.shape[1]]
    
    ts_col = df_raw.columns[0]
    df_raw['Timestamp'] = parse_timestamp_series(df_raw[ts_col])
    df_raw = df_raw.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)

    # 1. Tìm cột Công suất tác dụng phát lên lưới 110kV
    p_110kv_col = None
    for c in df_raw.columns:
        c_upper = c.upper()
        if ('110KV' in c_upper or '110_KV' in c_upper or 'GRID' in c_upper) and any(k in c_upper for k in ['P(MW)', 'P_MW', 'ACTIVE', 'CONG_SUAT']):
            p_110kv_col = c
            break
            
    if p_110kv_col is None:
        for c in df_raw.columns:
            if c != 'Timestamp' and any(k in c.upper() for k in ['P(MW)', 'P_MW', 'PMW', 'P_GRID']):
                p_110kv_col = c
                break
                
    if p_110kv_col is not None:
        df_raw['P_Grid_Actual_MW'] = pd.to_numeric(df_raw[p_110kv_col], errors='coerce').fillna(0.0).clip(lower=0)
    else:
        df_raw['P_Grid_Actual_MW'] = 0.0

    # 2. Tìm cột Công suất phản kháng Q (MVAr)
    q_col = None
    for c in df_raw.columns:
        if ('110KV' in c.upper() or 'GRID' in c.upper()) and any(k in c.upper() for k in ['Q(MVAR)', 'Q_MVAR', 'QMVAR']):
            q_col = c
            break
    df_raw['Q_Grid_Actual_MVAr'] = pd.to_numeric(df_raw[q_col], errors='coerce').fillna(0.0) if q_col else 0.0

    # 3. Tìm cột Điện áp U (kV)
    u_col = None
    for c in df_raw.columns:
        if ('110KV' in c.upper() or 'GRID' in c.upper()) and any(k in c.upper() for k in ['U(KV)', 'U_KV', 'VOLT', 'DIEN_AP']):
            u_col = c
            break
    df_raw['U_110kV'] = pd.to_numeric(df_raw[u_col], errors='coerce').fillna(110.0) if u_col else 110.0

    # 4. Tìm cột Tần số F (Hz)
    f_col = None
    for c in df_raw.columns:
        if any(k in c.upper() for k in ['F(HZ)', 'F_HZ', 'FREQ', 'TAN_SO']):
            f_col = c
            break
    df_raw['F_Hz'] = pd.to_numeric(df_raw[f_col], errors='coerce').fillna(50.0) if f_col else 50.0

    # 5. Tìm công suất từng trạm Inverter (STATION-01..07)
    station_cols = [c for c in df_raw.columns if 'STATION' in c.upper() and any(k in c.upper() for k in ['P(MW)', 'P_MW'])]
    for sc in station_cols:
        df_raw[sc] = pd.to_numeric(df_raw[sc], errors='coerce').fillna(0.0)

    metadata = {
        "format": "SCADA_POWER_TELEMETRY",
        "p_grid_col": p_110kv_col,
        "u_110kv_col": u_col,
        "f_hz_col": f_col,
        "inverter_stations_count": len(station_cols),
        "inverter_stations_names": station_cols,
        "total_rows": len(df_raw),
        "start_ts": df_raw['Timestamp'].min(),
        "end_ts": df_raw['Timestamp'].max(),
        "peak_actual_p_mw": float(df_raw['P_Grid_Actual_MW'].max()) if len(df_raw) > 0 else 0.0
    }

    out_cols = ['Timestamp', 'P_Grid_Actual_MW', 'Q_Grid_Actual_MVAr', 'U_110kV', 'F_Hz'] + station_cols
    return df_raw[out_cols], metadata


def process_actual_power_1min_to_15min(df_actual_1min: pd.DataFrame) -> pd.DataFrame:
    """
    Gộp dữ liệu công suất đo thực tế 1 phút sang 96 chu kỳ 15 phút
    """
    df_calc = df_actual_1min.copy().set_index('Timestamp')
    resampler = df_calc.resample('15min', label='left', closed='left')
    
    df_15min_act = pd.DataFrame({
        'P_Grid_Actual_Avg_MW': resampler['P_Grid_Actual_MW'].mean().fillna(0.0),
        'P_Grid_Actual_Max_MW': resampler['P_Grid_Actual_MW'].max().fillna(0.0),
        'Q_Grid_Actual_Avg_MVAr': resampler['Q_Grid_Actual_MVAr'].mean().fillna(0.0) if 'Q_Grid_Actual_MVAr' in df_calc else 0.0,
        'U_110kV_Avg': resampler['U_110kV'].mean().fillna(110.0) if 'U_110kV' in df_calc else 110.0,
        'F_Hz_Avg': resampler['F_Hz'].mean().fillna(50.0) if 'F_Hz' in df_calc else 50.0,
    }).reset_index()
    
    # Sản lượng điện năng thực tế = P_TB * 0.25h (MWh)
    df_15min_act['Energy_Actual_MWh'] = df_15min_act['P_Grid_Actual_Avg_MW'] * 0.25
    
    df_15min_act['Date'] = df_15min_act['Timestamp'].dt.date
    df_15min_act['Start_Time'] = df_15min_act['Timestamp'].dt.strftime('%H:%M')
    df_15min_act['End_Timestamp'] = df_15min_act['Timestamp'] + pd.Timedelta(minutes=15)
    df_15min_act['End_Time'] = df_15min_act['End_Timestamp'].dt.strftime('%H:%M')
    
    minutes_from_midnight = df_15min_act['Timestamp'].dt.hour * 60 + df_15min_act['Timestamp'].dt.minute
    df_15min_act['Interval_Index'] = (minutes_from_midnight // 15) + 1
    
    return df_15min_act


def calculate_forecast_vs_actual_comparison(
    df_forecast_15min: pd.DataFrame,
    df_actual_15min: pd.DataFrame,
    dc_capacity_mwp: float = MyHiepSolarPlantConfig.DC_CAPACITY_MWP
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    So sánh & Đánh giá sai số Dự Báo vs Đo Đếm Thực Tế theo tiêu chuẩn EVN / A0 / A3:
    - MAE (MW), RMSE (MW), Normalized MAE (%), Độ chính xác (%), Điện năng chênh lệch (MWh)
    """
    # Merge theo Timestamp hoặc Interval_Index
    merged = pd.merge(
        df_forecast_15min,
        df_actual_15min[['Timestamp', 'P_Grid_Actual_Avg_MW', 'P_Grid_Actual_Max_MW', 'Energy_Actual_MWh', 'U_110kV_Avg', 'F_Hz_Avg']],
        on='Timestamp',
        how='inner'
    )
    
    if len(merged) == 0:
        merged = pd.merge(
            df_forecast_15min,
            df_actual_15min[['Interval_Index', 'P_Grid_Actual_Avg_MW', 'P_Grid_Actual_Max_MW', 'Energy_Actual_MWh', 'U_110kV_Avg', 'F_Hz_Avg']],
            on='Interval_Index',
            how='inner'
        )
        
    if len(merged) == 0:
        raise ValueError("Không thể ghép nối chuỗi thời gian giữa dữ liệu Dự Báo và Đo Đếm Thực Tế!")

    # Tính độ lệch công suất: Diff = Thực Tế - Dự Báo
    merged['Diff_Power_MW'] = (merged['P_Grid_Actual_Avg_MW'] - merged['P_Grid_Avg_MW']).round(3)
    merged['Abs_Diff_Power_MW'] = merged['Diff_Power_MW'].abs()
    merged['Diff_Energy_MWh'] = (merged['Energy_Actual_MWh'] - merged['Energy_Grid_MWh']).round(4)
    
    # Chỉ tính sai số trong khung giờ có nắng (P_Forecast > 0.1MW hoặc P_Actual > 0.1MW)
    daylight_mask = (merged['P_Grid_Avg_MW'] > 0.05) | (merged['P_Grid_Actual_Avg_MW'] > 0.05)
    df_daylight = merged[daylight_mask] if daylight_mask.sum() > 0 else merged
    
    mae_mw = float(df_daylight['Abs_Diff_Power_MW'].mean())
    rmse_mw = float(np.sqrt((df_daylight['Diff_Power_MW'] ** 2).mean()))
    
    # Normalized MAE (%) theo công suất lắp đặt 50MWp (Quy chuẩn EVN)
    nmae_pct = (mae_mw / dc_capacity_mwp) * 100.0
    accuracy_pct = max(0.0, 100.0 - nmae_pct)
    
    total_energy_forecast = float(merged['Energy_Grid_MWh'].sum())
    total_energy_actual = float(merged['Energy_Actual_MWh'].sum())
    total_diff_energy = total_energy_actual - total_energy_forecast
    energy_accuracy_pct = (1.0 - abs(total_diff_energy) / max(total_energy_forecast, 1.0)) * 100.0
    
    kpis = {
        "mae_mw": round(mae_mw, 3),
        "rmse_mw": round(rmse_mw, 3),
        "nmae_pct": round(nmae_pct, 2),
        "accuracy_pct": round(accuracy_pct, 2),
        "total_energy_forecast_mwh": round(total_energy_forecast, 3),
        "total_energy_actual_mwh": round(total_energy_actual, 3),
        "total_diff_energy_mwh": round(total_diff_energy, 3),
        "energy_accuracy_pct": round(max(0.0, energy_accuracy_pct), 2),
        "peak_actual_mw": round(float(merged['P_Grid_Actual_Avg_MW'].max()), 3),
        "peak_forecast_mw": round(float(merged['P_Grid_Avg_MW'].max()), 3),
        "total_compared_intervals": len(merged)
    }
    
    return merged, kpis


def detect_and_parse_input_data(
    file_or_content: Union[str, bytes, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Hàm tổng quát nhận diện và đọc mọi định dạng: TXT SCADA Thời tiết, TXT SCADA Điện lực Công suất, CSV, Excel
    """
    metadata = {"format": "GENERIC"}
    
    if isinstance(file_or_content, pd.DataFrame):
        df_clean = detect_and_parse_columns(file_or_content)
        metadata["total_rows"] = len(df_clean)
        metadata["start_ts"] = df_clean['Timestamp'].min() if len(df_clean) > 0 else None
        metadata["end_ts"] = df_clean['Timestamp'].max() if len(df_clean) > 0 else None
        return df_clean, metadata

    text_content = ""
    if isinstance(file_or_content, bytes):
        text_content = robust_decode_bytes(file_or_content)
    elif isinstance(file_or_content, str):
        if "\n" not in file_or_content and (file_or_content.endswith('.txt') or file_or_content.endswith('.csv')):
            with open(file_or_content, 'rb') as f:
                text_content = robust_decode_bytes(f.read())
        elif "\n" not in file_or_content and (file_or_content.endswith('.xlsx') or file_or_content.endswith('.xls')):
            df_in = pd.read_excel(file_or_content)
            df_clean = detect_and_parse_columns(df_in)
            return df_clean, {
                "format": "EXCEL", 
                "total_rows": len(df_clean),
                "start_ts": df_clean['Timestamp'].min() if len(df_clean) > 0 else None,
                "end_ts": df_clean['Timestamp'].max() if len(df_clean) > 0 else None
            }
        else:
            text_content = file_or_content

    # 1. Nhận diện file SCADA Công Suất Điện Lực (110kV / 22kV / STATION-01..07)
    if text_content and ('110KV' in text_content.upper() or 'P(MW)' in text_content.upper() or 'STATION-01' in text_content.upper()):
        try:
            res_df_p, meta_p = parse_scada_power_txt_advanced(text_content)
            if len(res_df_p) > 0:
                return res_df_p, meta_p
        except Exception:
            pass

    # 2. Thử Parser SCADA Thời Tiết (GHI, PV Temperature)
    if text_content and len(text_content.strip()) > 0:
        try:
            res_df, meta = parse_scada_weather_txt_advanced(text_content)
            if len(res_df) > 0:
                return res_df, meta
        except Exception:
            pass

    # 3. Thử đọc dạng CSV / TXT với separator tự động
    if text_content:
        for sep in [';', ',', '\t', r'\s+']:
            try:
                df_try = pd.read_csv(io.StringIO(text_content), sep=sep, engine='python')
                if len(df_try.columns) >= 2 and len(df_try) > 0:
                    df_clean = detect_and_parse_columns(df_try)
                    if len(df_clean) > 0:
                        return df_clean, {
                            "format": f"CSV_SEP_{sep}", 
                            "total_rows": len(df_clean),
                            "start_ts": df_clean['Timestamp'].min(),
                            "end_ts": df_clean['Timestamp'].max()
                        }
            except Exception:
                continue
                
    # 4. Thử đọc Excel nếu là bytes
    if isinstance(file_or_content, bytes):
        try:
            df_excel = pd.read_excel(io.BytesIO(file_or_content))
            df_clean = detect_and_parse_columns(df_excel)
            if len(df_clean) > 0:
                return df_clean, {
                    "format": "EXCEL", 
                    "total_rows": len(df_clean),
                    "start_ts": df_clean['Timestamp'].min(),
                    "end_ts": df_clean['Timestamp'].max()
                }
        except Exception:
            pass

    raise ValueError("Không tìm thấy dòng dữ liệu ngày giờ và tham số hợp lệ. Vui lòng kiểm tra lại cấu trúc file!")


def detect_and_parse_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tự động nhận diện và ánh xạ các cột dữ liệu trong DataFrame
    """
    df_clean = df.copy()
    
    # 1. Tìm cột thời gian
    time_col = None
    time_keywords = ['time', 'date', 'datetime', 'thoi_gian', 'ngay_gio', 'timestamp', 'gio', 'ngay']
    for col in df_clean.columns:
        if any(kw in str(col).lower() for kw in time_keywords):
            time_col = col
            break
            
    if time_col is None:
        time_col = df_clean.columns[0]
        
    df_clean['Timestamp'] = parse_timestamp_series(df_clean[time_col])
    df_clean = df_clean.dropna(subset=['Timestamp']).sort_values('Timestamp').reset_index(drop=True)
    
    if len(df_clean) == 0:
        raise ValueError("Cột thời gian không chứa giá trị ngày giờ hợp lệ!")

    # 2. Tìm cột bức xạ hoặc công suất
    rad_col = None
    rad_keywords = ['rad', 'irr', 'ghi', 'poa', 'buc_xa', 'solar', 'w/m2', 'w/m', 'kw/m2', 'wm2', 'intensity']
    for col in df_clean.columns:
        if col != time_col and col != 'Timestamp':
            if any(kw in str(col).lower() for kw in rad_keywords):
                rad_col = col
                break
                
    if rad_col is None:
        for c in df_clean.columns:
            if c not in [time_col, 'Timestamp']:
                s_num = pd.to_numeric(df_clean[c], errors='coerce').dropna()
                if len(s_num) > 0 and s_num.max() > 10.0 and s_num.max() < 1600.0:
                    rad_col = c
                    break
                    
    if rad_col is None:
        numeric_cols = [c for c in df_clean.select_dtypes(include=[np.number]).columns if c not in [time_col, 'Timestamp']]
        if numeric_cols:
            rad_col = numeric_cols[0]
        else:
            raise ValueError("Không tìm thấy cột dữ liệu số hợp lệ trong file import!")
            
    df_clean['Irradiance'] = pd.to_numeric(df_clean[rad_col], errors='coerce').fillna(0.0).clip(lower=0)
    if df_clean['Irradiance'].max() > 0 and df_clean['Irradiance'].max() < 5.0:
        df_clean['Irradiance'] = df_clean['Irradiance'] * 1000.0

    # 3. Nhiệt độ môi trường
    temp_col = None
    temp_keywords = ['temp', 'nhiet_do', 't_amb', 'tamb', 'temperature', 'nhietdo', 'degc', 'celsius']
    for col in df_clean.columns:
        if col not in [time_col, 'Timestamp', rad_col]:
            if any(kw in str(col).lower() for kw in temp_keywords):
                temp_col = col
                break
                
    if temp_col is not None:
        df_clean['Temperature'] = pd.to_numeric(df_clean[temp_col], errors='coerce')
        df_clean['Temperature'] = df_clean['Temperature'].interpolate().fillna(30.0)
    else:
        df_clean['Temperature'] = 24.0 + (df_clean['Irradiance'] / 1000.0) * 10.0

    # 4. Nhiệt độ tấm pin nếu có
    pv_temp_col = None
    pv_keywords = ['pv temp', 'pv_temp', 't_mod', 'module temp', 'cell_temp', 'nhiet_do_pin']
    for col in df_clean.columns:
        if col not in [time_col, 'Timestamp', rad_col, temp_col]:
            if any(kw in str(col).lower() for kw in pv_keywords):
                pv_temp_col = col
                break
    if pv_temp_col is not None:
        df_clean['PV_Temperature'] = pd.to_numeric(df_clean[pv_temp_col], errors='coerce')

    res_cols = ['Timestamp', 'Irradiance', 'Temperature']
    if 'PV_Temperature' in df_clean:
        res_cols.append('PV_Temperature')
        
    return df_clean[res_cols]


def process_1min_to_15min_forecast(
    df_1min: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """
    Xử lý toàn diện chuỗi dữ liệu 1 phút sang chu kỳ 15 phút (96 chu kỳ/ngày)
    và tính toán sản lượng điện của Nhà máy ĐMT Mỹ Hiệp.
    """
    if len(df_1min) == 0:
        raise ValueError("Dữ liệu đầu vào rỗng (0 dòng)!")

    if params is None:
        params = {}
        
    dc_mwp = params.get('dc_capacity_mwp', MyHiepSolarPlantConfig.DC_CAPACITY_MWP)
    ac_mw = params.get('ac_capacity_mw', MyHiepSolarPlantConfig.AC_CAPACITY_MW)
    temp_coeff = params.get('temp_coeff', MyHiepSolarPlantConfig.TEMP_COEFF_PMP)
    noct_c = params.get('noct_c', MyHiepSolarPlantConfig.NOCT_C)
    soiling = params.get('soiling_loss', MyHiepSolarPlantConfig.DEFAULT_SOILING_LOSS)
    dc_cable = params.get('dc_cable_loss', MyHiepSolarPlantConfig.DEFAULT_DC_CABLE_LOSS)
    mismatch = params.get('mismatch_loss', MyHiepSolarPlantConfig.DEFAULT_MISMATCH_LID_LOSS)
    inv_eff = params.get('inverter_eff', MyHiepSolarPlantConfig.DEFAULT_INVERTER_EFF)
    ac_trafo = params.get('ac_trafo_loss', MyHiepSolarPlantConfig.DEFAULT_AC_TRAFO_LOSS)
    aux_loss = params.get('aux_loss', MyHiepSolarPlantConfig.DEFAULT_AUX_LOSS)
    
    df_1min_calc = df_1min.copy()
    measured_pv_temp = df_1min_calc['PV_Temperature'] if 'PV_Temperature' in df_1min_calc else None
    
    df_1min_calc['Cell_Temp_C'] = calculate_cell_temperature(
        df_1min_calc['Irradiance'], 
        df_1min_calc['Temperature'], 
        measured_pv_temp_c=measured_pv_temp,
        noct_c=noct_c
    )
    
    out_1min = calculate_solar_output(
        irradiance_wm2=df_1min_calc['Irradiance'],
        cell_temp_c=df_1min_calc['Cell_Temp_C'],
        dc_capacity_mwp=dc_mwp,
        ac_capacity_mw=ac_mw,
        temp_coeff=temp_coeff,
        soiling_loss=soiling,
        dc_cable_loss=dc_cable,
        mismatch_loss=mismatch,
        inverter_eff=inv_eff,
        ac_trafo_loss=ac_trafo,
        aux_loss=aux_loss
    )
    
    for key, series in out_1min.items():
        df_1min_calc[key] = series
        
    df_1min_calc['energy_grid_mwh'] = df_1min_calc['p_grid_mw'] / 60.0
    
    # Resample 15 phút
    df_1min_calc = df_1min_calc.set_index('Timestamp')
    resampler = df_1min_calc.resample('15min', label='left', closed='left')
    
    df_15min = pd.DataFrame({
        'Irradiance_Avg_Wm2': resampler['Irradiance'].mean().fillna(0.0),
        'Irradiance_Max_Wm2': resampler['Irradiance'].max().fillna(0.0),
        'Amb_Temp_Avg_C': resampler['Temperature'].mean().fillna(25.0),
        'Cell_Temp_Avg_C': resampler['Cell_Temp_C'].mean().fillna(25.0),
        'P_DC_Avg_MW': resampler['p_dc_mw'].mean().fillna(0.0),
        'P_AC_Raw_Avg_MW': resampler['p_ac_raw_mw'].mean().fillna(0.0),
        'P_AC_Inv_Avg_MW': resampler['p_ac_inv_mw'].mean().fillna(0.0),
        'Clipping_Loss_Avg_MW': resampler['clipping_loss_mw'].mean().fillna(0.0),
        'P_Grid_Avg_MW': resampler['p_grid_mw'].mean().fillna(0.0),
        'Energy_Grid_MWh': resampler['energy_grid_mwh'].sum().fillna(0.0),
    }).reset_index()
    
    df_15min['Date'] = df_15min['Timestamp'].dt.date
    df_15min['Start_Time'] = df_15min['Timestamp'].dt.strftime('%H:%M')
    df_15min['End_Timestamp'] = df_15min['Timestamp'] + pd.Timedelta(minutes=15)
    df_15min['End_Time'] = df_15min['End_Timestamp'].dt.strftime('%H:%M')
    
    minutes_from_midnight = df_15min['Timestamp'].dt.hour * 60 + df_15min['Timestamp'].dt.minute
    df_15min['Interval_Index'] = (minutes_from_midnight // 15) + 1
    
    grid_factor = (1.0 - ac_trafo) * (1.0 - aux_loss)
    df_15min['Clipping_Loss_MWh'] = df_15min['Clipping_Loss_Avg_MW'] * 0.25 * grid_factor
    
    total_energy_mwh = df_15min['Energy_Grid_MWh'].sum()
    total_clipping_mwh = df_15min['Clipping_Loss_MWh'].sum()
    peak_grid_mw = df_15min['P_Grid_Avg_MW'].max() if len(df_15min) > 0 else 0.0
    peak_dc_mw = df_15min['P_DC_Avg_MW'].max() if len(df_15min) > 0 else 0.0
    max_irradiance = df_15min['Irradiance_Max_Wm2'].max() if len(df_15min) > 0 else 0.0
    
    total_solar_insolation_kwh_m2 = (df_1min_calc['Irradiance'].sum() / 60.0) / 1000.0
    
    if total_solar_insolation_kwh_m2 > 0:
        pr_percentage = (total_energy_mwh / (dc_mwp * total_solar_insolation_kwh_m2)) * 100.0
        specific_yield_kwh_kwp = (total_energy_mwh * 1000.0) / (dc_mwp * 1000.0)
    else:
        pr_percentage = 0.0
        specific_yield_kwh_kwp = 0.0
        
    clipping_loss_ratio = (total_clipping_mwh / (total_energy_mwh + total_clipping_mwh) * 100.0) if (total_energy_mwh + total_clipping_mwh) > 0 else 0.0

    start_ts = df_15min['Timestamp'].min() if len(df_15min) > 0 else datetime.now()
    end_ts = df_15min['End_Timestamp'].max() if len(df_15min) > 0 else datetime.now()

    kpi_summary = {
        "plant_name": MyHiepSolarPlantConfig.PLANT_NAME,
        "dc_capacity_mwp": dc_mwp,
        "ac_capacity_mw": ac_mw,
        "total_energy_mwh": round(float(total_energy_mwh), 3),
        "peak_grid_mw": round(float(peak_grid_mw), 3),
        "peak_dc_mw": round(float(peak_dc_mw), 3),
        "max_irradiance_wm2": round(float(max_irradiance), 1),
        "total_clipping_loss_mwh": round(float(total_clipping_mwh), 3),
        "clipping_loss_ratio_pct": round(float(clipping_loss_ratio), 2),
        "solar_insolation_kwh_m2": round(float(total_solar_insolation_kwh_m2), 3),
        "performance_ratio_pct": round(float(pr_percentage), 2),
        "specific_yield_kwh_kwp": round(float(specific_yield_kwh_kwp), 2),
        "total_15min_intervals": len(df_15min),
        "start_time": start_ts,
        "end_time": end_ts
    }
    
    return df_1min_calc.reset_index(), df_15min, kpi_summary


def forecast_rolling_intervals(
    start_time: Optional[Union[str, datetime]] = None,
    n_intervals: int = 18,
    params: Optional[Dict[str, Any]] = None,
    weather_condition: str = "Nắng đẹp (Clear Sky)"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Dự báo công suất và sản lượng cho N chu kỳ 15 phút tiếp theo (mặc định 18 chu kỳ = 4.5 giờ)
    áp dụng đầy đủ đặc tính kỹ thuật ĐMT Mỹ Hiệp (50MWp / 40.075MW, Sharp NU-440).
    """
    if params is None:
        params = {}
        
    dc_mwp = params.get('dc_capacity_mwp', MyHiepSolarPlantConfig.DC_CAPACITY_MWP)
    ac_mw = params.get('ac_capacity_mw', MyHiepSolarPlantConfig.AC_CAPACITY_MW)
    temp_coeff = params.get('temp_coeff', MyHiepSolarPlantConfig.TEMP_COEFF_PMP)
    noct = params.get('noct_c', MyHiepSolarPlantConfig.NOCT_C)
    soiling = params.get('soiling_loss', MyHiepSolarPlantConfig.DEFAULT_SOILING_LOSS)
    dc_cable = params.get('dc_cable_loss', MyHiepSolarPlantConfig.DEFAULT_DC_CABLE_LOSS)
    mismatch = params.get('mismatch_loss', MyHiepSolarPlantConfig.DEFAULT_MISMATCH_LID_LOSS)
    inv_eff = params.get('inverter_eff', MyHiepSolarPlantConfig.DEFAULT_INVERTER_EFF)
    ac_trafo = params.get('ac_trafo_loss', MyHiepSolarPlantConfig.DEFAULT_AC_TRAFO_LOSS)
    aux_loss = params.get('aux_loss', MyHiepSolarPlantConfig.DEFAULT_AUX_LOSS)
    
    if start_time is None:
        base_dt = datetime(2026, 8, 27, 14, 15)
    elif isinstance(start_time, str):
        base_dt = pd.to_datetime(start_time)
    else:
        base_dt = start_time

    rows = []
    for i in range(n_intervals):
        start_t = base_dt + timedelta(minutes=15 * i)
        end_t = start_t + timedelta(minutes=15)
        
        mid_hr = (start_t.hour * 60 + start_t.minute + 7.5) / 60.0
        sunrise = 5.75
        sunset = 18.25
        
        if sunrise <= mid_hr <= sunset:
            zenith = np.sin(np.pi * (mid_hr - sunrise) / (sunset - sunrise))
            irr = 1050.0 * (zenith ** 1.15)
            if "mây thay đổi" in weather_condition.lower():
                cloud_dip = 1.0 - 0.35 * (np.sin(mid_hr * 3.5) ** 2)
                irr = irr * max(0.2, cloud_dip)
            elif "nhiều mây" in weather_condition.lower() or "mưa" in weather_condition.lower():
                irr = irr * 0.35
            temp_phase = np.sin(np.pi * (mid_hr - 7.0) / 14.0) if 7.0 <= mid_hr <= 21.0 else 0.0
            amb_temp = 24.5 + 11.5 * max(0.0, temp_phase)
            cell_temp = amb_temp + ((noct - 20.0) / 800.0) * irr + 1.5
        else:
            irr = 0.0
            amb_temp = 24.0
            cell_temp = 24.0
            
        f_temp = 1.0 + temp_coeff * (cell_temp - 25.0)
        f_temp = max(0.5, min(1.2, f_temp))
        
        dc_derate = (1.0 - soiling) * (1.0 - dc_cable) * (1.0 - mismatch)
        p_dc = dc_mwp * (irr / 1000.0) * f_temp * dc_derate
        
        p_ac_raw = p_dc * inv_eff
        p_ac_inv = min(p_ac_raw, ac_mw)
        clipping_mw = max(0.0, p_ac_raw - ac_mw)
        
        grid_factor = (1.0 - ac_trafo) * (1.0 - aux_loss)
        p_grid = p_ac_inv * grid_factor
        
        e_mwh = p_grid * 0.25
        clip_mwh = clipping_mw * grid_factor * 0.25
        
        interval_idx = (start_t.hour * 60 + start_t.minute) // 15 + 1
        
        rows.append({
            'Interval_Index': interval_idx,
            'Date': start_t.strftime('%d/%m/%Y'),
            'Start_Time': start_t.strftime('%H:%M'),
            'End_Time': end_t.strftime('%H:%M'),
            'Timestamp': start_t,
            'End_Timestamp': end_t,
            'Irradiance_Avg_Wm2': round(irr, 1),
            'Irradiance_Max_Wm2': round(irr, 1),
            'Amb_Temp_Avg_C': round(amb_temp, 1),
            'Cell_Temp_Avg_C': round(cell_temp, 1),
            'P_DC_Avg_MW': round(p_dc, 3),
            'P_AC_Raw_Avg_MW': round(p_ac_raw, 3),
            'P_AC_Inv_Avg_MW': round(p_ac_inv, 3),
            'P_Grid_Avg_MW': round(p_grid, 3),
            'Energy_Grid_MWh': round(e_mwh, 4),
            'Clipping_Loss_Avg_MW': round(clipping_mw, 3),
            'Clipping_Loss_MWh': round(clip_mwh, 4)
        })

    df_res = pd.DataFrame(rows)
    total_energy = df_res['Energy_Grid_MWh'].sum()
    total_clip = df_res['Clipping_Loss_MWh'].sum()
    peak_grid = df_res['P_Grid_Avg_MW'].max()
    peak_dc = df_res['P_DC_Avg_MW'].max()
    
    kpis = {
        "plant_name": MyHiepSolarPlantConfig.PLANT_NAME,
        "dc_capacity_mwp": dc_mwp,
        "ac_capacity_mw": ac_mw,
        "n_intervals": n_intervals,
        "total_energy_mwh": round(float(total_energy), 3),
        "total_clipping_loss_mwh": round(float(total_clip), 3),
        "peak_grid_mw": round(float(peak_grid), 3),
        "peak_dc_mw": round(float(peak_dc), 3),
        "start_time": df_res['Timestamp'].iloc[0],
        "end_time": df_res['End_Timestamp'].iloc[-1],
        "total_15min_intervals": len(df_res)
    }
    
    return df_res, kpis


def generate_synthetic_1min_data(
    start_date: str = "2026-08-27",
    num_days: int = 1,
    weather_type: str = "Nắng đẹp (Clear Sky)"
) -> pd.DataFrame:
    """
    Tạo dữ liệu bức xạ chu kỳ 1 phút thực tế của Nhà máy ĐMT Mỹ Hiệp
    """
    timestamps = []
    irradiances = []
    temperatures = []
    pv_temperatures = []
    wind_speeds = []
    
    base_date = datetime.strptime(start_date, "%Y-%m-%d")
    
    for day in range(num_days):
        current_date = base_date + timedelta(days=day)
        
        for minute_idx in range(1440):
            ts = current_date + timedelta(minutes=minute_idx)
            timestamps.append(ts)
            
            hour_float = minute_idx / 60.0
            sunrise = 5.75
            sunset = 18.25
            day_length = sunset - sunrise
            
            if sunrise <= hour_float <= sunset:
                zenith_factor = np.sin(np.pi * (hour_float - sunrise) / day_length)
                clear_sky_irr = 1050.0 * (zenith_factor ** 1.15)
                
                np.random.seed(day * 1000 + minute_idx)
                if weather_type == "Nắng đẹp (Clear Sky)":
                    noise = np.random.normal(0, 15.0)
                    irr = max(0.0, clear_sky_irr + noise)
                elif weather_type == "Có mây thay đổi (Partly Cloudy)":
                    cloud_dip = 1.0 - 0.45 * np.sin(hour_float * 3.5) ** 2 if 9.0 <= hour_float <= 15.0 else 1.0
                    noise = np.random.normal(0, 35.0)
                    irr = max(0.0, clear_sky_irr * cloud_dip + noise)
                else:
                    irr = clear_sky_irr * 0.35 + np.random.normal(0, 20.0)
                    irr = max(0.0, irr)
                    
                temp_phase = np.sin(np.pi * (hour_float - 7.0) / 14.0) if 7.0 <= hour_float <= 21.0 else 0.0
                amb_temp = 24.5 + 10.5 * max(0.0, temp_phase) + np.random.normal(0, 0.2)
                pv_temp = amb_temp + (25.0 / 800.0) * irr + np.random.normal(0, 0.5)
                wind = 3.5 + np.random.normal(0, 1.0)
            else:
                irr = 0.0
                amb_temp = 24.0 + np.random.normal(0, 0.2)
                pv_temp = amb_temp
                wind = 2.0 + np.random.normal(0, 0.5)
                
            irradiances.append(round(irr, 1))
            temperatures.append(round(amb_temp, 1))
            pv_temperatures.append(round(pv_temp, 1))
            wind_speeds.append(round(max(0.0, wind), 1))
            
    df_synthetic = pd.DataFrame({
        'Thời gian': timestamps,
        'Bức xạ (W/m2)': irradiances,
        'Nhiệt độ môi trường (°C)': temperatures,
        'Nhiệt độ tấm pin (°C)': pv_temperatures,
        'Tốc độ gió (m/s)': wind_speeds
    })
    
    return df_synthetic


def generate_scada_txt_sample_content() -> str:
    """
    Tạo nội dung mẫu dạng file TXT trạm SCADA Thời Tiết Mỹ Hiệp
    """
    lines = [
        "WEATHER STATION;PLANT;;;;STATION-02-;WEATHER STAT;ION;;;;;;;STATION-06-;WEATHER STAT;ION;;;;",
        "Parameter;PERFORMANCE;WIND DIRECTION;WIND SPEED;GHI-01 IRRADIANCE;GHI-02 IRRADIANCE;AIR PRESSURE;AIR TEMPERATURE;HUMIDITY;RAIN;PV TEMPERATURE;WIND DIRECTION;WIND SPEED;GHI-01 IRRADIANCE;GHI-02 IRRADIANCE;AIR PRESSURE;AIR TEMPERATURE;HUMIDITY;RAIN;PV TEMPERATURE;",
        ";(%);(deg);(m/s);(W/m2);(W/m2);(mBar);(oC);(%);(mm);(oC);(deg);(m/s);(W/m2);(W/m2);(mBar);(oC);(%);(mm);(oC);"
    ]
    
    base_date = datetime(2026, 8, 27, 0, 0)
    for m in range(1440):
        dt = base_date + timedelta(minutes=m)
        ts_str = dt.strftime("%d/%m/%y %H:%M")
        
        hr = m / 60.0
        if 5.75 <= hr <= 18.25:
            sin_fac = np.sin(np.pi * (hr - 5.75) / 12.5)
            irr1 = max(0.0, round(1020.0 * (sin_fac ** 1.15) + np.random.normal(0, 10.0), 3))
            irr2 = max(0.0, round(1015.0 * (sin_fac ** 1.15) + np.random.normal(0, 12.0), 3))
            irr3 = max(0.0, round(1025.0 * (sin_fac ** 1.15) + np.random.normal(0, 10.0), 3))
            irr4 = max(0.0, round(1018.0 * (sin_fac ** 1.15) + np.random.normal(0, 11.0), 3))
            
            air_t1 = round(26.0 + 8.5 * sin_fac + np.random.normal(0, 0.2), 3)
            air_t2 = round(25.9 + 8.6 * sin_fac + np.random.normal(0, 0.2), 3)
            
            pv_t1 = round(air_t1 + (25.0 / 800.0) * irr1, 3)
            pv_t2 = round(air_t2 + (25.0 / 800.0) * irr3, 3)
            
            w_spd1 = round(max(0.5, 4.5 + np.random.normal(0, 1.0)), 3)
            w_spd2 = round(max(0.5, 4.2 + np.random.normal(0, 0.8)), 3)
        else:
            irr1 = round(np.random.uniform(-0.05, 0.05), 3)
            irr2 = round(np.random.uniform(-0.05, 0.05), 3)
            irr3 = round(np.random.uniform(-0.05, 0.05), 3)
            irr4 = round(np.random.uniform(-0.05, 0.05), 3)
            air_t1 = round(25.5 + np.random.normal(0, 0.1), 3)
            air_t2 = round(25.4 + np.random.normal(0, 0.1), 3)
            pv_t1 = air_t1
            pv_t2 = air_t2
            w_spd1 = round(max(0.2, 2.5 + np.random.normal(0, 0.5)), 3)
            w_spd2 = round(max(0.2, 2.3 + np.random.normal(0, 0.5)), 3)
            
        row_str = f"{ts_str};0.000;0.000;{w_spd1};{irr1};{irr2};1076.410;{air_t1};70.324;0.000;{pv_t1};263.528;{w_spd2};{irr3};{irr4};1076.410;{air_t2};70.188;0.000;{pv_t2};"
        lines.append(row_str)
        
    return "\n".join(lines)


def generate_scada_power_sample_content(base_date_str: str = "2026-08-27") -> str:
    """
    Tạo nội dung mẫu file SCADA Công Suất Điện Lực Mỹ Hiệp (110kV / 22kV / 7 Trạm Inverter)
    """
    lines = [
        "SOLAR;110KV;110KV;110KV;110KV;110KV;22KV;22KV;22KV;22KV;22KV;STATION-01;STATION-01;STATION-01;STATION-01;STATION-02;STATION-02;STATION-02;STATION-02;STATION-03;STATION-03;STATION-03;STATION-03;STATION-04;STATION-04;STATION-04;STATION-04;STATION-05;STATION-05;STATION-05;STATION-05;STATION-06;STATION-06;STATION-06;STATION-06;STATION-07;STATION-07;STATION-07;STATION-07;",
        "Parameter;P(MW);Q(MVAr);PF;U(kV);F(Hz);P(MW);Q(MVAr);PF;U(kV);F(Hz);I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;I(A);P(MW);Q(MVAr);Cos;"
    ]
    
    base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
    
    for m in range(1440):
        dt = base_date + timedelta(minutes=m)
        ts_str = dt.strftime("%d/%m/%y %H:%M")
        
        hr = m / 60.0
        u_110 = round(117.5 + np.random.normal(0, 0.4), 3)
        f_hz = round(50.0 + np.random.normal(0, 0.04), 3)
        u_22 = round(22.1 + np.random.normal(0, 0.05), 3)
        
        if 5.75 <= hr <= 18.25:
            sin_fac = np.sin(np.pi * (hr - 5.75) / 12.5)
            # Công suất đỉnh thực tế ~39.2 MW (có thể bị mây nhẹ)
            cloud_noise = np.random.normal(0, 0.8)
            p_tot_raw = max(0.0, 41.5 * (sin_fac ** 1.18) + cloud_noise)
            p_110 = min(39.475, p_tot_raw * 0.985) # Cắt trần Inverter & tổn hao MBA
            q_110 = round(p_110 * 0.05 + np.random.normal(0, 0.1), 3)
            pf_110 = round(0.995 + np.random.normal(0, 0.003), 3) if p_110 > 1.0 else 0.0
            
            p_22 = round(p_110 / 0.988, 3)
            q_22 = q_110
            
            # Chia đều cho 7 trạm Inverter (STATION-01..07)
            st_p = round(p_22 / 7.0, 3)
            st_q = round(q_22 / 7.0, 3)
            st_i = round((st_p * 1000.0) / (np.sqrt(3) * 0.8), 1) if st_p > 0.01 else 0.0
            st_cos = 0.998
        else:
            p_110 = 0.0
            q_110 = 0.0
            pf_110 = 0.0
            p_22 = 0.0
            q_22 = 0.0
            st_p = 0.0
            st_q = 0.0
            st_i = 0.0
            st_cos = 0.0
            
        p_110_s = f"{p_110:.3f}"
        q_110_s = f"{q_110:.3f}"
        pf_110_s = f"{pf_110:.3f}"
        p_22_s = f"{p_22:.3f}"
        q_22_s = f"{q_22:.3f}"
        
        st_parts = []
        for _ in range(7):
            st_parts.append(f"{st_i:.3f};{st_p:.3f};{st_q:.3f};{st_cos:.3f}")
            
        st_str = ";".join(st_parts)
        row_str = f"{ts_str};{p_110_s};{q_110_s};{pf_110_s};{u_110:.3f};{f_hz:.3f};{p_22_s};{q_22_s};{pf_110_s};{u_22:.3f};{f_hz:.3f};{st_str};"
        lines.append(row_str)
        
    return "\n".join(lines)


def recalculate_15min_forecast_kpis(df_15min: pd.DataFrame, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Tính toán lại toàn bộ chỉ số KPI tổng thể từ bảng 96 chu kỳ 15 phút
    """
    dc_cap = params.get('dc_capacity_mwp', MyHiepSolarPlantConfig.DC_CAPACITY_MWP) if params else MyHiepSolarPlantConfig.DC_CAPACITY_MWP
    ac_cap = params.get('ac_capacity_mw', MyHiepSolarPlantConfig.AC_CAPACITY_MW) if params else MyHiepSolarPlantConfig.AC_CAPACITY_MW

    total_energy_mwh = float(df_15min['Energy_Grid_MWh'].sum())
    peak_grid_mw = float(df_15min['P_Grid_Avg_MW'].max()) if len(df_15min) > 0 else 0.0
    peak_dc_mw = float(df_15min['P_DC_Avg_MW'].max()) if 'P_DC_Avg_MW' in df_15min else peak_grid_mw
    max_irr = float(df_15min['Irradiance_Avg_Wm2'].max()) if 'Irradiance_Avg_Wm2' in df_15min else 0.0

    clipping_loss_mwh = float(df_15min['Clipping_Loss_MWh'].sum()) if 'Clipping_Loss_MWh' in df_15min else 0.0
    total_unclipped_mwh = total_energy_mwh + clipping_loss_mwh
    clipping_loss_ratio = (clipping_loss_mwh / total_unclipped_mwh * 100.0) if total_unclipped_mwh > 0 else 0.0

    # Bức xạ tổng tích lũy (kWh/m2) = sum(W/m2 * 0.25h) / 1000
    total_irr_kwh_m2 = (float(df_15min['Irradiance_Avg_Wm2'].sum()) * 0.25 / 1000.0) if 'Irradiance_Avg_Wm2' in df_15min else 0.0
    ideal_energy_mwh = total_irr_kwh_m2 * dc_cap
    pr_pct = (total_energy_mwh / ideal_energy_mwh * 100.0) if ideal_energy_mwh > 0 else 82.5

    start_ts = pd.to_datetime(df_15min['Timestamp'].min()) if 'Timestamp' in df_15min and len(df_15min) > 0 else datetime.now()
    end_ts = pd.to_datetime(df_15min['Timestamp'].max()) if 'Timestamp' in df_15min and len(df_15min) > 0 else datetime.now()

    return {
        'total_energy_mwh': round(total_energy_mwh, 3),
        'peak_grid_mw': round(peak_grid_mw, 3),
        'peak_dc_mw': round(peak_dc_mw, 3),
        'max_irradiance_wm2': round(max_irr, 1),
        'total_clipping_loss_mwh': round(clipping_loss_mwh, 4),
        'clipping_loss_ratio_pct': round(clipping_loss_ratio, 2),
        'performance_ratio_pct': round(min(98.0, max(50.0, pr_pct)), 1),
        'total_intervals': len(df_15min),
        'start_time': start_ts,
        'end_time': end_ts,
        'plant_name': MyHiepSolarPlantConfig.PLANT_NAME,
        'dc_capacity_mwp': dc_cap,
        'ac_capacity_mw': ac_cap
    }


def process_custom_pw_dataframe(
    df_input: pd.DataFrame,
    base_df_15min: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None,
    recalculate_p_from_w: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Xử lý bảng dữ liệu P & W tùy chỉnh được nạp từ file Excel/CSV hoặc chỉnh sửa trực tiếp trên giao diện
    """
    df_res = base_df_15min.copy()
    n_rows = min(len(df_input), len(df_res))
    
    # 1. Tìm cột Bức xạ W
    w_col = None
    for c in df_input.columns:
        c_up = str(c).upper()
        if any(k in c_up for k in ['W(W/M2)', 'BUC_XA', 'IRRADIANCE', 'GHI', 'RADIATION', 'W_WM2', 'W (W/M2)']) or c_up == 'W':
            w_col = c
            break
            
    # 2. Tìm cột Công suất P
    p_col = None
    for c in df_input.columns:
        c_up = str(c).upper()
        if any(k in c_up for k in ['P(MW)', 'CONG_SUAT', 'P_GRID', 'P_MW', 'ACTIVE_POWER', 'P (MW)']) or c_up == 'P':
            p_col = c
            break

    # 3. Tìm cột Nhiệt độ Cell
    t_col = None
    for c in df_input.columns:
        c_up = str(c).upper()
        if any(k in c_up for k in ['T_CELL', 'PV_TEMP', 'CELL_TEMP', 'NHIET_DO', 'TEMP', 'NHIET_DO_CELL']):
            t_col = c
            break

    ac_limit = params.get('ac_capacity_mw', MyHiepSolarPlantConfig.AC_CAPACITY_MW) if params else MyHiepSolarPlantConfig.AC_CAPACITY_MW

    # Cập nhật Bức xạ W
    if w_col is not None:
        w_vals = pd.to_numeric(df_input[w_col].iloc[:n_rows], errors='coerce').fillna(0.0).clip(lower=0.0)
        df_res.loc[:n_rows-1, 'Irradiance_Avg_Wm2'] = w_vals.values
        df_res.loc[:n_rows-1, 'Irradiance_Max_Wm2'] = (w_vals * 1.03).values

    # Cập nhật Nhiệt độ T
    if t_col is not None:
        t_vals = pd.to_numeric(df_input[t_col].iloc[:n_rows], errors='coerce').fillna(25.0).clip(lower=0.0, upper=85.0)
        df_res.loc[:n_rows-1, 'Cell_Temp_Avg_C'] = t_vals.values

    # Tính toán / Cập nhật Công suất P
    if recalculate_p_from_w or p_col is None:
        # Tính toán lại P từ W qua mô hình pin Sharp NU-440
        w_series = df_res['Irradiance_Avg_Wm2']
        t_series = df_res.get('Cell_Temp_Avg_C', pd.Series([45.0] * len(df_res)))
        
        p_dc_list = []
        p_grid_list = []
        clip_list = []
        
        for w, t in zip(w_series, t_series):
            calc_out = calculate_solar_output(float(w), float(t), params=params)
            p_dc_list.append(calc_out['p_dc_mw'])
            p_grid_list.append(calc_out['p_grid_mw'])
            clip_list.append(calc_out['clipping_loss_mw'])
            
        df_res['P_DC_Avg_MW'] = p_dc_list
        df_res['P_AC_Inv_Avg_MW'] = [min(ac_limit, p) for p in p_dc_list]
        df_res['P_Grid_Avg_MW'] = p_grid_list
        df_res['Energy_Grid_MWh'] = [round(p * 0.25, 4) for p in p_grid_list]
        df_res['Clipping_Loss_MWh'] = [round(c * 0.25, 4) for c in clip_list]
    else:
        # Sử dụng trực tiếp giá trị P nhập vào
        p_vals = pd.to_numeric(df_input[p_col].iloc[:n_rows], errors='coerce').fillna(0.0).clip(lower=0.0)
        p_grid_capped = [round(min(ac_limit, float(p)), 3) for p in p_vals.values]
        p_dc_est = [round(p / 0.965, 3) for p in p_vals.values]
        clipping_est = [round(max(0.0, float(p) - ac_limit), 3) for p in p_vals.values]
        
        df_res.loc[:n_rows-1, 'P_Grid_Avg_MW'] = p_grid_capped
        df_res.loc[:n_rows-1, 'P_DC_Avg_MW'] = p_dc_est
        df_res.loc[:n_rows-1, 'P_AC_Inv_Avg_MW'] = p_grid_capped
        df_res.loc[:n_rows-1, 'Energy_Grid_MWh'] = [round(p * 0.25, 4) for p in p_grid_capped]
        df_res.loc[:n_rows-1, 'Clipping_Loss_MWh'] = [round(c * 0.25, 4) for c in clipping_est]

    kpi_updated = recalculate_15min_forecast_kpis(df_res, params=params)
    return df_res, kpi_updated


def process_any_external_scada_or_pw_file(
    file_bytes_or_content: Union[str, bytes],
    filename: str,
    base_df_15min: pd.DataFrame,
    params: Optional[Dict[str, Any]] = None,
    recalculate_p_from_w: bool = False
) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
    """
    Xử lý mọi loại file nạp từ bên ngoài:
    1. File SCADA Thời Tiết thô (.txt, .dat, .csv chứa GHI/Bức xạ, Nhiệt độ cell 1 phút hoặc 15 phút)
    2. File SCADA Công Suất thô (.txt, .dat, .csv chứa P 110kV, Q, U, F 1 phút hoặc 15 phút)
    3. File Bảng tính Excel / CSV chứa cột P và W (96 chu kỳ)
    """
    parsed_df, meta = detect_and_parse_input_data(file_bytes_or_content)
    fmt = meta.get('format', '')
    
    # 1. Kịch bản File SCADA Thời Tiết (W.txt, DL.txt, Solar Radiation Log)
    if 'SCADA_WEATHER' in fmt or ('GHI' in parsed_df.columns and len(parsed_df) > 90):
        _, df_15min_f, kpi_f = process_1min_to_15min_forecast(parsed_df, params=params)
        msg = f"Đã nhận diện file SCADA Thời Tiết ({len(parsed_df)} dòng dữ liệu -> Tổng hợp 96 chu kỳ)"
        return df_15min_f, kpi_f, msg
        
    # 2. Kịch bản File SCADA Công Suất Đo Đếm Điện Lực (P.txt, D.txt, 110kV Feeder Log)
    elif 'SCADA_POWER' in fmt or 'P_Grid_Actual_MW' in parsed_df.columns:
        df_act_15 = process_actual_power_1min_to_15min(parsed_df)
        df_res = base_df_15min.copy()
        
        n_rows = min(len(df_act_15), len(df_res))
        df_res.loc[:n_rows-1, 'P_Grid_Avg_MW'] = df_act_15['P_Grid_Actual_Avg_MW'].iloc[:n_rows].values
        df_res.loc[:n_rows-1, 'P_Grid_Max_MW'] = df_act_15['P_Grid_Actual_Max_MW'].iloc[:n_rows].values
        df_res.loc[:n_rows-1, 'Energy_Grid_MWh'] = df_act_15['Energy_Actual_MWh'].iloc[:n_rows].values
        df_res.loc[:n_rows-1, 'P_DC_Avg_MW'] = (df_act_15['P_Grid_Actual_Avg_MW'].iloc[:n_rows] / 0.965).round(3).values
        df_res.loc[:n_rows-1, 'P_AC_Inv_Avg_MW'] = df_act_15['P_Grid_Actual_Avg_MW'].iloc[:n_rows].values
        
        kpi_updated = recalculate_15min_forecast_kpis(df_res, params=params)
        msg = f"Đã nhận diện file SCADA Công Suất ({len(parsed_df)} dòng đo đếm -> 96 chu kỳ)"
        return df_res, kpi_updated, msg
        
    # 3. Kịch bản File Bảng Tính 96 Chu Kỳ (Excel / CSV)
    else:
        df_res, kpi_updated = process_custom_pw_dataframe(
            parsed_df, 
            base_df_15min, 
            params=params, 
            recalculate_p_from_w=recalculate_p_from_w
        )
        msg = f"Đã nhận diện bảng dữ liệu 96 chu kỳ ({len(parsed_df)} hàng)"
        return df_res, kpi_updated, msg


