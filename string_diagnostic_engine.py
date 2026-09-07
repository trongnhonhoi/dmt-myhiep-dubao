r"""
HỆ THỐNG GIÁM SÁT, TỔNG HỢP VÀ CHẨN ĐOÁN 4.040 CHUỖI STRING DC (HUAWEI SUN2000-175KTL-H0)
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - ĐƯỜNG DẪN SMARTLOGGER: D:\STRING_INV
LƯU Ý THIẾT KẾ: 64 Inverter không có chuỗi PV18 (Tổng 4.040 String = 64 INV x 17 + 164 INV x 18)
"""

import os
import re
import io
import glob
import time
import tarfile
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

DEFAULT_STRING_PATH = r'D:\STRING_INV'

# Danh sách 64 Inverter không đấu nối chuỗi String 18 theo hồ sơ thiết kế công trình
NO_PV18_INVERTERS = {
    # Trạm S1 (9 Inverter)
    'INV1.1.12', 'INV1.1.13', 'INV1.1.14', 'INV1.1.15', 'INV1.1.16', 'INV1.1.17',
    'INV1.2.14', 'INV1.2.15', 'INV1.2.16',
    # Trạm S2 (11 Inverter)
    'INV2.1.1', 'INV2.1.2', 'INV2.1.3', 'INV2.1.4', 'INV2.1.5', 'INV2.1.6', 'INV2.1.7',
    'INV2.2.3', 'INV2.2.4', 'INV2.2.16', 'INV2.2.17',
    # Trạm S3 (9 Inverter)
    'INV3.1.1', 'INV3.1.2', 'INV3.1.3',
    'INV3.2.1', 'INV3.2.2', 'INV3.2.3', 'INV3.2.4', 'INV3.2.5', 'INV3.2.6',
    # Trạm S4 (11 Inverter)
    'INV4.1.1', 'INV4.1.2', 'INV4.1.3', 'INV4.1.4', 'INV4.1.5',
    'INV4.2.2', 'INV4.2.3', 'INV4.2.8', 'INV4.2.9', 'INV4.2.17', 'INV4.2.18',
    # Trạm S5 (10 Inverter)
    'INV5.1.13', 'INV5.1.14', 'INV5.1.15', 'INV5.1.17',
    'INV5.2.13', 'INV5.2.14', 'INV5.2.15', 'INV5.2.16', 'INV5.2.17', 'INV5.2.18',
    # Trạm S6 (10 Inverter)
    'INV6.1.14', 'INV6.1.15', 'INV6.1.17', 'INV6.1.18',
    'INV6.2.13', 'INV6.2.14', 'INV6.2.15', 'INV6.2.16', 'INV6.2.17', 'INV6.2.18',
    # Trạm S7 (4 Inverter)
    'INV7.1.14', 'INV7.1.16', 'INV7.1.17', 'INV7.1.18'
}

LOGGER_MAPPING = {
    '102070023339': {'name': 'S1 (STATION-01)', 'tag': 'S1', 'substation': 'TBA S1 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023322': {'name': 'S2 (STATION-02)', 'tag': 'S2', 'substation': 'TBA S2 Phù Mỹ Nam', 'inverter_qty': 34},
    '1020B0050070': {'name': 'S3 (STATION-03)', 'tag': 'S3', 'substation': 'TBA S3 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023337': {'name': 'S4 (STATION-04)', 'tag': 'S4', 'substation': 'TBA S4 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070027475': {'name': 'S5 (STATION-05)', 'tag': 'S5', 'substation': 'TBA S5 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023324': {'name': 'S6 (STATION-06)', 'tag': 'S6', 'substation': 'TBA S6 Phù Mỹ Nam', 'inverter_qty': 36},
    '102070098529': {'name': 'S7 (STATION-07)', 'tag': 'S7', 'substation': 'TBA S7 Phù Mỹ Nam', 'inverter_qty': 18}
}

class StringDataManager:
    """Quản lý và chẩn đoán dữ liệu chuỗi String DC từ SmartLogger (4.040 chuỗi thực tế)"""
    def __init__(self, base_path: str = DEFAULT_STRING_PATH):
        self.base_path = base_path
        self._cache_df: Optional[pd.DataFrame] = None
        self._last_loaded_time: float = 0.0

    def check_connection(self) -> bool:
        try:
            return os.path.exists(self.base_path)
        except Exception:
            return False

    def get_available_snapshots(self) -> List[Dict[str, Any]]:
        """Tìm danh sách các thư mục ngày / tệp dữ liệu SmartLogger trong D:\\STRING_INV"""
        if not self.check_connection():
            return []
        
        tar_files = glob.glob(os.path.join(self.base_path, '**', '*.tar.gz'), recursive=True)
        if not tar_files:
            return []
        
        dates_dict = {}
        for f in tar_files:
            dir_name = os.path.dirname(f)
            rel_dir = os.path.relpath(dir_name, self.base_path)
            mtime = os.path.getmtime(f)
            dt_file = datetime.fromtimestamp(mtime)
            
            # Match timestamp in filename if any e.g. 20260907092312
            m = re.search(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})', os.path.basename(f))
            if m:
                y, mth, d, h, mn = m.groups()
                time_label = f"{d}/{mth}/{y} {h}:{mn}"
                date_key = f"{d}/{mth}/{y}"
            else:
                time_label = dt_file.strftime('%d/%m/%Y %H:%M')
                date_key = dt_file.strftime('%d/%m/%Y')
                
            if dir_name not in dates_dict:
                dates_dict[dir_name] = {
                    'dir_path': dir_name,
                    'rel_dir': rel_dir,
                    'date_key': date_key,
                    'time_label': time_label,
                    'file_count': 1,
                    'latest_mtime': mtime
                }
            else:
                dates_dict[dir_name]['file_count'] += 1
                if mtime > dates_dict[dir_name]['latest_mtime']:
                    dates_dict[dir_name]['latest_mtime'] = mtime
                    dates_dict[dir_name]['time_label'] = time_label

        snapshots = sorted(dates_dict.values(), key=lambda x: x['latest_mtime'], reverse=True)
        return snapshots

    def load_string_data(self, target_dir: Optional[str] = None, force_reload: bool = False) -> pd.DataFrame:
        """Đọc và giải nén toàn bộ các file SmartLogger inv_run_pv_data.csv"""
        if self._cache_df is not None and not force_reload and target_dir is None:
            return self._cache_df

        if not self.check_connection():
            return pd.DataFrame()

        search_path = target_dir if target_dir and os.path.exists(target_dir) else self.base_path
        tar_files = glob.glob(os.path.join(search_path, '**', '*.tar.gz'), recursive=True)
        
        # If target_dir was not specified and there are multiple folders, pick the latest one
        if not target_dir and tar_files:
            snapshots = self.get_available_snapshots()
            if snapshots:
                search_path = snapshots[0]['dir_path']
                tar_files = glob.glob(os.path.join(search_path, '**', '*.tar.gz'), recursive=True)

        if not tar_files:
            return pd.DataFrame()

        raw_inverter_dfs = []
        for fpath in sorted(tar_files):
            try:
                with tarfile.open(fpath, 'r:*') as tar:
                    member_names = tar.getnames()
                    csv_member = next((m for m in member_names if m.endswith('.csv')), None)
                    if not csv_member:
                        continue
                    f = tar.extractfile(csv_member)
                    if not f:
                        continue
                    raw_lines = [l.decode('utf-8', errors='ignore').strip() for l in f if l.decode('utf-8', errors='ignore').strip()]
                    
                    logger_sn = ""
                    for line in raw_lines[:5]:
                        if 'SmartLogger SN:' in line:
                            logger_sn = line.split('SmartLogger SN:')[-1].strip()
                            break

                    data_lines = [l for l in raw_lines if not l.startswith('#')]
                    if not data_lines:
                        continue
                    
                    csv_text = "\n".join(data_lines)
                    df_smart = pd.read_csv(io.StringIO(csv_text))
                    df_smart.rename(columns={df_smart.columns[0]: 'Inverter_ID'}, inplace=True)
                    df_smart['Logger_SN'] = logger_sn
                    df_smart['Source_File'] = os.path.basename(fpath)
                    df_smart['File_Path'] = fpath
                    raw_inverter_dfs.append(df_smart)
            except Exception as e:
                print(f"Error reading {fpath}: {e}")

        if not raw_inverter_dfs:
            return pd.DataFrame()

        df_all = pd.concat(raw_inverter_dfs, ignore_index=True)

        # Convert string voltage and current columns
        u_cols = [f'Upv{i}(V)' for i in range(1, 19)]
        i_cols = [f'Ipv{i}(A)' for i in range(1, 19)]

        for c in u_cols + i_cols:
            if c in df_all.columns:
                df_all[c] = pd.to_numeric(df_all[c].astype(str).str.replace('--', ''), errors='coerce').fillna(0.0)
            else:
                df_all[c] = 0.0

        # Calculate Plant-wide benchmarks
        active_currents = []
        for _, r in df_all.iterrows():
            inv_id_chk = str(r['Inverter_ID']).strip()
            chk_range = 17 if inv_id_chk in NO_PV18_INVERTERS else 18
            for idx in range(chk_range):
                val = float(r[f'Ipv{idx+1}(A)'])
                if val > 0.5:
                    active_currents.append(val)
        benchmark_plant_i = float(np.median(active_currents)) if active_currents else 3.55
        benchmark_plant_u = 1015.0
        benchmark_string_kw = (benchmark_plant_u * benchmark_plant_i) / 1000.0

        records = []
        for _, r in df_all.iterrows():
            inv_id = str(r['Inverter_ID']).strip()
            sn = str(r.get('SN', '')).strip()
            status = str(r.get('Device status', 'On-grid')).strip()
            logger_sn = str(r.get('Logger_SN', '')).strip()
            addr = r.get('Address', 0)
            rated_p = float(r.get('Rated power(kW)', 175.0))
            f_name = r.get('Source_File', '')

            # Check if this Inverter has PV18 according to plant engineering design
            has_pv18 = (inv_id not in NO_PV18_INVERTERS)
            installed_strings = 17 if not has_pv18 else 18

            # Station identification
            st_info = LOGGER_MAPPING.get(logger_sn, {})
            station_name = st_info.get('name', f'Trạm {logger_sn}')
            station_tag = st_info.get('tag', 'S?')
            
            # Infer Station from Inverter ID if not in mapping
            if station_tag == 'S?' and 'INV' in inv_id.upper():
                m_st = re.search(r'INV(\d+)', inv_id.upper())
                if m_st:
                    station_tag = f'S{m_st.group(1)}'
                    station_name = f'S{m_st.group(1)} (STATION-0{m_st.group(1)})'

            u_arr = np.array([float(r[f'Upv{i}(V)']) for i in range(1, 19)], dtype=np.float64)
            i_arr = np.array([float(r[f'Ipv{i}(A)']) for i in range(1, 19)], dtype=np.float64)

            # If PV18 is not installed, override PV18 values to 0.0 for clean metrics
            if not has_pv18:
                u_arr[17] = 0.0
                i_arr[17] = 0.0

            p_arr_kw = np.round((u_arr * i_arr) / 1000.0, 3)
            tot_pdc_kw = float(np.sum(p_arr_kw))

            # Filter active vs dead strings (ONLY on installed strings 1..installed_strings)
            active_mask = (i_arr[:installed_strings] > 0.3)
            active_count = int(np.sum(active_mask))
            dead_count = installed_strings - active_count

            open_circuit_strings = []
            zero_u_strings = []
            low_i_strings = []

            for idx in range(installed_strings):
                u_val = u_arr[idx]
                i_val = i_arr[idx]
                if u_val > 300.0 and i_val <= 0.05:
                    open_circuit_strings.append(idx + 1)
                elif u_val <= 50.0 and i_val <= 0.05:
                    zero_u_strings.append(idx + 1)

            avg_i_inv = float(np.mean(i_arr[:installed_strings][active_mask])) if active_count > 0 else 0.0
            valid_u = u_arr[:installed_strings][u_arr[:installed_strings] > 300.0]
            avg_u_inv = float(np.mean(valid_u)) if len(valid_u) > 0 else 0.0
            min_i_inv = float(np.min(i_arr[:installed_strings][active_mask])) if active_count > 0 else 0.0
            max_i_inv = float(np.max(i_arr[:installed_strings])) if active_count > 0 else 0.0

            if active_count > 0 and avg_i_inv > 0.5:
                for idx in range(installed_strings):
                    i_val = i_arr[idx]
                    if 0.05 < i_val < avg_i_inv * 0.70:
                        low_i_strings.append(idx + 1)

            # Imbalance percentage
            imbalance_pct = round(((max_i_inv - min_i_inv) / avg_i_inv * 100.0), 1) if avg_i_inv > 0 else 0.0

            # Health classification
            diag_msgs = []
            if 'DISCONNECT' in status.upper():
                health_status = 'CRITICAL'
                anomaly_type = 'Mất Kết Nối (Disconnected)'
                diag_msgs.append('Inverter mất kết nối truyền thông RS485 với SmartLogger.')
                loss_kw = rated_p
            elif 'IDLE' in status.upper() or 'NO IRRADIATION' in status.upper() or active_count == 0:
                health_status = 'CRITICAL'
                anomaly_type = 'Dừng Nghỉ (Idle / P=0)'
                diag_msgs.append(f'Inverter ở trạng thái Idle, toàn bộ {installed_strings} chuỗi String không phát điện.')
                loss_kw = rated_p
            elif dead_count >= 3:
                health_status = 'MAJOR'
                anomaly_type = f'Hỏng {dead_count}/{installed_strings} Chuỗi'
                diag_msgs.append(f'Hỏng {dead_count}/{installed_strings} chuỗi String DC. Các chuỗi hở mạch: PV{open_circuit_strings}')
                loss_kw = dead_count * benchmark_string_kw
            elif dead_count >= 1:
                health_status = 'MINOR'
                anomaly_type = f'Hỏng {dead_count}/{installed_strings} Chuỗi'
                diag_msgs.append(f'Hỏng {dead_count}/{installed_strings} chuỗi String DC: PV{open_circuit_strings}')
                loss_kw = dead_count * benchmark_string_kw
            elif len(low_i_strings) > 0:
                health_status = 'WARNING'
                anomaly_type = f'Lệch Dòng {len(low_i_strings)} Chuỗi'
                diag_msgs.append(f'Dòng điện chuỗi PV{low_i_strings} suy giảm > 30% so với trung bình.')
                loss_kw = len(low_i_strings) * (benchmark_string_kw * 0.4)
            else:
                health_status = 'NORMAL'
                if not has_pv18:
                    anomaly_type = 'Bình Thường (17/17 String)'
                    diag_msgs.append('Tất cả 17 chuỗi String DC hoạt động bình thường (Chuỗi PV18 không đấu nối theo thiết kế).')
                else:
                    anomaly_type = 'Bình Thường (18/18 String)'
                    diag_msgs.append('Tất cả 18 chuỗi String DC hoạt động bình thường, dòng áp đồng đều.')
                loss_kw = 0.0

            records.append({
                'Inverter_ID': inv_id,
                'SN': sn,
                'Station': station_name,
                'Station_Tag': station_tag,
                'Logger_SN': logger_sn,
                'Address': addr,
                'Device_Status': status,
                'Health_Status': health_status,
                'Anomaly_Type': anomaly_type,
                'Installed_Strings': installed_strings,
                'Has_PV18': has_pv18,
                'PV18_Note': 'Có PV18' if has_pv18 else 'Không Đấu PV18 (Thiết kế)',
                'Active_Strings': active_count,
                'Dead_Strings_Count': dead_count,
                'Open_Circuit_Strings': open_circuit_strings,
                'Open_Circuit_Count': len(open_circuit_strings),
                'Zero_U_Strings': zero_u_strings,
                'Zero_U_Count': len(zero_u_strings),
                'Low_I_Strings': low_i_strings,
                'Low_I_Count': len(low_i_strings),
                'Total_Pdc_kW': round(tot_pdc_kw, 2),
                'Est_Loss_kW': round(loss_kw, 2),
                'Avg_Voltage_V': round(avg_u_inv, 1),
                'Avg_Current_A': round(avg_i_inv, 2),
                'Min_Current_A': round(min_i_inv, 2),
                'Max_Current_A': round(max_i_inv, 2),
                'Imbalance_Pct': imbalance_pct,
                'Diagnostic_Message': ' | '.join(diag_msgs),
                'Upv_List': u_arr.tolist(),
                'Ipv_List': i_arr.tolist(),
                'Pdc_List': p_arr_kw.tolist(),
                'Source_File': f_name
            })

        res_df = pd.DataFrame(records)
        res_df.sort_values(by=['Station_Tag', 'Inverter_ID'], inplace=True)
        self._cache_df = res_df
        self._last_loaded_time = time.time()
        return res_df

    def get_summary_kpis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Tính toán các thẻ KPIs tổng quan về tình trạng 4.040 chuỗi String thực tế"""
        if df.empty:
            return {}

        total_inv = len(df)
        total_installed_strings = int(df['Installed_Strings'].sum()) if 'Installed_Strings' in df.columns else total_inv * 18
        unconnected_pv18_inv = int((df['Installed_Strings'] == 17).sum()) if 'Installed_Strings' in df.columns else 0
        
        active_strings = int(df['Active_Strings'].sum())
        dead_strings = total_installed_strings - active_strings
        open_circuit_strings = int(df['Open_Circuit_Count'].sum())
        
        on_grid_inv = int((df['Health_Status'].isin(['NORMAL', 'MINOR', 'MAJOR', 'WARNING'])).sum())
        offline_inv = int((df['Health_Status'] == 'CRITICAL').sum())
        
        tot_pdc_mw = float(df['Total_Pdc_kW'].sum() / 1000.0)
        tot_loss_kw = float(df['Est_Loss_kW'].sum())
        
        healthy_pct = round(active_strings / total_installed_strings * 100.0, 1) if total_installed_strings > 0 else 0.0
        avg_u = float(df[df['Avg_Voltage_V'] > 300]['Avg_Voltage_V'].mean()) if not df.empty else 0.0
        avg_i = float(df[df['Avg_Current_A'] > 0.3]['Avg_Current_A'].mean()) if not df.empty else 0.0

        return {
            'total_inverters': total_inv,
            'on_grid_inverters': on_grid_inv,
            'offline_inverters': offline_inv,
            'total_installed_strings': total_installed_strings,
            'unconnected_pv18_inv': unconnected_pv18_inv,
            'active_strings': active_strings,
            'dead_strings': dead_strings,
            'open_circuit_strings': open_circuit_strings,
            'healthy_string_pct': healthy_pct,
            'total_pdc_mw': round(tot_pdc_mw, 3),
            'est_loss_kw': round(tot_loss_kw, 1),
            'est_loss_mw': round(tot_loss_kw / 1000.0, 3),
            'avg_voltage_v': round(avg_u, 1),
            'avg_current_a': round(avg_i, 2)
        }

    def get_station_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tổng hợp thống kê tình trạng String theo từng Trạm biến áp (S1..S7)"""
        if df.empty:
            return pd.DataFrame()

        rows = []
        for st_tag, grp in df.groupby('Station_Tag'):
            st_name = grp['Station'].iloc[0]
            n_inv = len(grp)
            tot_str = int(grp['Installed_Strings'].sum()) if 'Installed_Strings' in grp.columns else n_inv * 18
            n_no_pv18 = int((grp['Installed_Strings'] == 17).sum()) if 'Installed_Strings' in grp.columns else 0
            act_str = int(grp['Active_Strings'].sum())
            dead_str = tot_str - act_str
            open_str = int(grp['Open_Circuit_Count'].sum())
            pdc_mw = round(float(grp['Total_Pdc_kW'].sum()) / 1000.0, 3)
            loss_kw = round(float(grp['Est_Loss_kW'].sum()), 1)
            pct_act = round(act_str / tot_str * 100.0, 1) if tot_str > 0 else 0.0
            
            n_critical = int((grp['Health_Status'] == 'CRITICAL').sum())
            n_major = int((grp['Health_Status'] == 'MAJOR').sum())
            n_minor = int((grp['Health_Status'] == 'MINOR').sum())
            n_normal = int((grp['Health_Status'] == 'NORMAL').sum())

            rows.append({
                'Mã Trạm': st_tag,
                'Tên Trạm Biến Áp': st_name,
                'Số Inverter': n_inv,
                'Tổng String Thiết Kế': tot_str,
                'Số INV 17 String (KĐN PV18)': n_no_pv18,
                'String Đang Phát': act_str,
                'String Hỏng / Hở': dead_str,
                'Tỷ Lệ Phát (%)': pct_act,
                'Công Suất Pdc (MW)': pdc_mw,
                'Tổn Thất Ước Tính (kW)': loss_kw,
                'Số INV Offline': n_critical,
                'Số INV Lỗi Nặng': n_major,
                'Số INV Lỗi Nhẹ': n_minor,
                'Số INV Tốt': n_normal
            })

        res = pd.DataFrame(rows)
        res.sort_values(by='Mã Trạm', inplace=True)
        return res


def export_string_diagnostics_to_excel_bytes(df: pd.DataFrame, kpis: Dict[str, Any], date_label: str = "") -> bytes:
    """Xuất báo cáo chi tiết 4.040 chuỗi String DC ra file Excel 4 sheets"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Tổng Quan KPIs
        kpi_data = [
            {'Chỉ Số Giám Sát String': 'Thời Điểm Xuất Báo Cáo', 'Giá Trị': date_label},
            {'Chỉ Số Giám Sát String': 'Tổng Số Inverter Giám Sát', 'Giá Trị': kpis.get('total_inverters', 0)},
            {'Chỉ Số Giám Sát String': 'Số Inverter Hòa Lưới (On-grid)', 'Giá Trị': kpis.get('on_grid_inverters', 0)},
            {'Chỉ Số Giám Sát String': 'Số Inverter Nghỉ / Mất Kết Nối', 'Giá Trị': kpis.get('offline_inverters', 0)},
            {'Chỉ Số Giám Sát String': 'Tổng Số Chuỗi String Thiết Kế Thực Tế', 'Giá Trị': f"{kpis.get('total_installed_strings', 4040)} Chuỗi (64 INV x 17 + 164 INV x 18)"},
            {'Chỉ Số Giám Sát String': 'Số Inverter Không Đấu Nối PV18 (17 String)', 'Giá Trị': f"{kpis.get('unconnected_pv18_inv', 64)} Inverter"},
            {'Chỉ Số Giám Sát String': 'Số Chuỗi String Đang Phát Điện (I > 0.3A)', 'Giá Trị': kpis.get('active_strings', 0)},
            {'Chỉ Số Giám Sát String': 'Số Chuỗi String Bị Hở Mạch / Hỏng', 'Giá Trị': kpis.get('dead_strings', 0)},
            {'Chỉ Số Giám Sát String': 'Tỷ Lệ Chuỗi String Hoạt Động Tốt (%)', 'Giá Trị': f"{kpis.get('healthy_string_pct', 0.0)}%"},
            {'Chỉ Số Giám Sát String': 'Tổng Công Suất DC Tức Thời (MW)', 'Giá Trị': kpis.get('total_pdc_mw', 0.0)},
            {'Chỉ Số Giám Sát String': 'Tổng Tổn Thất Công Suất DC Ước Tính (kW)', 'Giá Trị': kpis.get('est_loss_kw', 0.0)},
            {'Chỉ Số Giám Sát String': 'Điện Áp Chuỗi Trung Bình (V)', 'Giá Trị': kpis.get('avg_voltage_v', 0.0)},
            {'Chỉ Số Giám Sát String': 'Dòng Điện Chuỗi Trung Bình (A)', 'Giá Trị': kpis.get('avg_current_a', 0.0)}
        ]
        pd.DataFrame(kpi_data).to_excel(writer, sheet_name='Tong_Quan_KPIs', index=False)

        # Sheet 2: Danh Sách 228 Inverter
        df_inv_exp = df[[
            'Inverter_ID', 'Station', 'SN', 'Device_Status', 'Health_Status',
            'Installed_Strings', 'PV18_Note', 'Active_Strings', 'Dead_Strings_Count', 'Open_Circuit_Count', 'Low_I_Count',
            'Total_Pdc_kW', 'Est_Loss_kW', 'Avg_Voltage_V', 'Avg_Current_A', 'Imbalance_Pct', 'Diagnostic_Message'
        ]].copy()
        df_inv_exp.columns = [
            'Mã Inverter', 'Trạm Biến Áp', 'Serial Number', 'Trạng Thái Máy', 'Đánh Giá Sức Khỏe',
            'Số String Thiết Kế (17/18)', 'Ghi Chú PV18', 'String Đang Phát', 'String Hỏng', 'String Hở Mạch (I=0, U>300V)', 'String Lệch Dòng',
            'Công Suất DC (kW)', 'Tổn Thất Ước Tính (kW)', 'Điện Áp TB (V)', 'Dòng Điện TB (A)', 'Độ Lệch Dòng (%)', 'Chẩn Đoán Kỹ Thuật O&M'
        ]
        df_inv_exp.to_excel(writer, sheet_name='Danh_Sach_228_Inverter', index=False)

        # Sheet 3: Ma Trận Chuỗi String Dòng Điện I (A) & Điện Áp U (V)
        matrix_rows = []
        for _, r in df.iterrows():
            row_dict = {
                'Mã Inverter': r['Inverter_ID'],
                'Trạm': r['Station_Tag'],
                'Số String Thiết Kế': r['Installed_Strings'],
                'Ghi Chú PV18': r['PV18_Note'],
                'Trạng Thái': r['Health_Status'],
                'Pdc (kW)': r['Total_Pdc_kW']
            }
            for i in range(18):
                if i == 17 and not r['Has_PV18']:
                    row_dict[f'I_PV{i+1} (A)'] = "KĐN"
                    row_dict[f'U_PV{i+1} (V)'] = "KĐN"
                else:
                    row_dict[f'I_PV{i+1} (A)'] = r['Ipv_List'][i]
                    row_dict[f'U_PV{i+1} (V)'] = r['Upv_List'][i]
            matrix_rows.append(row_dict)
        pd.DataFrame(matrix_rows).to_excel(writer, sheet_name='Ma_Tran_4040_Strings', index=False)

        # Sheet 4: Danh Sách Cảnh Báo Sự Cố Cần Bảo Dưỡng O&M
        df_faults = df[df['Health_Status'] != 'NORMAL'].copy()
        if not df_faults.empty:
            df_faults_exp = df_faults[[
                'Inverter_ID', 'Station', 'Health_Status', 'Anomaly_Type', 'Installed_Strings',
                'Dead_Strings_Count', 'Open_Circuit_Strings', 'Low_I_Strings',
                'Total_Pdc_kW', 'Est_Loss_kW', 'Diagnostic_Message'
            ]]
            df_faults_exp.columns = [
                'Mã Inverter', 'Trạm Biến Áp', 'Mức Độ Cảnh Báo', 'Hiện Tượng Bất Thường', 'Số String Thiết Kế',
                'Số Chuỗi Hỏng', 'Danh Sách Chuỗi Hở Mạch', 'Danh Sách Chuỗi Lệch Dòng',
                'Công Suất Hiện Tại (kW)', 'Tổn Thất (kW)', 'Khuyến Nghị O&M'
            ]
            df_faults_exp.to_excel(writer, sheet_name='Canh_Bao_Su_Co_OM', index=False)

    return output.getvalue()
