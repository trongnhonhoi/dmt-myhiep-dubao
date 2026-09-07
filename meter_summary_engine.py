r"""
HỆ THỐNG TỔNG HỢP CHỈ SỐ CÔNG TƠ & BIỂU GIÁ ĐIỆN NĂNG (EVN / A0 / A3)
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - ĐƯỜNG DẪN: \\192.168.1.231\csv
"""

import os
import re
import io
import time
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional, Any

DEFAULT_METER_PATH = r'\\192.168.1.231\csv'
RAW_METER_CODES = ['6101', '6301', '6302', '6303']
RAW_TO_DISPLAY_CODE = {
    '6101': '171C',
    '6301': '431',
    '6302': '171 DP1',
    '6303': '171 DP2'
}
DEFAULT_METERS = ['171C', '431', '171 DP1', '171 DP2']

METER_CONFIG = {
    '171C': {
        'raw_code': '6101',
        'name': 'Công Tơ Đo Đếm Ranh Giới 110kV (Chính)',
        'location': 'Ngăn Lộ 110kV / Xuất Tuyến 171',
        'voltage': '110 kV',
        'type': 'Chính 110kV',
        'color': '#0284C7'
    },
    '431': {
        'raw_code': '6301',
        'name': 'Công Tơ Đo Đếm Đầu Cực MBA T1 22kV (Chính)',
        'location': 'Phía 22kV Máy Biến Áp T1 / Ngăn 431',
        'voltage': '22 kV',
        'type': 'Chính 22kV (Ngăn 431)',
        'color': '#10B981'
    },
    '171 DP1': {
        'raw_code': '6302',
        'name': 'Công Tơ Đo Đếm Đối Chứng 110kV (Dự Phòng 1)',
        'location': 'Phía 110kV TBA 220kV Phù Mỹ (Dự Phòng 1)',
        'voltage': '110 kV',
        'type': 'Dự Phòng 1 (TBA 220kV Phù Mỹ)',
        'color': '#F59E0B'
    },
    '171 DP2': {
        'raw_code': '6303',
        'name': 'Công Tơ Đo Đếm Đối Chứng 110kV (Dự Phòng 2)',
        'location': 'Phía 110kV Máy Biến Áp T1 NMĐT Mỹ Hiệp (Dự Phòng 2)',
        'voltage': '110 kV',
        'type': 'Dự Phòng 2 (TBA Mỹ Hiệp)',
        'color': '#8B5CF6'
    }
}


def get_interval_tariff(interval_idx: int, is_sunday: bool) -> str:
    """
    Xác định biểu giá EVN (3 giá) cho 48 chu kỳ 30 phút (0 đến 47):
    - T3 (Thấp điểm): 22:00 - 04:00 sáng hôm sau (Chu kỳ 0..7 và 44..47)
    - T2 (Cao điểm): 09:30 - 11:30 (Chu kỳ 19..22) và 17:00 - 20:00 (Chu kỳ 34..39) (Từ Thứ 2 đến Thứ 7)
    - T1 (Bình thường): Các khung giờ còn lại và toàn bộ ngày Chủ nhật (04:00 - 22:00)
    """
    if 0 <= interval_idx <= 7 or 44 <= interval_idx <= 47:
        return 'T3'
    if is_sunday:
        return 'T1'
    if (19 <= interval_idx <= 22) or (34 <= interval_idx <= 39):
        return 'T2'
    return 'T1'


def parse_single_meter_csv(filepath: str) -> Optional[Dict[str, Any]]:
    """Phân tích 1 file CSV công tơ đo đếm hàng ngày (48 chu kỳ 30 phút)"""
    fname = os.path.basename(filepath)
    m = re.match(r'^(\d{2})(\d{2})(\w{4})\.CSV$', fname, re.IGNORECASE)
    if not m:
        return None
    dd, mm, raw_m_code = m.groups()
    if raw_m_code not in RAW_METER_CODES:
        return None

    m_code = RAW_TO_DISPLAY_CODE.get(raw_m_code, raw_m_code)

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [l.strip() for l in f if l.strip()]
    except Exception:
        return None

    if not lines:
        return None

    raw_date_str = ""
    kwh_giao_arr = np.zeros(48, dtype=np.float64)
    kwh_nhan_arr = np.zeros(48, dtype=np.float64)
    kvarh_giao_arr = np.zeros(48, dtype=np.float64)
    kvarh_nhan_arr = np.zeros(48, dtype=np.float64)

    for l in lines:
        parts = l.split(',')
        if len(parts) >= 3:
            raw_date_str = parts[0].strip()
            metric = parts[1].strip()
            vals = []
            for x in parts[2:50]:
                try:
                    vals.append(float(x))
                except Exception:
                    vals.append(0.0)
            while len(vals) < 48:
                vals.append(0.0)
            vals = vals[:48]

            if 'KwhGiao' in metric:
                kwh_giao_arr = np.array(vals, dtype=np.float64)
            elif 'KwhNhan' in metric:
                kwh_nhan_arr = np.array(vals, dtype=np.float64)
            elif 'KvarhGiao' in metric:
                kvarh_giao_arr = np.array(vals, dtype=np.float64)
            elif 'KvarhNhan' in metric:
                kvarh_nhan_arr = np.array(vals, dtype=np.float64)

    dt = None
    if raw_date_str:
        try:
            p_dt = raw_date_str.replace('/', '-').split('-')
            d_i, m_i, y_i = int(p_dt[0]), int(p_dt[1]), int(p_dt[2])
            if y_i < 100: y_i += 2000
            dt = datetime(y_i, m_i, d_i)
        except Exception:
            pass
    if dt is None:
        try:
            dt = datetime(2026, int(mm), int(dd))
        except Exception:
            return None

    is_sun = (dt.weekday() == 6)

    t1_giao, t2_giao, t3_giao = 0.0, 0.0, 0.0
    t1_nhan, t2_nhan, t3_nhan = 0.0, 0.0, 0.0

    for idx in range(48):
        tar = get_interval_tariff(idx, is_sun)
        if tar == 'T1':
            t1_giao += kwh_giao_arr[idx]
            t1_nhan += kwh_nhan_arr[idx]
        elif tar == 'T2':
            t2_giao += kwh_giao_arr[idx]
            t2_nhan += kwh_nhan_arr[idx]
        elif tar == 'T3':
            t3_giao += kwh_giao_arr[idx]
            t3_nhan += kwh_nhan_arr[idx]

    tot_kwh_giao = float(kwh_giao_arr.sum())
    tot_kwh_nhan = float(kwh_nhan_arr.sum())
    tot_kvarh_giao = float(kvarh_giao_arr.sum())
    tot_kvarh_nhan = float(kvarh_nhan_arr.sum())

    p_max_kw = float(kwh_giao_arr.max() * 2.0)
    p_max_idx = int(kwh_giao_arr.argmax())
    p_max_h = p_max_idx // 2
    p_max_m = (p_max_idx % 2) * 30
    p_max_time = f"{p_max_h:02d}:{p_max_m:02d}"

    s_va = np.sqrt(tot_kwh_giao**2 + (tot_kvarh_giao - tot_kvarh_nhan)**2)
    cos_phi = (tot_kwh_giao / s_va) if s_va > 0 else 1.0

    m_info = METER_CONFIG.get(m_code, {})

    return {
        'Date': dt,
        'Date_Str': dt.strftime('%d/%m/%Y'),
        'Year': dt.year,
        'Month': dt.month,
        'Month_Str': dt.strftime('Tháng %m/%Y'),
        'Day': dt.day,
        'Meter_Code': m_code,
        'Raw_Code': raw_m_code,
        'Meter_Name': m_info.get('name', f'Công tơ {m_code}'),
        'Location': m_info.get('location', ''),
        'Voltage': m_info.get('voltage', ''),
        'Meter_Type': m_info.get('type', ''),
        'kWh_Giao': round(tot_kwh_giao, 2),
        'kWh_Nhan': round(tot_kwh_nhan, 2),
        'kWh_Net': round(tot_kwh_giao - tot_kwh_nhan, 2),
        'MWh_Giao': round(tot_kwh_giao / 1000.0, 3),
        'MWh_Nhan': round(tot_kwh_nhan / 1000.0, 3),
        'MWh_Net': round((tot_kwh_giao - tot_kwh_nhan) / 1000.0, 3),
        'T1_kWh_Giao': round(t1_giao, 2),
        'T2_kWh_Giao': round(t2_giao, 2),
        'T3_kWh_Giao': round(t3_giao, 2),
        'T1_MWh_Giao': round(t1_giao / 1000.0, 3),
        'T2_MWh_Giao': round(t2_giao / 1000.0, 3),
        'T3_MWh_Giao': round(t3_giao / 1000.0, 3),
        'T1_kWh_Nhan': round(t1_nhan, 2),
        'T2_kWh_Nhan': round(t2_nhan, 2),
        'T3_kWh_Nhan': round(t3_nhan, 2),
        'kVARh_Giao': round(tot_kvarh_giao, 2),
        'kVARh_Nhan': round(tot_kvarh_nhan, 2),
        'Pmax_kW': round(p_max_kw, 2),
        'Pmax_MW': round(p_max_kw / 1000.0, 3),
        'Pmax_Time': p_max_time,
        'Cos_Phi': round(cos_phi, 4),
        'Profile_48_kWh_Giao': kwh_giao_arr,
        'Profile_48_kWh_Nhan': kwh_nhan_arr,
        'File_Path': filepath
    }


class MeterDataManager:
    """Quản lý tải và tổng hợp dữ liệu công tơ đo đếm với bộ nhớ đệm đa luồng tốc độ cao"""
    def __init__(self, base_path: str = DEFAULT_METER_PATH):
        self.base_path = base_path
        self._cache_df: Optional[pd.DataFrame] = None
        self._last_scan_time: float = 0.0

    def check_connection(self) -> bool:
        try:
            return os.path.exists(self.base_path)
        except Exception:
            return False

    def load_all_meters(self, force_reload: bool = False) -> pd.DataFrame:
        if self._cache_df is not None and not force_reload:
            return self._cache_df

        if not self.check_connection():
            return pd.DataFrame()

        # Quét danh sách file CSV nhanh bằng os.scandir
        file_paths = []
        try:
            with os.scandir(self.base_path) as entries:
                for entry in entries:
                    if entry.is_file() and entry.name.upper().endswith('.CSV'):
                        if any(m in entry.name for m in RAW_METER_CODES):
                            file_paths.append(entry.path)
        except Exception:
            return pd.DataFrame()

        if not file_paths:
            return pd.DataFrame()

        # Đọc song song 32 luồng để nạp toàn bộ 1000+ file chỉ trong 1-2 giây
        records = []
        with ThreadPoolExecutor(max_workers=32) as executor:
            results = executor.map(parse_single_meter_csv, file_paths)
            for res in results:
                if res is not None:
                    records.append(res)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df.sort_values(by=['Date', 'Meter_Code'], inplace=True)
        self._cache_df = df
        self._last_scan_time = time.time()
        return df

    def get_summary_kpis(self, df_filtered: pd.DataFrame) -> Dict[str, Any]:
        """Tính toán các chỉ số KPI điện năng tổng hợp"""
        if df_filtered.empty:
            return {}

        df_main = df_filtered[df_filtered['Meter_Code'] == '171C']
        if df_main.empty:
            df_main = df_filtered[df_filtered['Meter_Code'] == '431']
        if df_main.empty:
            df_main = df_filtered

        tot_giao_mwh = float(df_main['MWh_Giao'].sum())
        tot_nhan_mwh = float(df_main['MWh_Nhan'].sum())
        tot_net_mwh = float(df_main['MWh_Net'].sum())

        t1_giao_mwh = float(df_main['T1_MWh_Giao'].sum())
        t2_giao_mwh = float(df_main['T2_MWh_Giao'].sum())
        t3_giao_mwh = float(df_main['T3_MWh_Giao'].sum())

        p_max_mw = float(df_main['Pmax_MW'].max()) if not df_main.empty else 0.0
        avg_cos_phi = float(df_main['Cos_Phi'].mean()) if not df_main.empty else 1.0

        days_count = df_filtered['Date'].nunique()

        return {
            'days_count': days_count,
            'total_giao_mwh': round(tot_giao_mwh, 3),
            'total_nhan_mwh': round(tot_nhan_mwh, 3),
            'total_net_mwh': round(tot_net_mwh, 3),
            't1_giao_mwh': round(t1_giao_mwh, 3),
            't2_giao_mwh': round(t2_giao_mwh, 3),
            't3_giao_mwh': round(t3_giao_mwh, 3),
            't1_pct': round(t1_giao_mwh / tot_giao_mwh * 100.0, 1) if tot_giao_mwh > 0 else 0.0,
            't2_pct': round(t2_giao_mwh / tot_giao_mwh * 100.0, 1) if tot_giao_mwh > 0 else 0.0,
            't3_pct': round(t3_giao_mwh / tot_giao_mwh * 100.0, 1) if tot_giao_mwh > 0 else 0.0,
            'p_max_mw': round(p_max_mw, 3),
            'avg_daily_giao_mwh': round(tot_giao_mwh / max(1, days_count), 3),
            'avg_cos_phi': round(avg_cos_phi, 4)
        }

    def get_discrepancy_table(self, df_filtered: pd.DataFrame) -> pd.DataFrame:
        """Tính toán đối soát sai số % giữa 4 công tơ đo đếm theo ngày"""
        if df_filtered.empty:
            return pd.DataFrame()

        pivot_giao = df_filtered.pivot(index='Date_Str', columns='Meter_Code', values='kWh_Giao')
        if '171C' in pivot_giao.columns and '431' in pivot_giao.columns:
            pivot_giao['Delta_171C_431_kWh'] = pivot_giao['171C'] - pivot_giao['431']
            pivot_giao['Err_171C_431_Pct'] = ((pivot_giao['171C'] - pivot_giao['431']) / pivot_giao['171C'] * 100.0).round(3)
        if '431' in pivot_giao.columns and '171 DP1' in pivot_giao.columns:
            pivot_giao['Err_431_171DP1_Pct'] = ((pivot_giao['431'] - pivot_giao['171 DP1']) / pivot_giao['431'] * 100.0).round(3)
        if '431' in pivot_giao.columns and '171 DP2' in pivot_giao.columns:
            pivot_giao['Err_431_171DP2_Pct'] = ((pivot_giao['431'] - pivot_giao['171 DP2']) / pivot_giao['431'] * 100.0).round(3)
        if '171C' in pivot_giao.columns and '171 DP1' in pivot_giao.columns:
            pivot_giao['Err_171C_171DP1_Pct'] = ((pivot_giao['171C'] - pivot_giao['171 DP1']) / pivot_giao['171C'] * 100.0).round(3)
        if '171C' in pivot_giao.columns and '171 DP2' in pivot_giao.columns:
            pivot_giao['Err_171C_171DP2_Pct'] = ((pivot_giao['171C'] - pivot_giao['171 DP2']) / pivot_giao['171C'] * 100.0).round(3)
        return pivot_giao.reset_index()


def export_meter_report_to_excel_bytes(df_meters: pd.DataFrame, kpis: Dict[str, Any], date_label: str = "") -> bytes:
    """Xuất báo cáo tổng hợp chỉ số công tơ & biểu giá EVN ra file Excel (.xlsx)"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Tổng Hợp Hàng Ngày Toàn Bộ Công Tơ
        export_daily = df_meters[[
            'Date_Str', 'Meter_Code', 'Meter_Name', 'Location', 'Voltage',
            'kWh_Giao', 'kWh_Nhan', 'kWh_Net', 'MWh_Giao', 'MWh_Nhan', 'MWh_Net',
            'T1_kWh_Giao', 'T2_kWh_Giao', 'T3_kWh_Giao',
            'kVARh_Giao', 'kVARh_Nhan', 'Pmax_MW', 'Pmax_Time', 'Cos_Phi'
        ]].copy()
        export_daily.columns = [
            'Ngày', 'Mã Công Tơ', 'Tên Công Tơ', 'Vị Trí Đo Đếm', 'Cấp Điện Áp',
            'kWh Giao (Phát)', 'kWh Nhận (Tự Dùng)', 'kWh Thuần Net',
            'MWh Giao', 'MWh Nhận', 'MWh Thuần Net',
            'T1 Giao (kWh)', 'T2 Cao Điểm Giao (kWh)', 'T3 Thấp Điểm Giao (kWh)',
            'kVARh Giao', 'kVARh Nhận', 'Công Suất Đỉnh Pmax (MW)', 'Thời Điểm Pmax', 'Cos Phi'
        ]
        export_daily.to_excel(writer, sheet_name='Chi_Tiet_Hang_Ngay', index=False)

        # Sheet 2: Tổng Hợp Theo Tháng
        df_monthly = df_meters.groupby(['Month_Str', 'Meter_Code', 'Meter_Name']).agg({
            'MWh_Giao': 'sum',
            'MWh_Nhan': 'sum',
            'MWh_Net': 'sum',
            'T1_MWh_Giao': 'sum',
            'T2_MWh_Giao': 'sum',
            'T3_MWh_Giao': 'sum',
            'Pmax_MW': 'max',
            'Cos_Phi': 'mean'
        }).reset_index()
        df_monthly.columns = [
            'Tháng', 'Mã Công Tơ', 'Tên Công Tơ',
            'Tổng MWh Giao', 'Tổng MWh Nhận', 'Tổng MWh Net',
            'T1 Bình Thường (MWh)', 'T2 Cao Điểm (MWh)', 'T3 Thấp Điểm (MWh)',
            'Pmax Tháng (MW)', 'Cos Phi Trung Bình'
        ]
        df_monthly.to_excel(writer, sheet_name='Tong_Hop_Thang', index=False)

        # Sheet 3: Bảng Chỉ Số KPIs
        kpi_rows = [
            {'Chỉ Số': 'Phạm Vi Thời Gian Báo Cáo', 'Giá Trị': date_label},
            {'Chỉ Số': 'Số Ngày Đo Đếm Tổng Hợp', 'Giá Trị': kpis.get('days_count', 0)},
            {'Chỉ Số': 'Tổng Điện Năng Giao Lên Lưới (MWh)', 'Giá Trị': round(kpis.get('total_giao_mwh', 0.0), 3)},
            {'Chỉ Số': 'Tổng Điện Năng Nhận Tự Dùng (MWh)', 'Giá Trị': round(kpis.get('total_nhan_mwh', 0.0), 3)},
            {'Chỉ Số': 'Sản Lượng Điện Năng Thuần Net (MWh)', 'Giá Trị': round(kpis.get('total_net_mwh', 0.0), 3)},
            {'Chỉ Số': 'Sản Lượng Giờ Bình Thường T1 (MWh)', 'Giá Trị': round(kpis.get('t1_giao_mwh', 0.0), 3)},
            {'Chỉ Số': 'Sản Lượng Giờ Cao Điểm T2 (MWh)', 'Giá Trị': round(kpis.get('t2_giao_mwh', 0.0), 3)},
            {'Chỉ Số': 'Sản Lượng Giờ Thấp Điểm T3 (MWh)', 'Giá Trị': round(kpis.get('t3_giao_mwh', 0.0), 3)},
            {'Chỉ Số': 'Tỉ Lệ Phát Giờ Bình Thường T1 (%)', 'Giá Trị': f"{kpis.get('t1_pct', 0.0)}%"},
            {'Chỉ Số': 'Tỉ Lệ Phát Giờ Cao Điểm T2 (%)', 'Giá Trị': f"{kpis.get('t2_pct', 0.0)}%"},
            {'Chỉ Số': 'Công Suất Cực Đại Pmax (MW)', 'Giá Trị': round(kpis.get('p_max_mw', 0.0), 3)},
            {'Chỉ Số': 'Sản Lượng Phát Trung Bình Ngày (MWh/ngày)', 'Giá Trị': round(kpis.get('avg_daily_giao_mwh', 0.0), 3)},
            {'Chỉ Số': 'Hệ Số Công Suất Cos Phi Trung Bình', 'Giá Trị': round(kpis.get('avg_cos_phi', 1.0), 4)}
        ]
        pd.DataFrame(kpi_rows).to_excel(writer, sheet_name='Tong_Hop_KPIs', index=False)

    return output.getvalue()
