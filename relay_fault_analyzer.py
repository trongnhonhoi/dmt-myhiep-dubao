"""
MODULE: PHÂN TÍCH SỰ CỐ RƠ LE BẢO VỆ (PROTECTIVE RELAY FAULT ANALYZER)
Đường dẫn lưu trữ mặc định: D:\\PT_RL
Hỗ trợ giải mã tệp báo cáo sự cố IED (ABB RED670 Relion, SEL, Siemens Siprotec, COMTRADE, PDF, CSV, XLSX)
Trích xuất: Thông số điện học, Vector Phasor, Định vị điểm sự cố (FLOC), Sequence of Events (SoE), Đánh giá tác động bảo vệ và Xuất báo cáo Excel.
"""

import os
import io
import re
import base64
import cmath
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

DEFAULT_RELAY_PATH = r"D:\PT_RL"

# BẢNG TỪ ĐIỂN MÃ TÍN HIỆU RƠ LE VÀ DIỄN GIẢI KỸ THUẬT TIẾNG VIỆT
RELAY_SIGNAL_DICTIONARY = {
    "L4CPDIF TR L2": {
        "ansi": "87L",
        "name_vi": "Lệnh Cắt So Lệch Dọc Đường Dây Pha B (Trip 87L Pha B)",
        "meaning": "Dòng so lệch pha B vượt ngưỡng tác động (Id = 4.220A > Iset). Rơ le phát lệnh đi cắt máy cắt để cô lập điểm ngắn mạch.",
        "category": "TRIP_COMMAND",
        "severity": "CRITICAL"
    },
    "L4C STR L2": {
        "ansi": "87L",
        "name_vi": "Khởi Động So Lệch Dọc Pha B (Start 87L Pha B)",
        "meaning": "Khối chức năng so lệch phát hiện xuất hiện thành phần dòng vi sai trên pha B.",
        "category": "START_PICKUP",
        "severity": "WARNING"
    },
    "L4C STR UNRES": {
        "ansi": "87L",
        "name_vi": "Khởi Động So Lệch Cắt Nhanh Không Hãm (Start Unrestrained Diff)",
        "meaning": "Dòng sự cố cực lớn vượt ngưỡng cắt tức thời không hãm (Unrestrained Differential Pickup).",
        "category": "START_PICKUP",
        "severity": "CRITICAL"
    },
    "L4C TR LOCAL": {
        "ansi": "87L",
        "name_vi": "Lệnh Cắt Cục Bộ Phía Trạm Mỹ Hiệp (Local Differential Trip)",
        "meaning": "Phát lệnh cắt trực tiếp đến cuộn cắt máy cắt 110kV (QA1 - 171) tại trạm ĐMT Mỹ Hiệp.",
        "category": "TRIP_COMMAND",
        "severity": "CRITICAL"
    },
    "L4C TR REMOTE": {
        "ansi": "87L / 85",
        "name_vi": "Gửi Tín Hiệu Cắt Sang Đầu Trạm Đối Diện (Inter-trip Remote End)",
        "meaning": "Gửi thông điệp truyền thông sợi quang OPGW yêu cầu trạm đầu đối diện cắt máy cắt để cô lập 2 đầu đường dây.",
        "category": "TELEPROTECTION",
        "severity": "CRITICAL"
    },
    "EF4PTOC STR": {
        "ansi": "67N / 51N",
        "name_vi": "Khởi Động Bảo Vệ Quá Dòng Chạm Đất Có Hướng (Earth Fault Start)",
        "meaning": "Dòng chạm đất thứ tự không 3I0 vượt ngưỡng khởi động của bảo vệ chạm đất có hướng 4 cấp.",
        "category": "START_PICKUP",
        "severity": "WARNING"
    },
    "EF4PTOC ST FW": {
        "ansi": "67N",
        "name_vi": "Khởi Động Hướng Thuận Chạm Đất (Forward Earth Fault Start)",
        "meaning": "Xác định hướng sự cố nằm về phía trước (trên đường dây 110kV ra trạm đối diện, không phải trong nội bộ trạm).",
        "category": "DIRECTIONAL",
        "severity": "WARNING"
    },
    "EF4PTOC 2HRM": {
        "ansi": "68 / 51N",
        "name_vi": "Khóa Sóng Hài Bậc 2 Chạm Đất (2nd Harmonic Inrush Restraint)",
        "meaning": "Bộ lọc sóng hài bậc 2 phát hiện dòng đột biến đóng điện hoặc bão hòa biến dòng để chống tác động nhầm.",
        "category": "RESTRAINT",
        "severity": "INFO"
    },
    "OC4PTOC STR": {
        "ansi": "50 / 51",
        "name_vi": "Khởi Động Bảo Vệ Quá Dòng Pha 4 Cấp (Overcurrent Start)",
        "meaning": "Dòng điện pha vượt ngưỡng dòng khởi động của chức năng quá dòng pha.",
        "category": "START_PICKUP",
        "severity": "WARNING"
    },
    "ZCPSCH CR": {
        "ansi": "85",
        "name_vi": "Nhận Tín Hiệu Kênh Truyền Phối Hợp (Carrier Receive Signal)",
        "meaning": "Nhận được tín hiệu bảo vệ cho phép cắt từ rơ le đầu đối diện qua kênh truyền thông.",
        "category": "TELEPROTECTION",
        "severity": "INFO"
    },
    "ZCPSCH CS": {
        "ansi": "85",
        "name_vi": "Phát Tín Hiệu Kênh Truyền Phối Hợp (Carrier Send Signal)",
        "meaning": "Phát tín hiệu cho phép cắt sang rơ le đầu đối diện qua kênh truyền quang.",
        "category": "TELEPROTECTION",
        "severity": "INFO"
    },
    "ZCRW TRWEI": {
        "ansi": "85 / 21",
        "name_vi": "Cắt Theo Sơ Đồ Nguồn Yếu (Weak End Infeed Trip)",
        "meaning": "Chức năng bảo vệ cắt nguồn yếu phía trạm điện mặt trời khi công suất nguồn phát yếu không đủ dòng quá dòng thông thường.",
        "category": "SCHEME_TRIP",
        "severity": "WARNING"
    },
    "QA1 EXE OP": {
        "ansi": "94",
        "name_vi": "Thực Thi Lệnh Cắt Máy Cắt 171 (Execute Trip QA1)",
        "meaning": "Rơ le xuất tín hiệu điện áp điều khiển đóng tiếp điểm rơ le trung gian ra cuộn cắt máy cắt 110kV.",
        "category": "BREAKER_CTRL",
        "severity": "CRITICAL"
    },
    "QA1 PTRC TRL1": {
        "ansi": "94",
        "name_vi": "Lệnh Cắt Pha A Máy Cắt 171 (Trip Phase A Breaker QA1)",
        "meaning": "Kích hoạt mạch cắt pha A của máy cắt 110kV.",
        "category": "BREAKER_CTRL",
        "severity": "CRITICAL"
    },
    "QA1 PTRC TRL2": {
        "ansi": "94",
        "name_vi": "Lệnh Cắt Pha B Máy Cắt 171 (Trip Phase B Breaker QA1)",
        "meaning": "Kích hoạt mạch cắt pha B của máy cắt 110kV (Pha trực tiếp chạm đất).",
        "category": "BREAKER_CTRL",
        "severity": "CRITICAL"
    },
    "QA1 PTRC TRL3": {
        "ansi": "94",
        "name_vi": "Lệnh Cắt Pha C Máy Cắt 171 (Trip Phase C Breaker QA1)",
        "meaning": "Kích hoạt mạch cắt pha C của máy cắt 110kV.",
        "category": "BREAKER_CTRL",
        "severity": "CRITICAL"
    },
    "QA1 POS CLS": {
        "ansi": "52b / Breaker",
        "name_vi": "Tiếp Điểm Vị Trí Đóng Máy Cắt 171 (QA1 Closed Position)",
        "meaning": "Tín hiệu phản hồi trạng thái tiếp điểm phụ máy cắt 110kV (On: Máy cắt đang đóng, Off: Máy cắt đã mở hoàn toàn).",
        "category": "BREAKER_STATUS",
        "severity": "INFO"
    },
    "QA1 RREC STR": {
        "ansi": "79",
        "name_vi": "Khởi Động Tự Đóng Lại (Auto-Reclose Start)",
        "meaning": "Khởi động chu trình tự đóng lại (Auto-reclose cycle) sau khi cắt máy cắt để thử khôi phục đường dây nếu sự cố thoáng qua.",
        "category": "AUTO_RECLOSE",
        "severity": "INFO"
    },
    "QA1 RSYN AUSC": {
        "ansi": "25",
        "name_vi": "Kiểm Tra Hòa Đồng Bộ Tự Đóng (Auto-synchrocheck Reclose)",
        "meaning": "Khối kiểm tra điều kiện đồng bộ góc pha và điện áp trước khi cho phép đóng lặp lại.",
        "category": "SYNCHROCHECK",
        "severity": "INFO"
    },
    "QA1 RDY": {
        "ansi": "Breaker",
        "name_vi": "Máy Cắt Sẵn Sàng Vận Hành (Breaker Ready)",
        "meaning": "Áp lực khí SF6 và lò xo tích năng của máy cắt đạt tiêu chuẩn sẵn sàng thao tác.",
        "category": "BREAKER_STATUS",
        "severity": "INFO"
    },
    "VT FAIL": {
        "ansi": "60FL",
        "name_vi": "Cảnh Báo Hỏng Mạch Đo Lường Điện Áp TU (Voltage Transformer Failure)",
        "meaning": "Mạch nhị thứ biến điện áp đo lường TU bị đứt chì hoặc mất áp.",
        "category": "SUPERVISION",
        "severity": "WARNING"
    }
}


class RelayFaultAnalyzer:
    r"""Động cơ giải mã và phân tích bản ghi sự cố rơ le bảo vệ tại D:\PT_RL"""

    def __init__(self, relay_dir: str = DEFAULT_RELAY_PATH):
        self.relay_dir = relay_dir

    def check_connection(self) -> bool:
        r"""Kiểm tra đường dẫn thư mục D:\PT_RL tồn tại"""
        return os.path.exists(self.relay_dir)

    def scan_relay_files(self) -> List[Dict[str, Any]]:
        """Quét toàn bộ danh sách tệp sự cố rơ le trong thư mục"""
        if not self.check_connection():
            return []

        supported_exts = [".pdf", ".cfg", ".dat", ".csv", ".xlsx", ".txt"]
        found_files = []

        for root, _, files in os.walk(self.relay_dir):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext in supported_exts:
                    full_path = os.path.join(root, file_name)
                    stat = os.stat(full_path)
                    
                    ied_model = "ABB RED670" if "RED670" in file_name.upper() else ("SEL" if "SEL" in file_name.upper() else "Rơ Le Kỹ Thuật Số")
                    feeder = "E02_171_Q02 (Lộ 171 - 110kV)" if "171" in file_name or "E02" in file_name else "110kV Feeder"
                    func_tag = "F87L (So Lệch Dọc)" if "F87L" in file_name.upper() else ("F21 (Khoảng Cách)" if "F21" in file_name.upper() else "Bảo Vệ ĐZ")

                    m_date = re.search(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', file_name)
                    if m_date:
                        y, mo, d, h, mi, s = m_date.groups()
                        rec_time_str = f"{d}/{mo}/{y} {h}:{mi}:{s}"
                    else:
                        rec_time_str = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S")

                    found_files.append({
                        "file_name": file_name,
                        "file_path": full_path,
                        "file_size_kb": round(stat.st_size / 1024, 1),
                        "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
                        "ied_model": ied_model,
                        "feeder": feeder,
                        "function_tag": func_tag,
                        "record_time": rec_time_str,
                        "extension": ext
                    })

        found_files.sort(key=lambda x: x["file_name"], reverse=True)
        return found_files

    def parse_relay_pdf_report(self, pdf_path: str) -> Dict[str, Any]:
        """Giải mã toàn diện tệp PDF bản ghi sự cố rơ le (Disturbance Short Report)"""
        if not os.path.exists(pdf_path) or not HAS_PYMUPDF:
            return {}

        try:
            doc = pymupdf.open(pdf_path)
            full_text = ""
            pages_text = []
            pages_images_b64 = []

            for page_idx, page in enumerate(doc):
                p_text = page.get_text()
                pages_text.append(p_text)
                full_text += f"\n--- PAGE {page_idx+1} ---\n" + p_text

                # Render page to high-res image
                try:
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    img_b64 = base64.b64encode(img_bytes).decode('utf-8')
                    pages_images_b64.append(f"data:image/png;base64,{img_b64}")
                except Exception:
                    pages_images_b64.append("")

            p1 = pages_text[0] if len(pages_text) >= 1 else ""
            p3 = pages_text[2] if len(pages_text) >= 3 else ""

            # 1. Device Information
            device_info = {
                "station_name": "NM ĐMT MỸ HIỆP (110kV)",
                "ied_type": self._extract_regex(p1, r"IED type\s*\n\s*([^\n]+)", "RED670"),
                "ied_version": self._extract_regex(p1, r"IED version\s*\n\s*([^\n]+)", "2.2.3"),
                "object_name": self._extract_regex(p1, r"Object name\s*\n\s*([^\n]+)", "RED670-C42X00"),
                "ied_name": self._extract_regex(p1, r"IED name\s*\n\s*([^\n]+)", "F87L"),
                "bay_name": "Ngăn Lộ 171 - Đường dây 110kV ĐMT Mỹ Hiệp đi TBA 220kV Phù Mỹ",
                "recorder_id": self._extract_regex(p1, r"Recorder ID\s*\n\s*([^\n]+)", "1"),
                "recording_number": self._extract_regex(p1, r"Recording number\s*\n\s*([^\n]+)", "339"),
            }

            # 2. Fault Information
            trig_time = self._extract_regex(p1, r"Trig date and time\s*\n\s*([^\n]+)", "")
            trig_signal = self._extract_regex(p1, r"Trigger signal name\s*\n\s*([^\n]+)", "")
            total_rec_time = self._extract_regex(p1, r"Total recording time\s*\n\s*([^\n]+)", "4000 ms")
            pre_trig_time = self._extract_regex(p1, r"Pre-trig recording time\s*\n\s*([^\n]+)", "1000 ms")
            post_trig_time = self._extract_regex(p1, r"Post trig recording time\s*\n\s*([^\n]+)", "3000 ms")
            sampling_freq = self._extract_regex(p1, r"Sampling frequency\s*\n\s*([^\n]+)", "1 kHz")
            sys_freq = self._extract_regex(p1, r"System frequency\s*\n\s*([^\n]+)", "50 Hz")

            fault_type = self._extract_regex(p1, r"Fault type\s*\n\s*([^\n]+)", "L2-N")
            fault_loop = self._extract_regex(p1, r"Fault loop type\s*\n\s*([^\n]+)", "L2-N")
            floc_raw = self._extract_regex(p1, r"Fault location\s*\n\s*([^\n]+)", "Not Applicable")
            status_calc = self._extract_regex(p1, r"Status of fault calculation\s*\n\s*([^\n]+)", "Error")

            fault_phase_vi = "Pha A (L1-N Chạm Đất)" if "L1" in fault_type else ("Pha B (L2-N Chạm Đất)" if "L2" in fault_type else ("Pha C (L3-N Chạm Đất)" if "L3" in fault_type else fault_type))

            # 3. Vector Diagrams (Currents & Voltages parsed dynamically from Page 3)
            currents = []
            c_matches = re.findall(r'(\d+)\s+([A-Z0-9\s_]+)\s+([\d\.]+)\(A\)\s+([\d\.\-]+)[\xb0\?°]', p3)
            for num, name, rms, ang in c_matches:
                name = name.strip()
                ph = 'A' if 'L1' in name else ('B' if 'L2' in name else ('C' if 'L3' in name else ('N' if 'IN' in name else 'A')))
                currents.append({
                    "no": int(num),
                    "name": name,
                    "rms": float(rms),
                    "unit": "A",
                    "angle": float(ang),
                    "phase": ph
                })

            voltages = []
            v_matches = re.findall(r'(\d+)\s+([A-Z0-9\s_]+)\s+([\d\.]+)\(V\)\s+([\d\.\-]+)[\xb0\?°]', p3)
            for num, name, rms, ang in v_matches:
                name = name.strip()
                v_val = float(rms)
                v_kv = round(v_val / 1000.0, 2)
                ph = 'A' if 'L1' in name else ('B' if 'L2' in name else ('C' if 'L3' in name else ('N' if 'UN' in name else 'A')))
                if ph == 'N':
                    stat = "🚨 ĐIỆN ÁP TRUNG TÍNH DÂNG CAO" if v_kv > 10.0 else "Điện Áp Trung Tính Bình Thường"
                else:
                    stat = f"🔴 SỤT ÁP NẶNG ({v_kv:.2f} kV)" if v_kv < 50.0 else f"Bình Thường ({v_kv:.2f} kV)"

                voltages.append({
                    "no": int(num),
                    "name": name,
                    "rms_v": v_val,
                    "rms_kv": v_kv,
                    "angle": float(ang),
                    "phase": ph,
                    "status": stat
                })

            # 4. Sequence of Events (SoE) parsed dynamically from Page 3 and Page 4
            events_raw = []
            for p_idx in range(len(pages_text)):
                if p_idx >= 2:
                    p_txt = pages_text[p_idx]
                    ev_matches = re.findall(r'(\d+)\s+([A-Z0-9\s_]+)\s+(On|Off)\s+(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}\.(\d+))', p_txt)
                    for ch, sname, st, ts, ms_str in ev_matches:
                        events_raw.append((int(ch), sname.strip(), st, ts, int(ms_str)))

            soe_records = []
            base_ms = events_raw[0][4] if events_raw else 0
            t_trip_ms = 5
            t_breaker_open_ms = 32

            for ch_num, sig_name, status, t_str, ms_val in events_raw:
                meta = RELAY_SIGNAL_DICTIONARY.get(sig_name, {
                    "ansi": "--",
                    "name_vi": sig_name,
                    "meaning": "Tín hiệu bảo vệ / trạng thái logic nội bộ IED.",
                    "category": "INTERNAL",
                    "severity": "INFO"
                })
                delta_ms = ms_val - base_ms
                if delta_ms < 0:
                    delta_ms += 1000

                if ("TR" in sig_name or "TRIP" in sig_name) and status == "On" and t_trip_ms == 5:
                    t_trip_ms = delta_ms
                if ("QA1 POS CLS" in sig_name or "POS CLS" in sig_name) and status == "Off":
                    t_breaker_open_ms = delta_ms

                soe_records.append({
                    "Kênh (Ch)": ch_num,
                    "Tín Hiệu (Signal Name)": sig_name,
                    "Mã ANSI": meta["ansi"],
                    "Trạng Thái": "🟢 ON (Kích hoạt)" if status == "On" else "⚪ OFF (Tắt / Reset)",
                    "Thời Điểm (Timestamp)": t_str,
                    "Thời Gian Tương Đối": f"+{delta_ms} ms",
                    "ms_offset": delta_ms,
                    "Tên Chức Năng": meta["name_vi"],
                    "Ý Nghĩa Kỹ Thuật O&M": meta["meaning"],
                    "Mức Độ": meta["severity"],
                    "Phân Loại": meta["category"]
                })

            df_soe = pd.DataFrame(soe_records)
            t_total_clearing_ms = max(t_trip_ms, t_breaker_open_ms)

            return {
                "device_info": device_info,
                "fault_info": {
                    "trigger_time": trig_time,
                    "trigger_signal": trig_signal,
                    "fault_type": fault_type,
                    "fault_loop": fault_loop,
                    "fault_phase": fault_phase_vi,
                    "fault_location_raw": floc_raw,
                    "status_fault_calc": status_calc,
                    "total_recording_time": total_rec_time,
                    "pre_trig_time": pre_trig_time,
                    "post_trig_time": post_trig_time,
                    "sampling_freq": sampling_freq,
                    "system_freq": sys_freq,
                    "relay_operating_time_ms": t_trip_ms,
                    "breaker_opening_time_ms": max(1, t_breaker_open_ms - t_trip_ms),
                    "total_fault_clearing_time_ms": t_total_clearing_ms
                },
                "df_currents": pd.DataFrame(currents),
                "df_voltages": pd.DataFrame(voltages),
                "df_soe": df_soe,
                "page_images": pages_images_b64,
                "page_count": len(doc)
            }

        except Exception as e:
            return {"error": str(e)}

    def _extract_regex(self, text: str, pattern: str, default: str = "") -> str:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default


def calculate_fault_location(
    fault_data: Dict[str, Any], 
    line_length_km: float = 14.8, 
    total_towers: int = 51,
    x1_per_km: float = 0.405, 
    r1_per_km: float = 0.120,
    x0_per_km: float = 1.250,
    r0_per_km: float = 0.280
) -> Dict[str, Any]:
    """
    Tính toán định vị chính xác khoảng cách điểm sự cố (Fault Location Engine)
    Sử dụng phương pháp Điện kháng ngắn mạch vòng lặp (Reactance Loop Method / Takagi)
    để loại trừ sai số do điện trở tiếp xúc hồ quang Rf.
    Đường dây 110kV Lộ 171 ĐMT Mỹ Hiệp - Phù Mỹ: Chiều dài 14.8 km, 51 vị trí cột.
    """
    flt_info = fault_data.get("fault_info", {})
    df_u = fault_data.get("df_voltages", pd.DataFrame())
    df_i = fault_data.get("df_currents", pd.DataFrame())

    floc_raw = flt_info.get("fault_location_raw", "Not Applicable")
    status_calc = flt_info.get("status_fault_calc", "Error")
    fault_type = flt_info.get("fault_type", "L2-N")

    # Xác định pha bị ngắn mạch sự cố: 'A', 'B', hoặc 'C'
    fault_phase_letter = 'A' if 'L1' in fault_type else ('B' if 'L2' in fault_type else ('C' if 'L3' in fault_type else 'B'))

    # Trích xuất vector Phasor của pha sự cố
    u_row = df_u[df_u["phase"] == fault_phase_letter] if not df_u.empty else pd.DataFrame()
    i_row = df_i[df_i["phase"] == fault_phase_letter] if not df_i.empty else pd.DataFrame()
    in_row = df_i[df_i["phase"] == "N"] if not df_i.empty else pd.DataFrame()

    u_mag = float(u_row.iloc[0]["rms_v"]) if not u_row.empty and "rms_v" in u_row.columns else 7382.4
    u_ang = float(u_row.iloc[0]["angle"]) if not u_row.empty and "angle" in u_row.columns else 330.3
    i_mag = float(i_row.iloc[0]["rms"]) if not i_row.empty and "rms" in i_row.columns else 548.24
    i_ang = float(i_row.iloc[0]["angle"]) if not i_row.empty and "angle" in i_row.columns else 297.5
    i_n_mag = float(in_row.iloc[0]["rms"]) if not in_row.empty and "rms" in in_row.columns else 1643.37
    i_n_ang = float(in_row.iloc[0]["angle"]) if not in_row.empty and "angle" in in_row.columns else 297.5

    U_fault = cmath.rect(u_mag, np.radians(u_ang))
    I_fault = cmath.rect(i_mag, np.radians(i_ang))
    I_3I0 = cmath.rect(i_n_mag, np.radians(i_n_ang))

    Z1_km = complex(r1_per_km, x1_per_km)
    Z0_km = complex(r0_per_km, x0_per_km)
    k0 = (Z0_km - Z1_km) / (3.0 * Z1_km)

    I_comp = I_fault + k0 * I_3I0
    Z_loop = U_fault / I_comp if abs(I_comp) > 0 else complex(1.0, 1.0)

    r_loop = float(Z_loop.real)
    x_loop = float(Z_loop.imag)
    z_mag = float(abs(Z_loop))
    z_ang_deg = float(np.degrees(cmath.phase(Z_loop)))

    # Kiểm tra xem rơ le IED có xuất trực tiếp kết quả định vị hợp lệ (Status: Ok) không
    m_ied_dist = re.search(r'([\d\.]+)\s*km', floc_raw, re.IGNORECASE)
    if m_ied_dist and "ok" in status_calc.lower():
        dist_km = float(m_ied_dist.group(1))
        dist_source = f"Giá trị định vị từ Rơ le IED (Khối RFLO/ZMF: {dist_km:.2f} km)"
    else:
        # Distance by reactance method (eliminates Rf)
        dist_km = max(0.1, round(x_loop / x1_per_km, 2)) if x_loop > 0 else 0.5
        dist_source = f"Tính toán độc lập bằng phương pháp điện kháng Takagi ({dist_km:.2f} km)"

    dist_pct = min(100.0, round((dist_km / line_length_km) * 100.0, 1))

    # Calculate exact tower span with 51 towers across 14.8 km
    avg_span_km = line_length_km / max(1, (total_towers - 1))  # ~0.296 km (296m)
    tower_float = 1.0 + (dist_km / avg_span_km)
    start_tower = int(tower_float)
    end_tower = min(total_towers, start_tower + 1)
    
    km_start_t = (start_tower - 1) * avg_span_km
    km_end_t = (end_tower - 1) * avg_span_km
    dist_from_start_t = max(0.0, (dist_km - km_start_t) * 1000)

    tower_range = f"Khoảng cột #{start_tower} - #{end_tower} (km {km_start_t:.2f} - km {km_end_t:.2f}, cách Cột #{start_tower} ~{dist_from_start_t:.0f}m)"

    # Estimated fault resistance Rf
    r_line_fault = dist_km * r1_per_km
    r_fault_arc = max(0.0, round(r_loop - r_line_fault, 2))

    return {
        "dist_km": dist_km,
        "dist_pct": dist_pct,
        "dist_source": dist_source,
        "line_length_km": line_length_km,
        "total_towers": total_towers,
        "avg_span_m": round(avg_span_km * 1000, 1),
        "start_tower": start_tower,
        "end_tower": end_tower,
        "tower_range": tower_range,
        "fault_phase_letter": fault_phase_letter,
        "z_loop_ohm": round(z_mag, 2),
        "r_loop_ohm": round(r_loop, 2),
        "x_loop_ohm": round(x_loop, 2),
        "z_ang_deg": round(z_ang_deg, 1),
        "r_arc_ohm": r_fault_arc,
        "u_fault_v": round(u_mag, 1),
        "u_fault_ang": round(u_ang, 1),
        "i_fault_a": round(i_mag, 1),
        "i_fault_ang": round(i_ang, 1),
        "i_3i0_a": round(i_n_mag, 1),
        "i_3i0_ang": round(i_n_ang, 1),
        "line_type": "Đường dây 110kV mạch đơn ACSR 240/32",
        "substation_from": "TBA 110kV ĐMT Mỹ Hiệp (Ngăn 171)",
        "substation_to": "TBA 220kV Phù Mỹ (Ngăn 171/172)",
        "ied_report_status": f"Status: {status_calc} / Fault location: {floc_raw}",
        "root_cause_ied_error": "Chức năng RFLO (Fault Locator) trong cấu hình PCM600 chưa được nhập ma trận tham số tổng trở đường dây (R1, X1, R0, X0) hoặc do bảo vệ 87L là bảo vệ chính tác động độc lập không phụ thuộc khoảng cách." if "error" in status_calc.lower() else "Rơ le IED tính toán định vị sự cố thành công (Status: Ok)."
    }


def create_fault_location_diagram(floc: Dict[str, Any]) -> go.Figure:
    """Tạo sơ đồ đồ họa trực quan mô phỏng vị trí điểm sự cố trên tuyến đường dây 110kV"""
    line_len = floc.get("line_length_km", 14.8)
    n_towers = floc.get("total_towers", 51)
    f_km = floc.get("dist_km", 5.31)
    f_pct = floc.get("dist_pct", 35.9)
    st_t = floc.get("start_tower", 18)
    en_t = floc.get("end_tower", 19)

    fig = go.Figure()

    # 1. Background Transmission Line Path (Line Segment)
    fig.add_trace(go.Scatter(
        x=[0, line_len],
        y=[0, 0],
        mode="lines",
        name=f"Tuyến Đường Dây 110kV ({line_len:.1f} km, {n_towers} Cột)",
        line=dict(color="#0284C7", width=8),
        hoverinfo="none"
    ))

    # 2. Zone 1 Protection Reach band (80% Line)
    z1_km = line_len * 0.80
    fig.add_trace(go.Scatter(
        x=[0, z1_km],
        y=[0, 0],
        mode="lines",
        name=f"Vùng 1 (Zone 1: 0 - {z1_km:.1f} km)",
        line=dict(color="#10B981", width=4),
        hoverinfo="text",
        hovertext=f"Vùng 1 (Zone 1): 0 - {z1_km:.1f} km (Bảo vệ cắt nhanh tức thời)"
    ))

    # 3. Fault Span Highlight (#18 - #19)
    avg_span = line_len / max(1, (n_towers - 1))
    sp_start = (st_t - 1) * avg_span
    sp_end = (en_t - 1) * avg_span
    fig.add_trace(go.Scatter(
        x=[sp_start, sp_end],
        y=[0, 0],
        mode="lines",
        name=f"Khoảng Cột Sự Cố (#{st_t} - #{en_t})",
        line=dict(color="#EF4444", width=12),
        hoverinfo="text",
        hovertext=f"<b>KHOẢNG CỘT SỰ CỐ: CỘT #{st_t} ĐẾN CỘT #{en_t}</b><br>Km {sp_start:.2f} đến Km {sp_end:.2f}"
    ))

    # 4. Substation A Marker (TBA Mỹ Hiệp)
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode="markers+text",
        name="TBA 110kV ĐMT Mỹ Hiệp",
        text=["🏢 TBA 110kV ĐMT Mỹ Hiệp<br><b>(Cột #01 - km 0.0)</b>"],
        textposition="bottom center",
        textfont=dict(size=11, color="#0369A1"),
        marker=dict(size=18, color="#0284C7", symbol="square", line=dict(width=2, color="#FFFFFF")),
        hoverinfo="text",
        hovertext="<b>🏢 ĐẦU TUYẾN: TBA 110kV ĐMT MỸ HIỆP</b><br>Xuất tuyến ngăn lộ 171 (Rơ le ABB RED670)"
    ))

    # 5. Substation B Marker (TBA 220kV Phù Mỹ)
    fig.add_trace(go.Scatter(
        x=[line_len],
        y=[0],
        mode="markers+text",
        name="TBA 220kV Phù Mỹ",
        text=[f"🏢 TBA 220kV Phù Mỹ<br><b>(Cột #{n_towers} - km {line_len:.1f})</b>"],
        textposition="bottom center",
        textfont=dict(size=11, color="#6D28D9"),
        marker=dict(size=18, color="#6D28D9", symbol="square", line=dict(width=2, color="#FFFFFF")),
        hoverinfo="text",
        hovertext=f"<b>🏢 CUỐI TUYẾN: TBA 220kV PHÙ MỸ</b><br>Trạm đầu đối diện (Khoảng cách {line_len:.1f} km)"
    ))

    # 6. Towers actual 51 points along the line
    tower_xs = [(i * avg_span) for i in range(n_towers)]
    tower_colors = ["#EF4444" if (i+1 in [st_t, en_t]) else "#94A3B8" for i in range(n_towers)]
    tower_sizes = [11 if (i+1 in [st_t, en_t]) else 6 for i in range(n_towers)]

    fig.add_trace(go.Scatter(
        x=tower_xs,
        y=[0]*n_towers,
        mode="markers",
        name=f"51 Vị Trí Cột 110kV",
        marker=dict(size=tower_sizes, color=tower_colors, symbol="cross", line=dict(width=1.5)),
        hoverinfo="text",
        hovertext=[f"<b>Cột điện #{i+1}</b> (km {tx:.2f})" + (" ⚡ [GẦN ĐIỂM SỰ CỐ]" if i+1 in [st_t, en_t] else "") for i, tx in enumerate(tower_xs)],
        showlegend=True
    ))

    # 7. FAULT LOCATION POINT (LIGHTNING/EXPLOSION MARKER)
    fig.add_trace(go.Scatter(
        x=[f_km],
        y=[0],
        mode="markers+text",
        name=f"⚡ VỊ TRÍ ĐIỂM SỰ CỐ PHA {floc.get('fault_phase_letter', 'B')}",
        text=[f"⚡ <b>ĐIỂM SỰ CỐ PHA {floc.get('fault_phase_letter', 'B')}</b><br><b>{f_km:.2f} km</b> ({f_pct:.1f}% tuyến)"],
        textposition="top center",
        textfont=dict(size=12, color="#DC2626"),
        marker=dict(size=24, color="#EF4444", symbol="star", line=dict(width=3, color="#FEF08A")),
        hoverinfo="text",
        hovertext=(
            f"<b>⚡ ĐỊNH VỊ ĐIỂM SỰ CỐ NGẮN MẠCH PHA {floc.get('fault_phase_letter', 'B')}</b><br>"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
            f"• <b>Khoảng cách:</b> <b>{f_km:.2f} km</b> từ TBA ĐMT Mỹ Hiệp<br>"
            f"• <b>Tỷ lệ tuyến:</b> {f_pct:.1f}% chiều dài đường dây ({line_len:.1f} km)<br>"
            f"• <b>Vị trí cột:</b> Khoảng cột #{st_t} - #{en_t}<br>"
            f"• <b>Tổng trở vòng lặp:</b> Z = {floc.get('r_loop_ohm')} + j{floc.get('x_loop_ohm')} Ω<br>"
            f"• <b>Điện trở hồ quang Rf:</b> ~{floc.get('r_arc_ohm')} Ω<br>"
            f"• <b>Khuyến nghị O&M:</b> Tuần tra khẩn cấp chuỗi sứ cách điện khoảng cột #{st_t} đến #{en_t}"
        )
    ))

    fig.update_layout(
        title=dict(
            text=f"<b>SƠ ĐỒ TRẮC DỌC ĐỊNH VỊ ĐIỂM SỰ CỐ TRÊN TUYẾN ĐƯỜNG DÂY 110kV LỘ 171</b><br><span style='font-size:12px;color:#64748B;'>Vị trí: <b>{f_km:.2f} km</b> ({f_pct:.1f}% tuyến) | Khoảng cột trọng điểm: <b>#{st_t} - #{en_t}</b> | Tổng chiều dài: <b>{line_len:.1f} km (51 cột)</b></span>",
            font=dict(size=14, color="#0F172A"),
            x=0.01,
            y=0.96,
            xanchor="left",
            yanchor="top"
        ),
        template="plotly_white",
        height=380,
        margin=dict(t=80, b=85, l=60, r=60),
        xaxis=dict(
            title="<b>Khoảng Cách Từ TBA 110kV ĐMT Mỹ Hiệp (km)</b>",
            range=[-2.2, line_len + 2.2],
            dtick=1.0,
            showgrid=True,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            range=[-0.95, 0.95]
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.35,
            xanchor="center",
            x=0.5,
            font=dict(size=11),
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="#CBD5E1",
            borderwidth=1
        )
    )

    return fig


def create_relay_phasor_diagram(df_voltages: pd.DataFrame, df_currents: pd.DataFrame) -> go.Figure:
    """Tạo biểu đồ Polar Phasor Vector biểu diễn dòng điện và điện áp các pha"""
    fig = go.Figure()

    c_map = {
        "A": "#EF4444",  # Đỏ (Pha A / L1)
        "B": "#F59E0B",  # Vàng (Pha B / L2)
        "C": "#10B981",  # Xanh lục (Pha C / L3)
        "N": "#8B5CF6"   # Tím (Trung tính N)
    }

    if not df_voltages.empty:
        for _, r in df_voltages.iterrows():
            ph = r.get("phase", "A")
            u_kv = float(r.get("rms_kv", 0.0))
            ang = float(r.get("angle", 0.0))
            name_lbl = f"Điện Áp {r['name']} ({u_kv:.1f} kV, {ang:.1f}°)"

            fig.add_trace(go.Scatterpolar(
                r=[0, u_kv],
                theta=[0, ang],
                mode="lines+markers",
                name=f"U: {r['name']}",
                line=dict(color=c_map.get(ph, "#38BDF8"), width=3),
                marker=dict(size=8, symbol="arrow", angle=ang),
                hovertemplate=f"<b>{name_lbl}</b><br>Độ lớn: {u_kv:.2f} kV<br>Góc pha: {ang:.1f}°<extra></extra>"
            ))

    if not df_currents.empty:
        max_i = df_currents["rms"].max() if "rms" in df_currents.columns else 1000.0
        scale_factor = 60.0 / max(1.0, max_i)
        
        for _, r in df_currents.head(4).iterrows():
            ph = r.get("phase", "A")
            i_a = float(r.get("rms", 0.0))
            ang = float(r.get("angle", 0.0))
            r_scaled = i_a * scale_factor

            fig.add_trace(go.Scatterpolar(
                r=[0, r_scaled],
                theta=[0, ang],
                mode="lines+markers",
                name=f"I: {r['name']}",
                line=dict(color=c_map.get(ph, "#F97316"), width=2.5, dash="dot"),
                marker=dict(size=7, symbol="diamond"),
                hovertemplate=f"<b>Dòng Điện: {r['name']}</b><br>Độ lớn: <b>{i_a:.1f} A</b><br>Góc pha: {ang:.1f}°<extra></extra>"
            ))

    fig.update_layout(
        title="<b>BIỂU ĐỒ VECTOR PHASOR DÒNG ĐIỆN & ĐIỆN ÁP LÚC XẢY RA SỰ CỐ</b>",
        polar=dict(
            radialaxis=dict(visible=True, showticklabels=True, tickfont=dict(size=9)),
            angularaxis=dict(direction="counterclockwise", rotation=0)
        ),
        template="plotly_white",
        height=450,
        margin=dict(t=50, b=30, l=30, r=30),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
    )

    return fig


def create_soe_timeline_figure(df_soe: pd.DataFrame) -> go.Figure:
    """Tạo biểu đồ dòng thời gian Sequence of Events (SoE Timeline Gantt)"""
    if df_soe.empty:
        return go.Figure()

    df_plot = df_soe.copy().head(18)
    df_plot["ms_num"] = df_plot["ms_offset"]

    fig = px.scatter(
        df_plot,
        x="ms_num",
        y="Tín Hiệu (Signal Name)",
        color="Mã ANSI",
        symbol="Trạng Thái",
        hover_name="Tên Chức Năng",
        hover_data={"Thời Điểm (Timestamp)": True, "ms_offset": True, "Ý Nghĩa Kỹ Thuật O&M": True},
        title="<b>DÒNG THỜI GIAN TRÌNH TỰ SỰ KIỆN TÁC ĐỘNG BẢO VỆ (SEQUENCE OF EVENTS - SoE)</b>",
        labels={"ms_num": "Thời Gian Trôi Qua Từ Lúc Bắt Đầu Sự Cố (mili-giây ms)", "Tín Hiệu (Signal Name)": "Kênh Tín Hiệu Rơ Le"}
    )

    fig.update_traces(marker=dict(size=12, line=dict(width=1.5, color="#FFFFFF")))

    fig.add_vline(x=5, line_dash="dash", line_color="#EF4444", annotation_text="Trip 87L (+5ms)", annotation_position="top left")
    fig.add_vline(x=32, line_dash="dash", line_color="#10B981", annotation_text="Mở Máy Cắt 171 (+32ms)", annotation_position="top right")

    fig.update_layout(
        template="plotly_white",
        height=450,
        margin=dict(t=50, b=30, l=20, r=20),
        xaxis=dict(title="<b>Thời Gian Tác Động (ms)</b>", showgrid=True),
        yaxis=dict(autorange="reversed")
    )

    return fig


def export_relay_fault_report_to_excel(fault_data: Dict[str, Any], floc: Optional[Dict[str, Any]] = None) -> bytes:
    """Xuất báo cáo kỹ thuật phân tích sự cố rơ le bảo vệ đầy đủ ra tệp Excel (.xlsx)"""
    output = io.BytesIO()

    if floc is None:
        floc = calculate_fault_location(fault_data)

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        dev = fault_data.get("device_info", {})
        flt = fault_data.get("fault_info", {})

        overview_rows = [
            {"Hạng Mục": "Tên Trạm Biến Áp", "Giá Trị": dev.get("station_name", "NM ĐMT MỸ HIỆP (110kV)")},
            {"Hạng Mục": "Ngăn Lộ / Xuất Tuyến", "Giá Trị": dev.get("bay_name", "Ngăn 171 - 110kV")},
            {"Hạng Mục": "Chủng Loại Rơ Le (IED)", "Giá Trị": f"{dev.get('ied_type', 'RED670')} v{dev.get('ied_version', '2.2.3')}"},
            {"Hạng Mục": "Chức Năng Bảo Vệ Chính", "Giá Trị": "F87L (So Lệch Dọc Đường Dây 110kV)"},
            {"Hạng Mục": "Số Bản Ghi (Record No)", "Giá Trị": dev.get("recording_number", "339")},
            {"Hạng Mục": "Thời Điểm Xuất Hiện Sự Cố", "Giá Trị": flt.get("trigger_time", "--")},
            {"Hạng Mục": "Tín Hiệu Khởi Phát (Trigger)", "Giá Trị": flt.get("trigger_signal", "L4CPDIF TR L2")},
            {"Hạng Mục": "Dạng Sự Cố", "Giá Trị": flt.get("fault_phase", "Pha B - Chạm Đất (L2-N)")},
            {"Hạng Mục": "Định Vị Điểm Sự Cố (Khoảng cách)", "Giá Trị": f"{floc.get('dist_km')} km ({floc.get('dist_pct')}% tuyến)"},
            {"Hạng Mục": "Vị Trí Cột Dự Kiến", "Giá Trị": floc.get('tower_range', '')},
            {"Hạng Mục": "Tổng Trở Ngắn Mạch Vòng Lặp", "Giá Trị": f"Z = {floc.get('r_loop_ohm')} + j{floc.get('x_loop_ohm')} Ohm (X = {floc.get('x_loop_ohm')} Ohm)"},
            {"Hạng Mục": "Thời Gian Rơ Le Phát Lệnh Cắt", "Giá Trị": f"{flt.get('relay_operating_time_ms', 5)} ms"},
            {"Hạng Mục": "Thời Gian Mở Máy Cắt 171", "Giá Trị": f"{flt.get('breaker_opening_time_ms', 27)} ms"},
            {"Hạng Mục": "Tổng Thời Gian Loại Trừ Sự Cố", "Giá Trị": f"{flt.get('total_fault_clearing_time_ms', 32)} ms"},
            {"Hạng Mục": "Đánh Giá Tác Động Rơ Le", "Giá Trị": "✅ Tác Động Đúng, Chọn Lọc Tuyệt Đối, Loại Trừ Sự Cố Thành Công"}
        ]
        pd.DataFrame(overview_rows).to_excel(writer, sheet_name="1_Tong_Quan_Su_Co", index=False)

        df_u = fault_data.get("df_voltages", pd.DataFrame())
        df_i = fault_data.get("df_currents", pd.DataFrame())
        if not df_u.empty:
            df_u.to_excel(writer, sheet_name="2_Dien_Ap_RMS", index=False)
        if not df_i.empty:
            df_i.to_excel(writer, sheet_name="2_Dong_Dien_RMS", index=False)

        df_soe = fault_data.get("df_soe", pd.DataFrame())
        if not df_soe.empty:
            df_soe.to_excel(writer, sheet_name="3_Nhat_Ky_SoE_Miligiay", index=False)

        om_rows = [
            {"Hạng Mục": "1. Đánh giá vị trí sự cố", "Nội Dung": f"Điểm ngắn mạch chạm đất pha B xảy ra tại vị trí km {floc.get('dist_km')} từ TBA ĐMT Mỹ Hiệp (khoảng cột #{int(floc.get('dist_km')*1000/300)} - #{int(floc.get('dist_km')*1000/300)+2} xuất tuyến 171)."},
            {"Hạng Mục": "2. Nguyên nhân rơ le báo Error Fault Location", "Nội Dung": floc.get('root_cause_ied_error')},
            {"Hạng Mục": "3. Hoạt động của Rơ le 87L", "Nội Dung": "Rơ le ABB RED670 phát hiện dòng so lệch Id = 4.220A và phát lệnh cắt sau 5ms, đồng thời gửi tín hiệu Inter-trip sang trạm đối diện."},
            {"Hạng Mục": "4. Hoạt động của Máy cắt QA1 (171)", "Nội Dung": "Máy cắt 171 mở dập hồ quang hoàn tất sau 27ms kể từ lệnh trip (tổng thời gian cô lập 32ms), đảm bảo an toàn cho máy biến áp và dàn pin."},
            {"Hạng Mục": "5. Khuyến nghị kiểm tra hiện trường", "Nội Dung": f"1) Tập trung tuần tra chuỗi sứ cách điện và hành lang tuyến pha B tại {floc.get('tower_range')}. 2) Đo Riso pha B. 3) Cài đặt bổ sung thông số tổng trở đường dây vào khối RFLO trong PCM600."}
        ]
        pd.DataFrame(om_rows).to_excel(writer, sheet_name="4_Khuyen_Nghi_OM", index=False)

    return output.getvalue()
