"""
MODULE PHÂN TÍCH CÔNG SUẤT BẤT THƯỜNG & CHẨN ĐOÁN INVERTER (S1 - S7)
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP (50MWp / 40.075MW) - 229 INVERTER
Xử lý dữ liệu S1.txt, S2.txt, S3.txt, S4.txt, S5.txt, S6.txt, S7.txt
Đa khung thời gian: D-1..D-7, W-1..W-4, M-1..M-3
"""

import os
import re
import io
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional

# Cấu hình danh mục 7 Trạm Inverter tại Nhà Máy ĐMT Mỹ Hiệp (Tổng cộng 229 Inverter thực tế)
STATION_CONFIG = {
    'S1': {'name': 'STATION-01', 'capacity_mw': 5.60, 'inverters': 35}, # Loại trừ INV-1-2-18 (không tồn tại)
    'S2': {'name': 'STATION-02', 'capacity_mw': 5.60, 'inverters': 35}, # Loại trừ INV-2-2-18 (không tồn tại)
    'S3': {'name': 'STATION-03', 'capacity_mw': 5.60, 'inverters': 35},
    'S4': {'name': 'STATION-04', 'capacity_mw': 5.60, 'inverters': 35}, # Loại trừ INV-4-1-18 (không tồn tại)
    'S5': {'name': 'STATION-05', 'capacity_mw': 5.60, 'inverters': 35}, # Loại trừ INV-5-1-18 (không tồn tại)
    'S6': {'name': 'STATION-06', 'capacity_mw': 5.76, 'inverters': 36},
    'S7': {'name': 'STATION-07', 'capacity_mw': 2.88, 'inverters': 18},
}

# Danh sách các Inverter không tồn tại trên thực tế tại ĐMT Mỹ Hiệp (Dummy SCADA placeholder slots)
EXCLUDED_INVERTERS = {
    'INV-5-1-18', 'INV-5.1.18', 'INV 5.1.18', 'INV5.1.18',
    'INV-4-1-18', 'INV-4.1.18', 'INV 4.1.18', 'INV4.1.18',
    'INV-1-2-18', 'INV-1.2.18', 'INV 1.2.18', 'INV1.2.18',
    'INV-2-2-18', 'INV-2.2.18', 'INV 2.2.18', 'INV2.2.18',
}

def is_excluded_inverter(inv_name: str) -> bool:
    """Kiểm tra Inverter có thuộc danh sách không tồn tại cần loại bỏ không (INV 5.1.18, 4.1.18, 1.2.18, 2.2.18)"""
    if not inv_name:
        return True
    cleaned = re.sub(r'[-_\.\s]+', '-', inv_name.strip().upper())
    
    target_excluded = {
        'INV-5-1-18',
        'INV-4-1-18',
        'INV-1-2-18',
        'INV-2-2-18',
    }
    if cleaned in target_excluded:
        return True
    
    if re.search(r'^INV[-_\.\s]*5[-_\.\s]*1[-_\.\s]*18$', inv_name.strip(), re.IGNORECASE):
        return True
    if re.search(r'^INV[-_\.\s]*4[-_\.\s]*1[-_\.\s]*18$', inv_name.strip(), re.IGNORECASE):
        return True
    if re.search(r'^INV[-_\.\s]*1[-_\.\s]*2[-_\.\s]*18$', inv_name.strip(), re.IGNORECASE):
        return True
    if re.search(r'^INV[-_\.\s]*2[-_\.\s]*2[-_\.\s]*18$', inv_name.strip(), re.IGNORECASE):
        return True
    return False

def decode_scada_bytes(raw_bytes: bytes) -> str:
    """Giải mã file SCADA S1..S7 hỗ trợ đa dạng định dạng (UTF-16, UTF-8-sig, latin1)"""
    if raw_bytes.startswith(b'\xff\xfe') or raw_bytes.startswith(b'\xfe\xff'):
        try:
            return raw_bytes.decode('utf-16')
        except Exception:
            pass
            
    for enc in ['utf-16', 'utf-16-le', 'utf-8-sig', 'utf-8', 'cp1252', 'latin1']:
        try:
            text = raw_bytes.decode(enc)
            if '\x00' not in text:
                return text
        except Exception:
            pass
            
    # Fallback strip nulls
    cleaned = raw_bytes.replace(b'\x00', b'')
    return cleaned.decode('latin1', errors='ignore')


def parse_station_fast(filepath_or_bytes: Any) -> Tuple[Optional[str], Optional[List[str]], Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """
    Phân tích tốc độ cao file Trạm Inverter (S1..S7)
    Trả về: (station_name, inv_names, energy_kwh_array, peak_kw_array, total_station_p_mw_profile)
    """
    if isinstance(filepath_or_bytes, str):
        if not os.path.exists(filepath_or_bytes):
            return None, None, None, None, None
        with open(filepath_or_bytes, 'rb') as f:
            raw = f.read()
    elif isinstance(filepath_or_bytes, (bytes, bytearray)):
        raw = filepath_or_bytes
    else:
        return None, None, None, None, None

    text = decode_scada_bytes(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return None, None, None, None, None

    h1 = lines[0].split(';')
    st_name = h1[0].strip()

    # Tìm các cột Inverter P(kW) - Tự động loại bỏ các Inverter không tồn tại
    inv_names = []
    inv_indices = []
    for i in range(3, len(h1), 2):
        if i < len(h1) and h1[i].strip():
            candidate_name = h1[i].strip()
            if not is_excluded_inverter(candidate_name):
                inv_names.append(candidate_name)
                inv_indices.append(i)

    data_rows = []
    tot_station_p = []

    for l in lines[2:]:
        parts = l.split(';')
        if len(parts) >= 3:
            try:
                tot_station_p.append(float(parts[1]) if parts[1] else 0.0)
            except Exception:
                tot_station_p.append(0.0)

            vals = []
            for idx in inv_indices:
                if idx < len(parts) and parts[idx]:
                    try:
                        vals.append(float(parts[idx]))
                    except Exception:
                        vals.append(0.0)
                else:
                    vals.append(0.0)
            data_rows.append(vals)

    if not data_rows:
        return st_name, inv_names, np.zeros(len(inv_names)), np.zeros(len(inv_names)), np.zeros(len(tot_station_p))

    arr = np.array(data_rows, dtype=np.float32)
    # Energy in kWh = sum(1-min kW) / 60
    energy_kwh = arr.sum(axis=0) / 60.0
    peaks_kw = arr.max(axis=0)
    tot_st_mw = np.array(tot_station_p, dtype=np.float32)

    return st_name, inv_names, energy_kwh, peaks_kw, tot_st_mw


def parse_station_full(filepath_or_bytes: Any) -> Tuple[Optional[str], Optional[pd.DataFrame], Optional[Dict[str, Any]]]:
    """Phân tích đầy đủ 1-minute profile khi người dùng cần xem biểu đồ chi tiết từng phút"""
    if isinstance(filepath_or_bytes, str):
        if not os.path.exists(filepath_or_bytes):
            return None, None, None
        with open(filepath_or_bytes, 'rb') as f:
            raw = f.read()
    elif isinstance(filepath_or_bytes, (bytes, bytearray)):
        raw = filepath_or_bytes
    else:
        return None, None, None

    text = decode_scada_bytes(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 3:
        return None, None, None

    h1 = lines[0].split(';')
    st_name = h1[0].strip()

    inv_cols = [(h1[i].strip(), i) for i in range(3, len(h1), 2) if i < len(h1) and h1[i].strip() and not is_excluded_inverter(h1[i].strip())]
    records = {inv[0]: [] for inv in inv_cols}
    timestamps = []
    tot_p_mw = []

    for l in lines[2:]:
        parts = [p.strip() for p in l.split(';')]
        if len(parts) < 3:
            continue
        timestamps.append(parts[0])
        try:
            tot_p_mw.append(float(parts[1]))
        except Exception:
            tot_p_mw.append(0.0)

        for inv_name, col_idx in inv_cols:
            if col_idx < len(parts):
                try:
                    records[inv_name].append(float(parts[col_idx]))
                except Exception:
                    records[inv_name].append(0.0)
            else:
                records[inv_name].append(0.0)

    df_inv = pd.DataFrame(records)
    df_inv['Timestamp'] = timestamps
    df_inv['Total_Station_P_MW'] = tot_p_mw

    meta = {
        'station_name': st_name,
        'inverter_count': len(inv_cols),
        'inverter_list': [inv[0] for inv in inv_cols],
        'total_rows': len(df_inv)
    }
    return st_name, df_inv, meta


# Bộ nhớ đệm toàn cục cho các ngày đã nạp
GLOBAL_DAILY_INVERTER_CACHE: Dict[str, Dict[str, Any]] = {}

def load_day_inverter_summary_fast(day_dir: str, date_str: str = "") -> Dict[str, Any]:
    """Tải và tính toán sản lượng 233 Inverter của 1 ngày với tốc độ cao (< 30ms)"""
    if day_dir in GLOBAL_DAILY_INVERTER_CACHE:
        return GLOBAL_DAILY_INVERTER_CACHE[day_dir]

    inverter_rows = []
    station_summaries = {}

    for s_idx in range(1, 8):
        s_tag = f"S{s_idx}"
        target_path = None
        for cand in [f"{s_tag}.txt", f"{s_tag}.TXT", f"0{s_tag}.txt", f"*{s_tag}*.txt"]:
            matches = glob.glob(os.path.join(day_dir, cand))
            if matches:
                target_path = matches[0]
                break

        if target_path and os.path.exists(target_path):
            st_name, inv_names, energy_arr, peaks_arr, tot_mw_prof = parse_station_fast(target_path)
            if inv_names and len(energy_arr) == len(inv_names):
                st_tot_e_mwh = float(energy_arr.sum() / 1000.0)
                st_peak_mw = float(peaks_arr.max() / 1000.0 * len(inv_names)) if len(inv_names) > 0 else 0.0
                st_med_kwh = float(np.median(energy_arr)) if len(energy_arr) > 0 else 0.0

                station_summaries[s_tag] = {
                    'station_name': st_name,
                    'inverter_count': len(inv_names),
                    'total_energy_mwh': st_tot_e_mwh,
                    'median_energy_kwh': st_med_kwh,
                    'file_path': target_path
                }

                for i, inv_id in enumerate(inv_names):
                    inverter_rows.append({
                        'Inverter_ID': inv_id,
                        'Station': st_name,
                        'Station_Tag': s_tag,
                        'Date': date_str,
                        'Energy_kWh': round(float(energy_arr[i]), 2),
                        'Peak_kW': round(float(peaks_arr[i]), 2),
                        'Station_Median_kWh': round(st_med_kwh, 2)
                    })

    if not inverter_rows:
        res = {'status': 'NO_DATA', 'inverter_table': pd.DataFrame(), 'alerts': [], 'kpis': {}, 'station_summaries': {}}
        GLOBAL_DAILY_INVERTER_CACHE[day_dir] = res
        return res

    df_day = pd.DataFrame(inverter_rows)
    plant_med_kwh = float(df_day['Energy_kWh'].median())

    alerts = []
    health_status = []
    ratio_st_list = []
    anomaly_type_list = []
    loss_kwh_list = []

    for idx, row in df_day.iterrows():
        st_med = row['Station_Median_kWh']
        e_val = row['Energy_kWh']
        ratio_st = (e_val / st_med * 100.0) if st_med > 0 else 0.0
        ratio_st_list.append(round(ratio_st, 1))

        loss_kwh = max(0.0, st_med - e_val)
        loss_kwh_list.append(round(loss_kwh, 2))

        # Phân loại bất thường
        if st_med > 50.0 and e_val < 5.0:
            status = 'CRITICAL'
            anom = '🔴 Mất Điện / Ngắt CB / Offline Hoàn Toàn'
            alerts.append({
                'level': 'CRITICAL',
                'inverter': row['Inverter_ID'],
                'station': row['Station'],
                'date': date_str,
                'message': f"Inverter {row['Inverter_ID']} ({row['Station']}) OFFLINE hoàn toàn (Sản lượng: {e_val:.1f} kWh vs TB trạm {st_med:.1f} kWh). Mất ~{loss_kwh:.1f} kWh.",
                'energy_kwh': e_val,
                'st_median_kwh': st_med,
                'loss_kwh': loss_kwh,
                'ratio_pct': ratio_st
            })
        elif ratio_st < 75.0:
            status = 'MAJOR'
            anom = '🟠 Suy Giảm Nặng / Đứt Chuỗi String DC'
            alerts.append({
                'level': 'MAJOR',
                'inverter': row['Inverter_ID'],
                'station': row['Station'],
                'date': date_str,
                'message': f"Inverter {row['Inverter_ID']} suy giảm {100-ratio_st:.1f}% công suất so với đồng cấp ({e_val:.1f} kWh vs {st_med:.1f} kWh). Cần kiểm tra chuỗi pin/cầu chì.",
                'energy_kwh': e_val,
                'st_median_kwh': st_med,
                'loss_kwh': loss_kwh,
                'ratio_pct': ratio_st
            })
        elif ratio_st < 90.0:
            status = 'MINOR'
            anom = '🟡 Suy Giảm Nhẹ / Quá Nhiệt Derating'
            alerts.append({
                'level': 'MINOR',
                'inverter': row['Inverter_ID'],
                'station': row['Station'],
                'date': date_str,
                'message': f"Inverter {row['Inverter_ID']} lệch {100-ratio_st:.1f}% (Đạt {e_val:.1f} kWh vs {st_med:.1f} kWh). Kiểm tra tản nhiệt/bụi bẩn.",
                'energy_kwh': e_val,
                'st_median_kwh': st_med,
                'loss_kwh': loss_kwh,
                'ratio_pct': ratio_st
            })
        else:
            status = 'NORMAL'
            anom = '🟢 Hoạt Động Bình Thường'

        health_status.append(status)
        anomaly_type_list.append(anom)

    df_day['Health_Status'] = health_status
    df_day['Ratio_Station_Pct'] = ratio_st_list
    df_day['Anomaly_Type'] = anomaly_type_list
    df_day['Est_Loss_kWh'] = loss_kwh_list

    # Sắp xếp theo mức tổn thất giảm dần
    df_day.sort_values(by=['Health_Status', 'Est_Loss_kWh'], ascending=[True, False], inplace=True)

    total_inv = len(df_day)
    count_critical = sum(1 for s in health_status if s == 'CRITICAL')
    count_major = sum(1 for s in health_status if s == 'MAJOR')
    count_minor = sum(1 for s in health_status if s == 'MINOR')
    count_normal = sum(1 for s in health_status if s == 'NORMAL')
    total_loss_kwh = sum(loss_kwh_list)
    total_plant_energy_mwh = sum(df_day['Energy_kWh']) / 1000.0

    kpis = {
        'date': date_str,
        'total_inverters': total_inv,
        'critical_count': count_critical,
        'major_count': count_major,
        'minor_count': count_minor,
        'normal_count': count_normal,
        'plant_median_energy_kwh': plant_med_kwh,
        'total_loss_kwh': total_loss_kwh,
        'total_loss_mwh': round(total_loss_kwh / 1000.0, 3),
        'total_energy_mwh': round(total_plant_energy_mwh, 2),
        'plant_availability_pct': round((count_normal + count_minor) / max(1, total_inv) * 100.0, 1)
    }

    # Tính toán tổn thất và số lỗi theo từng trạm
    for s_tag in station_summaries:
        st_inverters = df_day[df_day['Station_Tag'] == s_tag]
        st_loss_kwh = float(st_inverters['Est_Loss_kWh'].sum()) if not st_inverters.empty else 0.0
        station_summaries[s_tag]['total_loss_mwh'] = round(st_loss_kwh / 1000.0, 3)
        station_summaries[s_tag]['fault_count'] = int((st_inverters['Health_Status'] != 'NORMAL').sum()) if not st_inverters.empty else 0

    res = {
        'status': 'SUCCESS',
        'date_str': date_str,
        'day_dir': day_dir,
        'inverter_table': df_day,
        'alerts': alerts,
        'kpis': kpis,
        'station_summaries': station_summaries
    }

    GLOBAL_DAILY_INVERTER_CACHE[day_dir] = res
    return res


class InverterAnomalyManager:
    """
    Quản lý chẩn đoán toàn diện Inverter đa chu kỳ thời gian:
    - D-1, D-2, D-3, D-4, D-5, D-6, D-7
    - W-1, W-2, W-3, W-4
    - M-1, M-2, M-3
    """
    def __init__(self, harvester: Any):
        self.harvester = harvester
        self._cached_dates: List[Dict[str, Any]] = []

    def get_available_s_dates(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các ngày có file S1..S7 trong máy chủ SCADA"""
        if self._cached_dates:
            return self._cached_dates

        if not self.harvester.check_server_connection():
            return []

        all_day_dirs = []
        for root, dirs, files in os.walk(self.harvester.base_path):
            bname = os.path.basename(root)
            if re.match(r'^\d{1,2}\.\d{1,2}$', bname):
                s_files = [f for f in files if re.match(r'.*S[1-7].*\.txt$', f, re.IGNORECASE)]
                if s_files:
                    parts = root.replace('/', '\\').split('\\')
                    y = 2026
                    m = 8
                    for p in parts:
                        if re.match(r'^202\d$', p):
                            y = int(p)
                        elif 'THANG' in p.upper():
                            m_m = re.search(r'\d+', p)
                            if m_m:
                                m = int(m_m.group())
                    day_val = int(bname.split('.')[0])
                    try:
                        dt = datetime(y, m, day_val)
                        all_day_dirs.append({
                            'date': dt,
                            'date_str': dt.strftime('%d/%m/%Y'),
                            'path': root,
                            's_count': len(s_files),
                            'files': s_files
                        })
                    except Exception:
                        pass

        all_day_dirs.sort(key=lambda x: x['date'])
        self._cached_dates = all_day_dirs
        return all_day_dirs

    def resolve_timeframe_dates(self, timeframe_code: str) -> List[Dict[str, Any]]:
        """
        Xác định danh sách các ngày tương ứng với mã khung thời gian:
        D-1..D-7, W-1..W-4, M-1..M-3
        """
        avail = self.get_available_s_dates()
        if not avail:
            return []

        latest_entry = avail[-1]
        latest_date = latest_entry['date']

        # D-1 .. D-7
        if timeframe_code.startswith('D-'):
            try:
                d_offset = int(timeframe_code.split('-')[1])
                target_dt = latest_date - timedelta(days=d_offset - 1)
                match = [e for e in avail if e['date'].date() == target_dt.date()]
                return match if match else [avail[-min(d_offset, len(avail))]]
            except Exception:
                return [latest_entry]

        # W-1 .. W-4 (Mỗi tuần 7 ngày)
        elif timeframe_code.startswith('W-'):
            try:
                w_offset = int(timeframe_code.split('-')[1])
                end_idx = len(avail) - (w_offset - 1) * 7
                start_idx = max(0, end_idx - 7)
                return avail[start_idx:end_idx]
            except Exception:
                return avail[-7:]

        # M-1 .. M-3 (Tháng)
        elif timeframe_code.startswith('M-'):
            try:
                m_offset = int(timeframe_code.split('-')[1])
                cur_m = latest_date.month
                cur_y = latest_date.year

                total_m = cur_y * 12 + cur_m - (m_offset - 1)
                t_y = total_m // 12
                t_m = total_m % 12
                if t_m == 0:
                    t_m = 12
                    t_y -= 1

                match = [e for e in avail if e['date'].year == t_y and e['date'].month == t_m]
                if match:
                    return match
                else:
                    end_i = len(avail) - (m_offset - 1) * 30
                    start_i = max(0, end_i - 30)
                    return avail[start_i:end_i]
            except Exception:
                return avail[-30:]

        return [latest_entry]

    def analyze_timeframe(self, timeframe_code: str) -> Dict[str, Any]:
        """
        Thực hiện chẩn đoán toàn diện cho khung thời gian (D-1..D-7, W-1..W-4, M-1..M-3)
        """
        date_entries = self.resolve_timeframe_dates(timeframe_code)
        if not date_entries:
            return {'status': 'NO_DATA', 'timeframe': timeframe_code, 'inverter_table': pd.DataFrame(), 'alerts': [], 'kpis': {}}

        daily_results = []
        for entry in date_entries:
            res = load_day_inverter_summary_fast(entry['path'], entry['date_str'])
            if res['status'] == 'SUCCESS':
                daily_results.append(res)

        if not daily_results:
            return {'status': 'NO_DATA', 'timeframe': timeframe_code, 'inverter_table': pd.DataFrame(), 'alerts': [], 'kpis': {}}

        # Nếu là đơn ngày (D-1 .. D-7)
        if len(daily_results) == 1:
            res_single = daily_results[0]
            res_single['timeframe'] = timeframe_code
            res_single['num_days'] = 1
            res_single['date_range_str'] = res_single['kpis']['date']
            return res_single

        # Tổng hợp đa ngày (W-1..W-4, M-1..M-3)
        inv_cum_dict = {}
        all_alerts = []
        tot_loss_kwh = 0.0
        tot_energy_mwh = 0.0

        for res in daily_results:
            d_tab = res['inverter_table']
            all_alerts.extend(res['alerts'])
            tot_loss_kwh += res['kpis']['total_loss_kwh']
            tot_energy_mwh += res['kpis']['total_energy_mwh']

            for _, r in d_tab.iterrows():
                inv_id = r['Inverter_ID']
                if inv_id not in inv_cum_dict:
                    inv_cum_dict[inv_id] = {
                        'Inverter_ID': inv_id,
                        'Station': r['Station'],
                        'Station_Tag': r['Station_Tag'],
                        'Total_Energy_kWh': 0.0,
                        'Days_Count': 0,
                        'Critical_Days': 0,
                        'Major_Days': 0,
                        'Minor_Days': 0,
                        'Peak_kW_Max': 0.0,
                        'Total_Loss_kWh': 0.0
                    }
                inv_cum_dict[inv_id]['Total_Energy_kWh'] += r['Energy_kWh']
                inv_cum_dict[inv_id]['Days_Count'] += 1
                inv_cum_dict[inv_id]['Peak_kW_Max'] = max(inv_cum_dict[inv_id]['Peak_kW_Max'], r['Peak_kW'])
                inv_cum_dict[inv_id]['Total_Loss_kWh'] += r['Est_Loss_kWh']

                if r['Health_Status'] == 'CRITICAL':
                    inv_cum_dict[inv_id]['Critical_Days'] += 1
                elif r['Health_Status'] == 'MAJOR':
                    inv_cum_dict[inv_id]['Major_Days'] += 1
                elif r['Health_Status'] == 'MINOR':
                    inv_cum_dict[inv_id]['Minor_Days'] += 1

        df_multi = pd.DataFrame(list(inv_cum_dict.values()))
        df_multi['Avg_Daily_Energy_kWh'] = (df_multi['Total_Energy_kWh'] / df_multi['Days_Count']).round(2)

        plant_med_multi = float(df_multi['Avg_Daily_Energy_kWh'].median())
        station_med_multi = {}
        for s_tag, grp in df_multi.groupby('Station_Tag'):
            station_med_multi[s_tag] = float(grp['Avg_Daily_Energy_kWh'].median())

        overall_status = []
        overall_ratio = []
        overall_diag = []

        for idx, row in df_multi.iterrows():
            s_tag = row['Station_Tag']
            st_med = station_med_multi.get(s_tag, plant_med_multi)
            avg_e = row['Avg_Daily_Energy_kWh']
            ratio = (avg_e / st_med * 100.0) if st_med > 0 else 0.0
            overall_ratio.append(round(ratio, 1))

            crit_d = row['Critical_Days']
            maj_d = row['Major_Days']
            tot_d = row['Days_Count']

            if crit_d >= tot_d * 0.5 or (st_med > 50.0 and avg_e < 10.0):
                overall_status.append('CRITICAL')
                overall_diag.append(f'🔴 Offline liên tục ({crit_d}/{tot_d} ngày)')
            elif (crit_d + maj_d) >= tot_d * 0.4 or ratio < 75.0:
                overall_status.append('MAJOR')
                overall_diag.append(f'🟠 Suy giảm nghiêm trọng ({ratio:.1f}% TB trạm)')
            elif row['Minor_Days'] >= tot_d * 0.4 or ratio < 90.0:
                overall_status.append('MINOR')
                overall_diag.append(f'🟡 Lệch công suất ({ratio:.1f}% TB trạm)')
            else:
                overall_status.append('NORMAL')
                overall_diag.append('🟢 Hoạt động ổn định')

        df_multi['Health_Status'] = overall_status
        df_multi['Ratio_Station_Pct'] = overall_ratio
        df_multi['Anomaly_Type'] = overall_diag
        df_multi['Energy_kWh'] = df_multi['Avg_Daily_Energy_kWh']
        df_multi['Peak_kW'] = df_multi['Peak_kW_Max']
        df_multi['Est_Loss_kWh'] = df_multi['Total_Loss_kWh'].round(2)

        df_multi.sort_values(by=['Health_Status', 'Total_Loss_kWh'], ascending=[True, False], inplace=True)

        date_start = date_entries[0]['date_str']
        date_end = date_entries[-1]['date_str']

        kpis = {
            'timeframe': timeframe_code,
            'num_days': len(date_entries),
            'date_range_str': f"{date_start} - {date_end}",
            'total_inverters': len(df_multi),
            'critical_count': sum(1 for s in overall_status if s == 'CRITICAL'),
            'major_count': sum(1 for s in overall_status if s == 'MAJOR'),
            'minor_count': sum(1 for s in overall_status if s == 'MINOR'),
            'normal_count': sum(1 for s in overall_status if s == 'NORMAL'),
            'plant_median_energy_kwh': plant_med_multi,
            'total_loss_kwh': tot_loss_kwh,
            'total_loss_mwh': tot_loss_kwh / 1000.0,
            'total_energy_mwh': tot_energy_mwh,
            'plant_availability_pct': (sum(1 for s in overall_status if s in ['NORMAL', 'MINOR'])) / max(1, len(df_multi)) * 100.0
        }

        # Station summaries
        st_sums = {}
        for s_tag, grp in df_multi.groupby('Station_Tag'):
            st_sums[s_tag] = {
                'station_name': grp['Station'].iloc[0],
                'inverter_count': len(grp),
                'total_energy_mwh': float(grp['Total_Energy_kWh'].sum() / 1000.0),
                'total_loss_mwh': float(grp['Total_Loss_kWh'].sum() / 1000.0),
                'fault_count': int((grp['Health_Status'] != 'NORMAL').sum())
            }

        return {
            'status': 'SUCCESS',
            'timeframe': timeframe_code,
            'num_days': len(date_entries),
            'date_range_str': f"{date_start} - {date_end}",
            'inverter_table': df_multi,
            'alerts': all_alerts,
            'kpis': kpis,
            'station_medians': station_med_multi,
            'station_summaries': st_sums,
            'daily_results': daily_results
        }


def export_inverter_diagnostics_to_excel_bytes(df_inverters: pd.DataFrame, kpis: Dict[str, Any]) -> bytes:
    """Xuất báo cáo chẩn đoán Inverter chuẩn Excel (.xlsx) với định dạng số và highlight lỗi"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df = df_inverters[[
            'Inverter_ID', 'Station', 'Health_Status', 'Anomaly_Type',
            'Energy_kWh', 'Peak_kW', 'Ratio_Station_Pct', 'Est_Loss_kWh'
        ]].copy()
        export_df.columns = [
            'Mã Inverter', 'Trạm Biến Áp', 'Trạng Thái', 'Chẩn Đoán Bất Thường',
            'Sản Lượng (kWh/ngày)', 'Công Suất Đỉnh (kW)', 'Tỉ Lệ vs TB Trạm (%)', 'Tổn Thất Ước Tính (kWh)'
        ]
        export_df.to_excel(writer, sheet_name='Chi_Tiet_Inverter', index=False)

        kpi_rows = [
            {'Chỉ Số': 'Khung Thời Gian Chẩn Đoán', 'Giá Trị': str(kpis.get('timeframe', ''))},
            {'Chỉ Số': 'Khoảng Ngày', 'Giá Trị': str(kpis.get('date_range_str', kpis.get('date', '')))},
            {'Chỉ Số': 'Tổng Số Inverter Toàn Nhà Máy', 'Giá Trị': kpis.get('total_inverters', 233)},
            {'Chỉ Số': 'Số Inverter Nguy Cấp / Offline (Critical)', 'Giá Trị': kpis.get('critical_count', 0)},
            {'Chỉ Số': 'Số Inverter Suy Giảm Nặng (Major)', 'Giá Trị': kpis.get('major_count', 0)},
            {'Chỉ Số': 'Số Inverter Cảnh Báo Nhẹ (Minor)', 'Giá Trị': kpis.get('minor_count', 0)},
            {'Chỉ Số': 'Số Inverter Hoạt Động Bình Thường', 'Giá Trị': kpis.get('normal_count', 0)},
            {'Chỉ Số': 'Tổng Sản Lượng Nhà Máy (MWh)', 'Giá Trị': round(kpis.get('total_energy_mwh', 0.0), 2)},
            {'Chỉ Số': 'Tổng Tổn Thất Do Lỗi Inverter (MWh)', 'Giá Trị': round(kpis.get('total_loss_mwh', 0.0), 3)},
            {'Chỉ Số': 'Độ Sẵn Sàng Thiết Bị Availability (%)', 'Giá Trị': round(kpis.get('plant_availability_pct', 0.0), 2)},
        ]
        pd.DataFrame(kpi_rows).to_excel(writer, sheet_name='Tong_Hop_KPIs', index=False)

    return output.getvalue()
