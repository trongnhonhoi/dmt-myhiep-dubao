r"""
HỆ THỐNG GIÁM SÁT, TỔNG HỢP VÀ CHẨN ĐOÁN 4.058 CHUỖI STRING DC (HUAWEI SUN2000-175KTL-H0)
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - ĐƯỜNG DẪN SMARTLOGGER: D:\STRING_INV
QUY MÔ TOÀN NHÀ MÁY: 229 INVERTER (64 INV x 17S + 165 INV x 18S = 4.058 STRINGS)
TỰ ĐỘNG PHÁT HIỆN INVERTER THIẾU DỮ LIỆU SMARTLOGGER (VD: INV2.2.1 TẠI TRẠM S2)
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

# Danh mục gốc 229 Inverter toàn nhà máy Mỹ Hiệp
PLANT_MASTER_INVERTERS_MAP = {}
# S1: 35
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV1.1.{i}"] = {'station': 'S1 (STATION-01)', 'tag': 'S1', 'logger': '102070023339'}
for i in range(1, 18): PLANT_MASTER_INVERTERS_MAP[f"INV1.2.{i}"] = {'station': 'S1 (STATION-01)', 'tag': 'S1', 'logger': '102070023339'}

# S2: 35 (Gồm cả INV2.2.1 có 18 chuỗi)
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV2.1.{i}"] = {'station': 'S2 (STATION-02)', 'tag': 'S2', 'logger': '102070023322'}
for i in range(1, 18): PLANT_MASTER_INVERTERS_MAP[f"INV2.2.{i}"] = {'station': 'S2 (STATION-02)', 'tag': 'S2', 'logger': '102070023322'}

# S3: 35
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV3.1.{i}"] = {'station': 'S3 (STATION-03)', 'tag': 'S3', 'logger': '1020B0050070'}
for i in range(1, 18): PLANT_MASTER_INVERTERS_MAP[f"INV3.2.{i}"] = {'station': 'S3 (STATION-03)', 'tag': 'S3', 'logger': '1020B0050070'}

# S4: 35
for i in range(1, 18): PLANT_MASTER_INVERTERS_MAP[f"INV4.1.{i}"] = {'station': 'S4 (STATION-04)', 'tag': 'S4', 'logger': '102070023337'}
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV4.2.{i}"] = {'station': 'S4 (STATION-04)', 'tag': 'S4', 'logger': '102070023337'}

# S5: 35
for i in range(1, 18): PLANT_MASTER_INVERTERS_MAP[f"INV5.1.{i}"] = {'station': 'S5 (STATION-05)', 'tag': 'S5', 'logger': '102070027475'}
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV5.2.{i}"] = {'station': 'S5 (STATION-05)', 'tag': 'S5', 'logger': '102070027475'}

# S6: 36
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV6.1.{i}"] = {'station': 'S6 (STATION-06)', 'tag': 'S6', 'logger': '102070023324'}
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV6.2.{i}"] = {'station': 'S6 (STATION-06)', 'tag': 'S6', 'logger': '102070023324'}

# S7: 18
for i in range(1, 19): PLANT_MASTER_INVERTERS_MAP[f"INV7.1.{i}"] = {'station': 'S7 (STATION-07)', 'tag': 'S7', 'logger': '102070098529'}


LOGGER_MAPPING = {
    '102070023339': {'name': 'S1 (STATION-01)', 'tag': 'S1', 'substation': 'TBA S1 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023322': {'name': 'S2 (STATION-02)', 'tag': 'S2', 'substation': 'TBA S2 Phù Mỹ Nam', 'inverter_qty': 35},
    '1020B0050070': {'name': 'S3 (STATION-03)', 'tag': 'S3', 'substation': 'TBA S3 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023337': {'name': 'S4 (STATION-04)', 'tag': 'S4', 'substation': 'TBA S4 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070027475': {'name': 'S5 (STATION-05)', 'tag': 'S5', 'substation': 'TBA S5 Phù Mỹ Nam', 'inverter_qty': 35},
    '102070023324': {'name': 'S6 (STATION-06)', 'tag': 'S6', 'substation': 'TBA S6 Phù Mỹ Nam', 'inverter_qty': 36},
    '102070098529': {'name': 'S7 (STATION-07)', 'tag': 'S7', 'substation': 'TBA S7 Phù Mỹ Nam', 'inverter_qty': 18}
}

class StringDataManager:
    """Quản lý và chẩn đoán dữ liệu 229 Inverter & 4.058 chuỗi String DC từ SmartLogger"""
    def __init__(self, base_path: str = DEFAULT_STRING_PATH):
        self.base_path = base_path
        self._cache_df: Optional[pd.DataFrame] = None
        self._cache_snap_path: Optional[str] = None
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
        """Đọc và giải nén toàn bộ các file SmartLogger inv_run_pv_data.csv kèm kiểm tra 229 Inverter"""
        if self._cache_df is not None and not force_reload and (target_dir is None or target_dir == self._cache_snap_path):
            return self._cache_df

        if not self.check_connection():
            return pd.DataFrame()

        search_path = target_dir if target_dir and os.path.exists(target_dir) else self.base_path
        tar_files = glob.glob(os.path.join(search_path, '**', '*.tar.gz'), recursive=True)
        
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
        found_inv_ids = set()

        for _, r in df_all.iterrows():
            inv_id = str(r['Inverter_ID']).strip()
            found_inv_ids.add(inv_id)
            sn = str(r.get('SN', '')).strip()
            status = str(r.get('Device status', 'On-grid')).strip()
            logger_sn = str(r.get('Logger_SN', '')).strip()
            addr = r.get('Address', 0)
            rated_p = float(r.get('Rated power(kW)', 175.0))
            f_name = r.get('Source_File', '')

            has_pv18 = (inv_id not in NO_PV18_INVERTERS)
            installed_strings = 17 if not has_pv18 else 18

            st_info = LOGGER_MAPPING.get(logger_sn, {})
            station_name = st_info.get('name', f'Trạm {logger_sn}')
            station_tag = st_info.get('tag', 'S?')
            
            if station_tag == 'S?' and 'INV' in inv_id.upper():
                m_st = re.search(r'INV(\d+)', inv_id.upper())
                if m_st:
                    station_tag = f'S{m_st.group(1)}'
                    station_name = f'S{m_st.group(1)} (STATION-0{m_st.group(1)})'

            u_arr = np.array([float(r[f'Upv{i}(V)']) for i in range(1, 19)], dtype=np.float64)
            i_arr = np.array([float(r[f'Ipv{i}(A)']) for i in range(1, 19)], dtype=np.float64)

            if not has_pv18:
                u_arr[17] = 0.0
                i_arr[17] = 0.0

            p_arr_kw = np.round((u_arr * i_arr) / 1000.0, 3)
            tot_pdc_kw = float(np.sum(p_arr_kw))

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

            imbalance_pct = round(((max_i_inv - min_i_inv) / avg_i_inv * 100.0), 1) if avg_i_inv > 0 else 0.0

            # MPPT Analysis
            mppt_details = []
            mppt_faulty_count = 0
            mppt_mismatch_max = 0.0
            both_dead_mppts = []

            for m in range(9):
                idx_a = 2 * m
                idx_b = 2 * m + 1
                pv_a = idx_a + 1
                pv_b = idx_b + 1
                
                ia = i_arr[idx_a]
                ua = u_arr[idx_a]
                
                if m == 8 and not has_pv18:
                    ib = 0.0
                    ub = 0.0
                    is_single_configured = True
                else:
                    ib = i_arr[idx_b]
                    ub = u_arr[idx_b]
                    is_single_configured = False
                
                diff_i = abs(ia - ib)
                avg_pair_i = (ia + ib) / 2.0 if (ia + ib) > 0 else 0.0
                pair_mismatch = round((diff_i / avg_pair_i * 100.0), 1) if avg_pair_i > 0.5 and not is_single_configured else 0.0
                if pair_mismatch > mppt_mismatch_max:
                    mppt_mismatch_max = pair_mismatch

                mppt_st = "TỐT"
                if is_single_configured:
                    mppt_st = "ĐƠN (17S - KĐN PV18)" if ia > 0.3 else ("HỞ MẠCH PV17" if ua > 300 else "MẤT DÒNG")
                elif ia <= 0.05 and ib <= 0.05:
                    mppt_st = "MẤT CẢ 2 CHUỖI" if (ua > 300 or ub > 300) else "DỪNG CẢ 2"
                    both_dead_mppts.append(m + 1)
                    mppt_faulty_count += 1
                elif ia <= 0.05 or ib <= 0.05:
                    h_name = f"PV{pv_a}" if ia <= 0.05 else f"PV{pv_b}"
                    mppt_st = f"HỞ 1 CHUỖI ({h_name})"
                    mppt_faulty_count += 1
                elif pair_mismatch > 20.0:
                    mppt_st = f"LỆCH DÒNG ({pair_mismatch}%)"
                    mppt_faulty_count += 1

                mppt_details.append({
                    'mppt': m + 1,
                    'pv_a': f"PV{pv_a}",
                    'pv_b': f"PV{pv_b}" if not is_single_configured else "KĐN",
                    'i_a': round(ia, 2),
                    'u_a': round(ua, 1),
                    'i_b': round(ib, 2),
                    'u_b': round(ub, 1),
                    'diff_i': round(diff_i, 2),
                    'mismatch_pct': pair_mismatch,
                    'status': mppt_st
                })

            # Helper format PV list
            def _format_pvs(pvs):
                if not pvs: return ""
                if isinstance(pvs, (list, tuple, set)):
                    return ", ".join([f"PV{x}" for x in sorted(pvs)])
                return f"PV{pvs}"

            dead_pv_indices = open_circuit_strings if open_circuit_strings else zero_u_strings
            dead_pv_txt = _format_pvs(dead_pv_indices)
            low_pv_txt = _format_pvs(low_i_strings)

            # Root Cause & Priorities
            if 'DISCONNECT' in status.upper():
                health_status = 'CRITICAL'
                anomaly_type = 'Mất Kết Nối (Disconnected)'
                root_cause_summary = 'Mất tín hiệu truyền thông RS485 với SmartLogger hoặc mất nguồn AC tự dùng.'
                action_recommendation = 'Kiểm tra cáp tín hiệu RS485 cổng COM1/COM2, kiểm tra cầu dao AC tự dùng của Inverter.'
                loss_kw = rated_p
                priority_level = "Mức 1 (Khẩn Cấp)"
            elif 'IDLE' in status.upper() or 'NO IRRADIATION' in status.upper() or active_count == 0:
                health_status = 'CRITICAL'
                anomaly_type = 'Dừng Nghỉ (Idle / P=0)'
                root_cause_summary = f'Inverter ở trạng thái Idle, toàn bộ {installed_strings} chuỗi String không phát điện.'
                action_recommendation = 'Kiểm tra điện áp lưới AC, rơle bảo vệ tác động hoặc công tắc DC Switch đang OFF.'
                loss_kw = rated_p
                priority_level = "Mức 1 (Khẩn Cấp)"
            elif dead_count >= 3:
                health_status = 'MAJOR'
                anomaly_type = f'Hỏng {dead_count}/{installed_strings} Chuỗi'
                if len(both_dead_mppts) >= 2:
                    root_cause_summary = f'Đứt tuyến cáp tổng máng gom hoặc hỏng bo mạch MPPT (Mất cả cặp tại MPPT {both_dead_mppts} gồm các chuỗi {dead_pv_txt}).'
                    action_recommendation = f'Đo kiểm tra điện áp Voc tại đầu vào MPPT {both_dead_mppts}, rà soát tuyến cáp ngầm từ giàn pin.'
                else:
                    root_cause_summary = f'Hở mạch {dead_count} chuỗi riêng lẻ tại các giàn pin ({dead_pv_txt}: Tuột giắc MC4 / Đứt cáp nhánh).'
                    action_recommendation = f'Dùng Ampe kìm DC đo từng chuỗi {dead_pv_txt}, bấm lại giắc MC4 bị cháy/lỏng.'
                loss_kw = dead_count * benchmark_string_kw
                priority_level = "Mức 1 (Khẩn Cấp)" if dead_count >= 5 else "Mức 2 (Trung Bình)"
            elif dead_count >= 1:
                health_status = 'MINOR'
                anomaly_type = f'Hỏng {dead_count}/{installed_strings} Chuỗi'
                root_cause_summary = f'Tuột/cháy giắc MC4 hoặc đứt cáp nhánh tại chuỗi {dead_pv_txt}.'
                action_recommendation = f'Kiểm tra và bấm lại giắc nối MC4 chuỗi {dead_pv_txt} tại đầu Inverter và giàn pin.'
                loss_kw = dead_count * benchmark_string_kw
                priority_level = "Mức 2 (Trung Bình)"
            elif len(low_i_strings) > 0:
                health_status = 'WARNING'
                anomaly_type = f'Suy Giảm Dòng ({len(low_i_strings)} Chuỗi)'
                root_cause_summary = f'Bụi bẩn, che bóng cục bộ hoặc hỏng Diode Bypass tại chuỗi {low_pv_txt}.'
                action_recommendation = f'Vệ sinh rửa bề mặt tấm pin các chuỗi {low_pv_txt}, dùng Camera nhiệt FLIR quét tìm Hotspot và Diode hỏng.'
                loss_kw = len(low_i_strings) * (benchmark_string_kw * 0.35)
                priority_level = "Mức 3 (Cần Vệ Sinh / Kiểm Tra)"
            elif mppt_mismatch_max > 45.0:
                health_status = 'WARNING'
                anomaly_type = f'Lệch Cặp MPPT ({mppt_mismatch_max}%)'
                root_cause_summary = f'Lệch dòng đáng kể giữa 2 chuỗi cùng cổng MPPT (chênh lệch {mppt_mismatch_max}%). Có thể do che bóng hoặc góc đón nắng giàn pin.'
                action_recommendation = 'Kiểm tra đấu nối đầu vào MPPT, kiểm tra bề mặt tấm pin và độ đồng đều giàn pin.'
                loss_kw = benchmark_string_kw * 0.25
                priority_level = "Mức 3 (Theo Dõi Thêm)"
            else:
                health_status = 'NORMAL'
                if not has_pv18:
                    anomaly_type = 'Bình Thường (17/17 String)'
                    root_cause_summary = 'Tất cả 17 chuỗi String DC hoạt động đồng đều, đạt công suất (Chuỗi PV18 không đấu nối theo thiết kế).'
                else:
                    anomaly_type = 'Bình Thường (18/18 String)'
                    root_cause_summary = 'Tất cả 18 chuỗi String DC hoạt động đồng đều, đạt công suất tối ưu.'
                action_recommendation = 'Tiếp tục theo dõi vận hành bình thường.'
                loss_kw = 0.0
                priority_level = "Mức 4 (Bình Thường)"

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
                'Priority_Level': priority_level,
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
                'MPPT_Mismatch_Max': mppt_mismatch_max,
                'MPPT_Faulty_Count': mppt_faulty_count,
                'MPPT_Details': mppt_details,
                'Root_Cause': root_cause_summary,
                'Action_Recommendation': action_recommendation,
                'Diagnostic_Message': f"{root_cause_summary} Khuyến nghị: {action_recommendation}",
                'Upv_List': u_arr.tolist(),
                'Ipv_List': i_arr.tolist(),
                'Pdc_List': p_arr_kw.tolist(),
                'Source_File': f_name
            })

        # AUTO-SYNTHESIZE MISSING INVERTERS FROM MASTER 229 REGISTRY (e.g. INV2.2.1)
        for inv_id, meta in PLANT_MASTER_INVERTERS_MAP.items():
            if inv_id not in found_inv_ids:
                has_pv18 = (inv_id not in NO_PV18_INVERTERS)
                installed_strings = 17 if not has_pv18 else 18
                
                # Synthetic MPPTs
                syn_mppts = []
                for m in range(9):
                    syn_mppts.append({
                        'mppt': m + 1,
                        'pv_a': f"PV{2*m+1}",
                        'pv_b': f"PV{2*m+2}" if not (m == 8 and not has_pv18) else "KĐN",
                        'i_a': 0.0, 'u_a': 0.0, 'i_b': 0.0, 'u_b': 0.0,
                        'diff_i': 0.0, 'mismatch_pct': 0.0, 'status': 'THIẾU DỮ LIỆU'
                    })

                records.append({
                    'Inverter_ID': inv_id,
                    'SN': '--',
                    'Station': meta['station'],
                    'Station_Tag': meta['tag'],
                    'Logger_SN': meta['logger'],
                    'Address': 0,
                    'Device_Status': 'Chưa Add / Mất Dữ Liệu SmartLogger',
                    'Health_Status': 'CRITICAL',
                    'Anomaly_Type': 'Thiếu Dữ Liệu SmartLogger (18 Chuỗi)',
                    'Priority_Level': 'Mức 1 (Khẩn Cấp)',
                    'Installed_Strings': installed_strings,
                    'Has_PV18': has_pv18,
                    'PV18_Note': 'Có PV18 (18S)' if has_pv18 else 'Không Đấu PV18 (17S)',
                    'Active_Strings': 0,
                    'Dead_Strings_Count': installed_strings,
                    'Open_Circuit_Strings': [],
                    'Open_Circuit_Count': 0,
                    'Zero_U_Strings': list(range(1, installed_strings + 1)),
                    'Zero_U_Count': installed_strings,
                    'Low_I_Strings': [],
                    'Low_I_Count': 0,
                    'Total_Pdc_kW': 0.0,
                    'Est_Loss_kW': 175.0,
                    'Avg_Voltage_V': 0.0,
                    'Avg_Current_A': 0.0,
                    'Min_Current_A': 0.0,
                    'Max_Current_A': 0.0,
                    'Imbalance_Pct': 0.0,
                    'MPPT_Mismatch_Max': 0.0,
                    'MPPT_Faulty_Count': 9,
                    'MPPT_Details': syn_mppts,
                    'Root_Cause': f'Inverter {inv_id} thiếu trong tệp dữ liệu SmartLogger {meta["tag"]} (Mất truyền thông RS485 / Chưa add thiết bị vào SmartLogger).',
                    'Action_Recommendation': f'Kiểm tra địa chỉ Modbus RS485 của {inv_id}, quét dò lại thiết bị (Device Auto-Assign / Add Device) trên giao diện SmartLogger {meta["tag"]}.',
                    'Diagnostic_Message': f'Inverter {inv_id} thiếu trong tệp dữ liệu SmartLogger {meta["tag"]}. Khuyến nghị: Quét add lại thiết bị trên SmartLogger {meta["tag"]}.',
                    'Upv_List': [0.0] * 18,
                    'Ipv_List': [0.0] * 18,
                    'Pdc_List': [0.0] * 18,
                    'Source_File': 'Thiếu trong SmartLogger'
                })

        res_df = pd.DataFrame(records)
        res_df.sort_values(by=['Station_Tag', 'Inverter_ID'], inplace=True)
        self._cache_df = res_df
        self._cache_snap_path = search_path
        self._last_loaded_time = time.time()
        return res_df

    def get_summary_kpis(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Tính toán các thẻ KPIs tổng quan về tình trạng 229 Inverter & 4.058 chuỗi String"""
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
        urgent_inv = int((df['Priority_Level'] == 'Mức 1 (Khẩn Cấp)').sum()) if 'Priority_Level' in df.columns else 0
        
        tot_pdc_mw = float(df['Total_Pdc_kW'].sum() / 1000.0)
        tot_loss_kw = float(df['Est_Loss_kW'].sum())
        
        healthy_pct = round(active_strings / total_installed_strings * 100.0, 1) if total_installed_strings > 0 else 0.0
        avg_u = float(df[df['Avg_Voltage_V'] > 300]['Avg_Voltage_V'].mean()) if not df.empty else 0.0
        avg_i = float(df[df['Avg_Current_A'] > 0.3]['Avg_Current_A'].mean()) if not df.empty else 0.0

        return {
            'total_inverters': total_inv,
            'on_grid_inverters': on_grid_inv,
            'offline_inverters': offline_inv,
            'urgent_inverters': urgent_inv,
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
            n_urgent = int((grp['Priority_Level'] == 'Mức 1 (Khẩn Cấp)').sum()) if 'Priority_Level' in grp.columns else 0

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
                'Số Lệnh Khẩn Cấp': n_urgent,
                'Số INV Offline': n_critical,
                'Số INV Lỗi Nặng': n_major,
                'Số INV Lỗi Nhẹ': n_minor,
                'Số INV Tốt': n_normal
            })

        res = pd.DataFrame(rows)
        res.sort_values(by='Mã Trạm', inplace=True)
        return res

    def get_om_work_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """Tự động tạo danh sách Phiếu Lệnh O&M Hiện Trường phân cấp ưu tiên"""
        if df.empty:
            return pd.DataFrame()

        faulty_df = df[df['Health_Status'] != 'NORMAL'].copy()
        if faulty_df.empty:
            return pd.DataFrame()

        def sort_priority(p):
            if 'Mức 1' in str(p): return 1
            if 'Mức 2' in str(p): return 2
            if 'Mức 3' in str(p): return 3
            return 4

        faulty_df['P_Rank'] = faulty_df['Priority_Level'].apply(sort_priority)
        faulty_df.sort_values(by=['P_Rank', 'Est_Loss_kW'], ascending=[True, False], inplace=True)

        wo_rows = []
        for idx, (_, r) in enumerate(faulty_df.iterrows(), 1):
            h_strings = f"PV{r['Open_Circuit_Strings']}" if r['Open_Circuit_Strings'] else ("Tất Cả" if r['Health_Status'] == 'CRITICAL' else "PV Lệch Dòng")
            tools = "Ampe kìm DC, Kìm bấm MC4, Bộ giắc MC4, VOM 1500V"
            if r['Health_Status'] == 'CRITICAL':
                tools = "Đồng hồ VOM, Bộ đàm, Máy tính lập trình SmartLogger, Kìm điện"
            elif 'Lệch Dòng' in r['Anomaly_Type']:
                tools = "Camera nhiệt FLIR, Dụng cụ rửa pin, Ampe kìm DC"

            wo_rows.append({
                'STT': idx,
                'Mức Độ Ưu Tiên': r['Priority_Level'],
                'Mã Inverter': r['Inverter_ID'],
                'Trạm Biến Áp': r['Station'],
                'Cấu Hình': f"{r['Installed_Strings']} String ({r['PV18_Note']})",
                'Chuỗi Bất Thường': h_strings,
                'Hiện Tượng Sự Cố': r['Anomaly_Type'],
                'Tổn Thất Ước Tính (kW)': r['Est_Loss_kW'],
                'Chẩn Đoán Nguyên Nhân Gốc': r['Root_Cause'],
                'Biện Pháp Xử Lý Kỹ Thuật': r['Action_Recommendation'],
                'Dụng Cụ Cần Mang Theo': tools,
                'Trạng Thái O&M': 'Chưa Xử Lý (Pending)'
            })

        return pd.DataFrame(wo_rows)

    def compare_snapshots(self, snap_path_1: str, snap_path_2: str) -> Dict[str, Any]:
        """So sánh biến động sự cố giữa 2 Snapshot thời gian (Snapshot Delta)"""
        df1 = self.load_string_data(target_dir=snap_path_1, force_reload=True)
        df2 = self.load_string_data(target_dir=snap_path_2, force_reload=True)

        if df1.empty or df2.empty:
            return {'status': 'error', 'message': 'Không thể đọc dữ liệu từ một trong hai snapshot'}

        records1 = df1.to_dict('records')
        records2 = df2.to_dict('records')
        dict1 = {r['Inverter_ID']: r for r in records1}
        dict2 = {r['Inverter_ID']: r for r in records2}

        all_inv_ids = sorted(list(set(dict1.keys()) & set(dict2.keys())))

        new_faults = []
        recovered_strings = []
        persistent_faults = []

        for inv_id in all_inv_ids:
            r1 = dict1[inv_id]
            r2 = dict2[inv_id]

            has_pv18 = r2.get('Has_PV18', True)
            chk_len = 17 if not has_pv18 else 18

            i_list1 = r1['Ipv_List']
            i_list2 = r2['Ipv_List']

            for pv_idx in range(chk_len):
                pv_num = pv_idx + 1
                i1 = float(i_list1[pv_idx])
                i2 = float(i_list2[pv_idx])

                is_dead1 = (i1 <= 0.05)
                is_dead2 = (i2 <= 0.05)

                if not is_dead1 and is_dead2:
                    new_faults.append({
                        'Inverter_ID': inv_id,
                        'Station': r2['Station_Tag'],
                        'String': f"PV{pv_num}",
                        'I_Truoc (A)': round(i1, 2),
                        'I_Sau (A)': round(i2, 2),
                        'U_Sau (V)': round(r2['Upv_List'][pv_idx], 1),
                        'Mo_Ta': 'Mới phát sinh mất dòng / hở mạch'
                    })
                elif is_dead1 and not is_dead2:
                    recovered_strings.append({
                        'Inverter_ID': inv_id,
                        'Station': r2['Station_Tag'],
                        'String': f"PV{pv_num}",
                        'I_Truoc (A)': round(i1, 2),
                        'I_Sau (A)': round(i2, 2),
                        'U_Sau (V)': round(r2['Upv_List'][pv_idx], 1),
                        'Mo_Ta': 'Đã được phục hồi phát điện'
                    })
                elif is_dead1 and is_dead2:
                    persistent_faults.append({
                        'Inverter_ID': inv_id,
                        'Station': r2['Station_Tag'],
                        'String': f"PV{pv_num}",
                        'I_Sau (A)': round(i2, 2),
                        'U_Sau (V)': round(r2['Upv_List'][pv_idx], 1),
                        'Mo_Ta': 'Lỗi kinh niên (Chưa được sửa)'
                    })

        return {
            'status': 'success',
            'new_faults_count': len(new_faults),
            'recovered_count': len(recovered_strings),
            'persistent_count': len(persistent_faults),
            'df_new_faults': pd.DataFrame(new_faults),
            'df_recovered': pd.DataFrame(recovered_strings),
            'df_persistent': pd.DataFrame(persistent_faults)
        }


def export_om_work_order_excel(wo_df: pd.DataFrame, plant_kpis: Dict[str, Any], snap_label: str = "") -> bytes:
    """Xuất Phiếu Giao Việc O&M Hiện Trường Chuẩn Kỹ Thuật (Excel)"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        wo_exp = wo_df[[
            'STT', 'Mức Độ Ưu Tiên', 'Mã Inverter', 'Trạm Biến Áp', 'Cấu Hình',
            'Chuỗi Bất Thường', 'Hiện Tượng Sự Cố', 'Tổn Thất Ước Tính (kW)',
            'Chẩn Đoán Nguyên Nhân Gốc', 'Biện Pháp Xử Lý Kỹ Thuật', 'Dụng Cụ Cần Mang Theo', 'Trạng Thái O&M'
        ]].copy()
        wo_exp.to_excel(writer, sheet_name='Phieu_Lenh_OM_Hien_Truong', index=False)

        checklist = wo_df[['STT', 'Mã Inverter', 'Trạm Biến Áp', 'Chuỗi Bất Thường', 'Biện Pháp Xử Lý Kỹ Thuật']].copy()
        checklist['Kỹ Thuật Viên Thực Hiện'] = ""
        checklist['Thời Gian Bắt Đầu'] = ""
        checklist['Thời Gian Hoàn Thành'] = ""
        checklist['Dòng Đo Sau Xử Lý (A)'] = ""
        checklist['Xác Nhận Trưởng Ca (Ký)'] = ""
        checklist.to_excel(writer, sheet_name='Bien_Ban_Nghiem_Thu', index=False)

    return output.getvalue()


def export_string_diagnostics_to_excel_bytes(df: pd.DataFrame, kpis: Dict[str, Any], date_label: str = "") -> bytes:
    """Xuất báo cáo chi tiết 229 Inverter & 4.058 chuỗi String DC ra file Excel 5 sheets"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        kpi_data = [
            {'Chỉ Số Giám Sát String': 'Thời Điểm Xuất Báo Cáo', 'Giá Trị': date_label},
            {'Chỉ Số Giám Sát String': 'Tổng Số Inverter Toàn Nhà Máy', 'Giá Trị': f"{kpis.get('total_inverters', 229)} Inverter (S1..S5: 35, S6: 36, S7: 18)"},
            {'Chỉ Số Giám Sát String': 'Số Inverter Hòa Lưới (On-grid)', 'Giá Trị': kpis.get('on_grid_inverters', 0)},
            {'Chỉ Số Giám Sát String': 'Số Inverter Nghỉ / Mất Kết Nối / Thiếu Dữ Liệu', 'Giá Trị': kpis.get('offline_inverters', 0)},
            {'Chỉ Số Giám Sát String': 'Tổng Số Chuỗi String Thiết Kế Thực Tế', 'Giá Trị': f"{kpis.get('total_installed_strings', 4058)} Chuỗi (64 INV x 17S + 165 INV x 18S)"},
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

        df_inv_exp = df[[
            'Inverter_ID', 'Station', 'SN', 'Device_Status', 'Health_Status', 'Priority_Level',
            'Installed_Strings', 'PV18_Note', 'Active_Strings', 'Dead_Strings_Count', 'Open_Circuit_Count', 'Low_I_Count',
            'Total_Pdc_kW', 'Est_Loss_kW', 'Avg_Voltage_V', 'Avg_Current_A', 'Imbalance_Pct', 'Root_Cause', 'Action_Recommendation'
        ]].copy()
        df_inv_exp.columns = [
            'Mã Inverter', 'Trạm Biến Áp', 'Serial Number', 'Trạng Thái Máy', 'Đánh Giá Sức Khỏe', 'Mức Độ Ưu Tiên O&M',
            'Số String Thiết Kế (17/18)', 'Ghi Chú PV18', 'String Đang Phát', 'String Hỏng', 'String Hở Mạch (I=0, U>300V)', 'String Lệch Dòng',
            'Công Suất DC (kW)', 'Tổn Thất Ước Tính (kW)', 'Điện Áp TB (V)', 'Dòng Điện TB (A)', 'Độ Lệch Dòng (%)', 'Chẩn Đoán Nguyên Nhân Gốc', 'Khuyến Nghị Xử Lý O&M'
        ]
        df_inv_exp.to_excel(writer, sheet_name='Danh_Sach_229_Inverter', index=False)

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
        pd.DataFrame(matrix_rows).to_excel(writer, sheet_name='Ma_Tran_4058_Strings', index=False)

        mppt_rows = []
        for _, r in df.iterrows():
            for mp in r['MPPT_Details']:
                mppt_rows.append({
                    'Mã Inverter': r['Inverter_ID'],
                    'Trạm': r['Station_Tag'],
                    'MPPT': f"MPPT {mp['mppt']}",
                    'Cặp Chuỗi': f"{mp['pv_a']} & {mp['pv_b']}",
                    'Dòng I_A (A)': mp['i_a'],
                    'Áp U_A (V)': mp['u_a'],
                    'Dòng I_B (A)': mp['i_b'],
                    'Áp U_B (V)': mp['u_b'],
                    'Độ Lệch Dòng (A)': mp['diff_i'],
                    'Lệch Cặp (%)': f"{mp['mismatch_pct']}%",
                    'Đánh Giá MPPT': mp['status']
                })
        pd.DataFrame(mppt_rows).to_excel(writer, sheet_name='Phan_Tich_9_MPPT', index=False)

        mgr_tmp = StringDataManager()
        wo_df = mgr_tmp.get_om_work_orders(df)
        if not wo_df.empty:
            wo_df.to_excel(writer, sheet_name='Phieu_Lenh_OM_Hien_Truong', index=False)

    return output.getvalue()
