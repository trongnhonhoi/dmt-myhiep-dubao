"""
Module Đọc và Giải Mã Nhật Ký Biến Tần Huawei SUN2000-175KTL-H0 (D:\\LOG)
Nhà Máy Điện Mặt Trời Mỹ Hiệp (50MWp / 40.075MW)
Chức năng:
- Quét và nhận diện các thư mục Log biến tần (ESN_Timestamp) trong D:\\LOG
- Giải mã tệp nhị phân cảnh báo alarmg_history.gz & alarmg_active.emap
- Trích xuất nhật ký vận hành run_log.gz, sun_escp_log.gz, dsp_log
- Đọc thông tin cấu hình, I-V curve iv_data.emap, maint_file.emap, cfg_file
- Xuất báo cáo chẩn đoán sự cố biến tần chuyên sâu (Excel)
"""

import os
import io
import gzip
import struct
import glob
import re
import time
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Đường dẫn mặc định
def get_default_log_path() -> str:
    """Tự động tìm đường dẫn thư mục D:\\LOG hoặc thư mục dự phòng data/LOG"""
    if os.path.exists(r"D:\LOG"):
        return r"D:\LOG"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(current_dir, "data", "LOG"),
        os.path.join(os.getcwd(), "data", "LOG"),
        os.path.join(current_dir, "sample_data", "LOG"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return r"D:\LOG"

DEFAULT_LOG_PATH = get_default_log_path()

def clean_excel_string(val: Any) -> Any:
    """Lọc bỏ các ký tự điều khiển không hợp lệ để xuất Excel an toàn"""
    if isinstance(val, str):
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", val)
    return val

# Bảng tra cứu mã lỗi Huawei SUN2000 tiêu chuẩn (Kèm nhóm nguyên nhân gốc & khuyến nghị O&M)
HUAWEI_ALARM_REGISTRY = {
    2001: {
        "name_en": "High DC Input Voltage",
        "name_vi": "Quá điện áp đầu vào DC",
        "severity": "CRITICAL",
        "severity_vi": "Khẩn cấp",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Điện áp hở mạch chuỗi PV vượt quá ngưỡng chịu đựng tối đa của Inverter (1500VDC).",
        "action": "Kiểm tra số lượng tấm pin trên chuỗi String DC, đo điện áp Voc khi nhiệt độ môi trường thấp."
    },
    2002: {
        "name_en": "DC Arc Fault",
        "name_vi": "Lỗi phát sinh hồ quang điện DC (AFCI)",
        "severity": "CRITICAL",
        "severity_vi": "Khẩn cấp",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Phát hiện tia lửa điện/hồ quang tại giắc MC4, hộp đấu nối hoặc cáp DC bị hở.",
        "action": "Ngắt ngay DC Switch, kiểm tra siết chặt toàn bộ đầu nối MC4 và cáp dẫn DC chống cháy nổ."
    },
    2011: {
        "name_en": "String Reverse Connection",
        "name_vi": "Đấu nối ngược cực tính chuỗi pin",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Cực dương (+) và cực âm (-) của chuỗi pin bị đấu ngược vào cổng MPPT.",
        "action": "Đo kiểm tra cực tính bằng đồng hồ VOM và đảo lại đầu cắm MC4 đúng quy cách."
    },
    2012: {
        "name_en": "String Current Backfeed",
        "name_vi": "Dòng điện chạy ngược chuỗi pin (Backfeed)",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Độ lệch điện áp giữa 2 chuỗi cùng MPPT quá lớn khiến chuỗi áp cao nạp dòng ngược sang chuỗi áp thấp.",
        "action": "Kiểm tra tấm pin bị che bóng, hỏng Diode Bypass hoặc đứt cầu chì/chuỗi pin lân cận."
    },
    2021: {
        "name_en": "AFCI Self-Check Failure",
        "name_vi": "Tự kiểm tra mạch AFCI thất bại",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "SYSTEM_OP",
        "category_vi": "🛠️ Vận Hành & Firmware",
        "cause": "Module dò hồ quang nội bộ biến tần bị lỗi hoặc suy giảm độ nhạy.",
        "action": "Khởi động lại biến tần, kiểm tra cập nhật phần mềm DSP hoặc liên hệ Huawei TAC."
    },
    2031: {
        "name_en": "Phase Angle Exception",
        "name_vi": "Góc lệch pha điện áp lưới bất thường",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Lưới điện 110kV/22kV bị dao động góc pha hoặc sai thứ tự pha AC.",
        "action": "Kiểm tra thứ tự pha R-S-T tại đầu cực AC và rơ le bảo vệ TBA."
    },
    2032: {
        "name_en": "Grid Under-Voltage / Fault",
        "name_vi": "Lưới điện sụt áp / Mất điện lưới AC",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Điện áp lưới AC 800V tụt dưới ngưỡng cho phép hoặc mất nguồn lưới điện EVN.",
        "action": "Kiểm tra máy cắt AC, rơ le bảo vệ trạm biến áp và trạng thái lưới điện EVN."
    },
    2033: {
        "name_en": "Grid Over-Voltage",
        "name_vi": "Quá điện áp lưới điện AC",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Điện áp lưới AC vượt ngưỡng bảo vệ mức 1 hoặc mức 2 của Inverter.",
        "action": "Kiểm tra nấc phân áp máy biến áp nâng áp hoặc cài đặt ngưỡng bảo vệ AC Overvoltage."
    },
    2034: {
        "name_en": "Grid Voltage Unbalance",
        "name_vi": "Mất cân bằng điện áp 3 pha lưới AC",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Độ lệch điện áp giữa các pha U_ab, U_bc, U_ca vượt ngưỡng quy định.",
        "action": "Kiểm tra chất lượng lưới điện trạm biến áp và cân tải nội bộ nhà máy."
    },
    2035: {
        "name_en": "Grid Under-Frequency",
        "name_vi": "Tần số lưới điện quá thấp (< 49.5 Hz)",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Hệ thống điện quốc gia bị sụt giảm tần số dưới ngưỡng cài đặt bảo vệ.",
        "action": "Kiểm tra thông số cài đặt Grid Code và phối hợp Trung tâm Điều độ A0/A3."
    },
    2036: {
        "name_en": "Grid Over-Frequency",
        "name_vi": "Tần số lưới điện quá cao (> 50.5 Hz)",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Tần số hệ thống điện tăng cao vượt ngưỡng cài đặt bảo vệ.",
        "action": "Kiểm tra chế độ đáp ứng quá tần số (Over-frequency derating) của biến tần."
    },
    2037: {
        "name_en": "Grid Frequency Instability",
        "name_vi": "Tốc độ biến thiên tần số lưới quá nhanh (RoCoF)",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Dao động tần số trên lưới điện truyền tải diễn ra đột ngột.",
        "action": "Theo dõi ổn định hệ thống điện và kiểm tra cài đặt RoCoF."
    },
    2038: {
        "name_en": "Output Over-Current",
        "name_vi": "Quá dòng điện đầu ra AC",
        "severity": "CRITICAL",
        "severity_vi": "Khẩn cấp",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Dòng điện AC tức thời vượt quá khả năng chịu dòng cực đại của IGBT.",
        "action": "Kiểm tra chạm chập ngắn mạch đường cáp AC 800V và tình trạng cầu chì AC."
    },
    2039: {
        "name_en": "Output Current DC Component High",
        "name_vi": "Thành phần một chiều (DC Component) trong dòng AC cao",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Mạch lọc hoặc thuật toán điều khiển nghịch lưu có thành phần dòng DC xâm nhập lưới.",
        "action": "Theo dõi và khởi động lại Inverter nếu hiện tượng lặp lại thường xuyên."
    },
    2040: {
        "name_en": "Power Grid Quality Anomaly",
        "name_vi": "Chất lượng điện lưới bất thường / Sóng hài cao",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "GRID_TBA",
        "category_vi": "🌐 Lưới Điện & TBA",
        "cause": "Sóng hài điện áp hoặc dòng điện trên lưới AC vượt tiêu chuẩn kỹ thuật.",
        "action": "Kiểm tra các thiết bị bù phản kháng hoặc sóng hài từ trạm lân cận."
    },
    2051: {
        "name_en": "Output Short Circuit",
        "name_vi": "Đoản mạch đầu ra AC Inverter",
        "severity": "CRITICAL",
        "severity_vi": "Khẩn cấp",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Chạm chập giữa các pha AC hoặc chạm đất tại đầu cực biến tần.",
        "action": "Ngắt ngay lập tức, kiểm tra cách điện cáp AC và thanh cái tủ gom ACB."
    },
    2061: {
        "name_en": "Low Insulation Resistance",
        "name_vi": "Điện trở cách điện DC quá thấp (Riso Low)",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Cáp DC hoặc tấm pin bị trầy xước, ngấm nước mưa gây rò điện DC xuống đất (R < 50kΩ).",
        "action": "Đo Megger cách điện từng chuỗi String DC, tìm điểm rò rỉ hoặc cáp bị ngập nước."
    },
    2062: {
        "name_en": "Residual Current Abnormally High",
        "name_vi": "Dòng rò tiếp địa (RCD) quá cao",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "DC_FIELD",
        "category_vi": "☀️ Chuỗi Pin PV & Cáp DC",
        "cause": "Phát hiện dòng điện rò rỉ từ mạch DC hoặc AC thoát xuống hệ thống tiếp địa trạm.",
        "action": "Kiểm tra hệ thống tiếp địa Inverter, kiểm tra cáp ngầm bị ẩm ướt hoặc đứt vỏ bọc."
    },
    2063: {
        "name_en": "Cabinet Over-Temperature",
        "name_vi": "Nhiệt độ bên trong vỏ tủ Inverter quá cao",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Nhiệt độ môi trường cao kết hợp quạt làm mát suy giảm hoặc tản nhiệt bị bám bụi.",
        "action": "Vệ sinh cánh tản nhiệt phía sau, kiểm tra thông gió và tốc độ quay của quạt làm mát."
    },
    2064: {
        "name_en": "Device Fault",
        "name_vi": "Lỗi phần cứng nội bộ biến tần (Hardware Fault)",
        "severity": "CRITICAL",
        "severity_vi": "Khẩn cấp",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Hỏng hóc khối công suất IGBT, mạch kích lái Driver hoặc vi xử lý DSP.",
        "action": "Ghi nhận mã phụ (Sub-code), liên hệ trung tâm bảo hành Huawei để thay thế thiết bị."
    },
    2065: {
        "name_en": "Fan Fault / Failure",
        "name_vi": "Lỗi / Hỏng quạt làm mát Inverter",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Quạt ngoài (External Fan) hoặc quạt trong (Internal Fan) bị kẹt rác, đứt dây hoặc hỏng ổ bi.",
        "action": "Kiểm tra quay tay quạt làm mát, vệ sinh dị vật và thay thế cụm quạt định kỳ."
    },
    2066: {
        "name_en": "Upgrade Status / Operation",
        "name_vi": "Trạng thái nạp / Nâng cấp Firmware",
        "severity": "INFO",
        "severity_vi": "Thông tin",
        "category": "SYSTEM_OP",
        "category_vi": "🛠️ Vận Hành & Firmware",
        "cause": "Quá trình cập nhật phần mềm điều khiển DSP / ARM của biến tần.",
        "action": "Kiểm tra phiên bản Firmware sau nâng cấp đảm bảo hoạt động ổn định."
    },
    2067: {
        "name_en": "License Expired",
        "name_vi": "Bản quyền tính năng nâng cao hết hạn",
        "severity": "INFO",
        "severity_vi": "Thông tin",
        "category": "SYSTEM_OP",
        "category_vi": "🛠️ Vận Hành & Firmware",
        "cause": "Hết hạn giấy phép sử dụng tính năng cao cấp trên thiết bị.",
        "action": "Gia hạn License nếu cần sử dụng tính năng mở rộng."
    },
    2070: {
        "name_en": "Reactive Power Compensation Anomaly",
        "name_vi": "Bất thường chế độ điều khiển công suất phản kháng",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "SYSTEM_OP",
        "category_vi": "🛠️ Vận Hành & Firmware",
        "cause": "Biến tần không đáp ứng được đường đặc tính Q(U) hoặc Cos phi theo lệnh SmartLogger.",
        "action": "Kiểm tra cài đặt điều khiển công suất phản kháng trên SmartLogger / PPC."
    },
    2080: {
        "name_en": "Communication Disconnected",
        "name_vi": "Mất kết nối truyền thông nội bộ Inverter",
        "severity": "MAJOR",
        "severity_vi": "Nghiêm trọng",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Mất liên lạc giữa bo mạch điều khiển chính và bo mạch hiển thị / giám sát.",
        "action": "Kiểm tra cáp bẹ truyền thông nội bộ và nguồn cấp bo mạch."
    },
    2086: {
        "name_en": "Communication Sync Anomaly",
        "name_vi": "Bất thường đồng bộ truyền thông CAN/PLC",
        "severity": "WARNING",
        "severity_vi": "Cảnh báo",
        "category": "HARDWARE",
        "category_vi": "⚙️ Phần Cứng & Tủ Biến Tần",
        "cause": "Lỗi đồng bộ gói tin chu kỳ cao trên đường truyền cáp RS485 / MBUS PLC.",
        "action": "Kiểm tra điện trở đầu cuối 120Ω và chống nhiễu đường truyền tín hiệu."
    }
}


def calculate_inverter_health_score(df_alarms: Optional[pd.DataFrame] = None, cur_inv: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Thuật toán tính toán Chỉ Số Sức Khỏe Biến Tần (Inverter Health Index - IHI 0-100 pts)
    Dựa trên quy tắc phân tích nhật ký lỗi thực tế từ Huawei SUN2000-175KTL-H0.
    """
    base_score = 100.0
    deductions = []
    
    cat_counts = {
        "GRID_TBA": 0,
        "DC_FIELD": 0,
        "HARDWARE": 0,
        "SYSTEM_OP": 0
    }

    if df_alarms is None or df_alarms.empty:
        return {
            "score": 100.0,
            "rating": "Rất Tốt (Excellent)",
            "color": "#10B981",
            "badge": "🟢",
            "deductions": [],
            "category_counts": cat_counts,
            "prescription": "Biến tần hoạt động hoàn toàn ổn định, không ghi nhận bất kỳ sự cố nào trong nhật ký. Tiếp tục duy trì kiểm tra định kỳ."
        }

    df_calc = df_alarms.copy()

    # Đảm bảo các cột cần thiết luôn tồn tại
    if "Mã Lỗi" not in df_calc.columns:
        df_calc["Mã Lỗi"] = 0

    if "Category_Code" not in df_calc.columns:
        df_calc["Category_Code"] = df_calc["Mã Lỗi"].apply(
            lambda x: HUAWEI_ALARM_REGISTRY.get(int(x), {}).get("category", "SYSTEM_OP") if pd.notnull(x) else "SYSTEM_OP"
        )

    if "Nhóm Nguyên Nhân" not in df_calc.columns:
        df_calc["Nhóm Nguyên Nhân"] = df_calc["Mã Lỗi"].apply(
            lambda x: HUAWEI_ALARM_REGISTRY.get(int(x), {}).get("category_vi", "🛠️ Vận Hành & Khác") if pd.notnull(x) else "🛠️ Vận Hành & Khác"
        )

    if "Thời Điểm Kết Thúc" not in df_calc.columns:
        df_calc["Thời Điểm Kết Thúc"] = "N/A"

    # Đếm số lượng sự cố theo từng nhóm nguyên nhân
    for cat in df_calc["Category_Code"]:
        if cat in cat_counts:
            cat_counts[cat] += 1

    # Kiểm tra cảnh báo còn Active (Đang diễn ra)
    active_alarms = df_calc[df_calc["Thời Điểm Kết Thúc"] == "Đang Diễn Ra"]
    if not active_alarms.empty:
        n_act = len(active_alarms)
        pen_act = min(30.0, n_act * 15.0)
        base_score -= pen_act
        deductions.append({
            "reason": f"Có {n_act} sự cố đang diễn ra (chưa phục hồi)",
            "points": -pen_act,
            "severity": "CRITICAL"
        })

    # 1. Trừ điểm cho lỗi phần cứng (HARDWARE: 2064, 2065, 2051, 2038)
    hw_crit = df_calc[df_calc["Mã Lỗi"].isin([2064, 2051, 2038])]
    if not hw_crit.empty:
        pen_hw = min(35.0, len(hw_crit) * 10.0)
        base_score -= pen_hw
        deductions.append({
            "reason": f"Ghi nhận {len(hw_crit)} lần lỗi phần cứng nghiêm trọng (IGBT/Mạch lực/Đoản mạch)",
            "points": -pen_hw,
            "severity": "CRITICAL"
        })

    fan_faults = df_calc[df_calc["Mã Lỗi"] == 2065]
    if not fan_faults.empty:
        pen_fan = min(15.0, len(fan_faults) * 5.0)
        base_score -= pen_fan
        deductions.append({
            "reason": f"Ghi nhận {len(fan_faults)} lần lỗi quạt làm mát (Fan Fault)",
            "points": -pen_fan,
            "severity": "MAJOR"
        })

    # 2. Trừ điểm cho lỗi DC Field (2061 Riso, 2062 RCD, 2002 AFCI, 2001 Quá áp DC)
    dc_crit = df_calc[df_calc["Mã Lỗi"].isin([2061, 2062, 2002, 2001])]
    if not dc_crit.empty:
        pen_dc = min(25.0, len(dc_crit) * 5.0)
        base_score -= pen_dc
        deductions.append({
            "reason": f"Ghi nhận {len(dc_crit)} lần lỗi cách điện DC/Rò điện/Hồ quang (Riso/RCD/AFCI)",
            "points": -pen_dc,
            "severity": "MAJOR"
        })

    # 3. Trừ điểm cho Backfeed hoặc Quá nhiệt (2012, 2063)
    backfeed_temp = df_calc[df_calc["Mã Lỗi"].isin([2012, 2063])]
    if not backfeed_temp.empty:
        pen_bt = min(12.0, len(backfeed_temp) * 2.0)
        base_score -= pen_bt
        deductions.append({
            "reason": f"Ghi nhận {len(backfeed_temp)} lần dòng điện ngược Backfeed hoặc quá nhiệt vỏ tủ",
            "points": -pen_bt,
            "severity": "WARNING"
        })

    # 4. Trừ điểm nhẹ cho dao động lưới (GRID_TBA: 2032, 2034, 2031, v.v.)
    grid_events = df_calc[df_calc["Category_Code"] == "GRID_TBA"]
    if not grid_events.empty:
        pen_gr = min(8.0, len(grid_events) * 0.5)
        base_score -= pen_gr
        deductions.append({
            "reason": f"Ghi nhận {len(grid_events)} lần biến động/sụt áp điện lưới AC hoặc trạm nâng",
            "points": -pen_gr,
            "severity": "INFO"
        })

    final_score = max(0.0, min(100.0, round(base_score, 1)))

    if final_score >= 90.0:
        rating = "Rất Tốt (Excellent)"
        color = "#10B981"
        badge = "🟢"
    elif final_score >= 75.0:
        rating = "Tốt (Good)"
        color = "#38BDF8"
        badge = "🔵"
    elif final_score >= 60.0:
        rating = "Cần Bảo Trì (Attention)"
        color = "#F59E0B"
        badge = "🟡"
    else:
        rating = "Nguy Cơ Cao (High Risk)"
        color = "#EF4444"
        badge = "🔴"

    # Tạo chỉ định O&M tự động
    prescriptions = []
    if cat_counts["HARDWARE"] > 0:
        prescriptions.append("🛠️ **Phần cứng**: Cần kiểm tra quạt tản nhiệt, vệ sinh cánh nhôm và kiểm tra mã phụ (Sub-code) mạch kích IGBT.")
    if cat_counts["DC_FIELD"] > 0:
        prescriptions.append("☀️ **Chuỗi DC**: Cần đo điện trở cách điện Riso từng chuỗi String, kiểm tra đầu cosse MC4 và cách điện cáp ngầm DC.")
    if cat_counts["GRID_TBA"] > 0:
        prescriptions.append("🌐 **Lưới & TBA**: Cần rà soát rơ le bảo vệ TBA và theo dõi chất lượng điện áp 3 pha AC 800V.")
    if not prescriptions:
        prescriptions.append("✅ **Vận hành bình thường**: Tiếp tục theo dõi thông số chu kỳ và thực hiện vệ sinh định kỳ.")

    return {
        "score": final_score,
        "rating": rating,
        "color": color,
        "badge": badge,
        "deductions": deductions,
        "category_counts": cat_counts,
        "prescription": "\n\n".join(prescriptions)
    }




class HuaweiInverterLogParser:
    """Động cơ phân tích và giải mã tệp Logger Inverter Huawei từ thư mục D:\\LOG"""
    def __init__(self, base_path: str = DEFAULT_LOG_PATH):
        self.base_path = base_path
        self._cache_inverters: List[Dict[str, Any]] = []
        self._last_scan_time: float = 0.0

    def check_connection(self) -> bool:
        """Kiểm tra sự tồn tại của thư mục D:\\LOG hoặc thư mục dự phòng"""
        try:
            if os.path.exists(self.base_path):
                return True
            fallback = get_default_log_path()
            if os.path.exists(fallback):
                self.base_path = fallback
                return True
            return False
        except Exception:
            return False

    def scan_inverter_log_folders(self, force_reload: bool = False) -> List[Dict[str, Any]]:
        """Quét và phân tích danh mục toàn bộ các thư mục Inverter Log có trong D:\\LOG"""
        if self._cache_inverters and not force_reload:
            return self._cache_inverters

        if not self.check_connection():
            return []

        folders = [f for f in glob.glob(os.path.join(self.base_path, "*")) if os.path.isdir(f)]
        if not folders:
            return []

        results = []
        for fld in sorted(folders):
            fld_name = os.path.basename(fld)
            m = re.match(r"^([A-Za-z0-9]+)_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", fld_name)
            if m:
                esn, yr, mo, dy, hr, mn, sc = m.groups()
                export_time = f"{dy}/{mo}/{yr} {hr}:{mn}:{sc}"
                dt_export = datetime(int(yr), int(mo), int(dy), int(hr), int(mn), int(sc))
            else:
                esn = fld_name.split("_")[0]
                mtime = os.path.getmtime(fld)
                dt_export = datetime.fromtimestamp(mtime)
                export_time = dt_export.strftime("%d/%m/%Y %H:%M:%S")

            # 1. Tìm Inverter ID từ iv_data.emap
            inv_id = "Chưa rõ ID"
            iv_path = os.path.join(fld, "iv_data.emap")
            if os.path.exists(iv_path):
                try:
                    with open(iv_path, "rb") as fp:
                        b = fp.read()
                        m_inv = re.search(rb"INV\d+\.\d+\.\d+", b)
                        if m_inv:
                            inv_id = m_inv.group(0).decode("ascii")
                except Exception:
                    pass

            # 2. Tìm Firmware version từ run_log.gz
            fw_ver = "V300R001C00B4G175"
            run_p = os.path.join(fld, "run_log.gz")
            if os.path.exists(run_p):
                try:
                    with gzip.open(run_p, "rt", encoding="utf-8", errors="ignore") as gz:
                        for line in gz:
                            if "inv_equip_base1246" in line and "V:" in line:
                                fw_ver = line.split("V:")[-1].strip()
                                break
                except Exception:
                    pass

            # 3. Đếm số lượng cảnh báo trong alarmg_history.gz
            alarm_p = os.path.join(fld, "alarmg_history.gz")
            alarm_count = 0
            if os.path.exists(alarm_p):
                try:
                    alarm_count = os.path.getsize(alarm_p) // 24
                except Exception:
                    pass

            # 4. Kiểm tra cảnh báo đang active
            active_p = os.path.join(fld, "alarmg_active.emap")
            has_active = os.path.exists(active_p) and os.path.getsize(active_p) > 0

            # 5. Xác định trạm biến áp phụ trách
            station_tag = "S1"
            if "INV" in inv_id:
                m_st = re.search(r"INV(\d+)\.", inv_id)
                if m_st:
                    station_tag = f"S{m_st.group(1)}"

            results.append({
                "folder_name": fld_name,
                "folder_path": fld,
                "inverter_id": inv_id,
                "esn": esn,
                "station_tag": station_tag,
                "firmware_version": fw_ver,
                "export_time": export_time,
                "export_datetime": dt_export,
                "alarm_count": alarm_count,
                "alarm_file_size_kb": round(os.path.getsize(alarm_p) / 1024, 1) if os.path.exists(alarm_p) else 0,
                "has_run_log": os.path.exists(run_p),
                "has_active_alarm": has_active,
                "file_count": len(glob.glob(os.path.join(fld, "*")))
            })

        results.sort(key=lambda x: x["inverter_id"])
        self._cache_inverters = results
        self._last_scan_time = time.time()
        return results

    def get_inverter_alarm_history(self, folder_path: str) -> pd.DataFrame:
        """Giải mã toàn bộ bản ghi nhị phân lịch sử sự cố (alarmg_history.gz) của 1 Inverter"""
        alarm_p = os.path.join(folder_path, "alarmg_history.gz")
        if not os.path.exists(alarm_p):
            return pd.DataFrame()

        try:
            with gzip.open(alarm_p, "rb") as f:
                bdata = f.read()
        except Exception:
            return pd.DataFrame()

        rec_len = 24
        num_recs = len(bdata) // rec_len
        if num_recs == 0:
            return pd.DataFrame()

        records = []
        for i in range(num_recs):
            chunk = bdata[i * rec_len : (i + 1) * rec_len]
            idx, dev_type, alarm_id, t_start, t_end, sub_id, flags = struct.unpack("<IHHIIII", chunk)
            
            dt_s = datetime.fromtimestamp(t_start) if t_start > 0 else None
            dt_e = datetime.fromtimestamp(t_end) if t_end > 0 else None
            
            dur_seconds = (t_end - t_start) if (t_end > t_start > 0) else 0
            if dur_seconds >= 3600:
                dur_str = f"{dur_seconds // 3600}h {(dur_seconds % 3600) // 60}m {dur_seconds % 60}s"
            elif dur_seconds >= 60:
                dur_str = f"{dur_seconds // 60}m {dur_seconds % 60}s"
            else:
                dur_str = f"{dur_seconds}s"

            info = HUAWEI_ALARM_REGISTRY.get(alarm_id, {
                "name_en": f"Huawei Alarm #{alarm_id}",
                "name_vi": f"Cảnh báo Huawei mã {alarm_id}",
                "severity": "WARNING",
                "severity_vi": "Cảnh báo",
                "category": "SYSTEM_OP",
                "category_vi": "🛠️ Vận Hành & Khác",
                "cause": "Sự cố vận hành ghi nhận từ bộ ghi nhật ký Inverter.",
                "action": "Tra cứu mã lỗi trong sổ tay kỹ thuật Huawei SUN2000-175KTL."
            })

            records.append({
                "STT": idx,
                "Mã Lỗi": alarm_id,
                "Tên Sự Cố (Việt)": info["name_vi"],
                "Tên Sự Cố (Anh)": info["name_en"],
                "Nhóm Nguyên Nhân": info.get("category_vi", "🛠️ Vận Hành & Khác"),
                "Category_Code": info.get("category", "SYSTEM_OP"),
                "Mức Độ": info["severity_vi"],
                "Severity_Code": info["severity"],
                "Thời Điểm Bắt Đầu": dt_s.strftime("%d/%m/%Y %H:%M:%S") if dt_s else "N/A",
                "Thời Điểm Kết Thúc": dt_e.strftime("%d/%m/%Y %H:%M:%S") if dt_e else "Đang Diễn Ra",
                "Thời Lượng": dur_str,
                "Duration_Sec": dur_seconds,
                "Nguyên Nhân Kỹ Thuật": info["cause"],
                "Biện Pháp Xử Lý": info["action"],
                "Start_DT": dt_s
            })

        df = pd.DataFrame(records)
        df.sort_values(by="Start_DT", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df

    def get_inverter_run_logs(self, folder_path: str, keyword: Optional[str] = None, max_lines: int = 1500) -> pd.DataFrame:
        """Đọc và lọc tệp nhật ký hoạt động run_log.gz của Inverter"""
        run_p = os.path.join(folder_path, "run_log.gz")
        if not os.path.exists(run_p):
            return pd.DataFrame()

        try:
            with gzip.open(run_p, "rt", encoding="utf-8", errors="ignore") as gz:
                lines = [l.strip() for l in gz if l.strip()]
        except Exception:
            return pd.DataFrame()

        if not lines:
            return pd.DataFrame()

        parsed_rows = []
        for line in lines:
            # Lọc bỏ ký tự điều khiển lạ
            clean_l = clean_excel_string(line)
            if not clean_l.strip():
                continue

            if keyword and keyword.lower() not in clean_l.lower():
                continue
            
            m = re.match(r"^(\d{2})(\d{2})(\d{2})\s+(\d{2})(\d{2})(\d{2})\s+(\w+)\s+(\S+)\s+(.*)$", clean_l)
            if m:
                yr, mo, dy, hr, mn, sc, mod, caller, msg = m.groups()
                time_str = f"{dy}/{mo}/20{yr} {hr}:{mn}:{sc}"
                parsed_rows.append({
                    "Thời Gian": time_str,
                    "Phân Hệ": mod,
                    "Module Hàm": caller,
                    "Nội Dung Sự Kiện": msg,
                    "Raw_Line": clean_l
                })
            else:
                parsed_rows.append({
                    "Thời Gian": "Hệ thống",
                    "Phân Hệ": "INFO",
                    "Module Hàm": "-",
                    "Nội Dung Sự Kiện": clean_l,
                    "Raw_Line": clean_l
                })

            if len(parsed_rows) >= max_lines:
                break

        return pd.DataFrame(parsed_rows)

    def get_inverter_protection_logs(self, folder_path: str) -> pd.DataFrame:
        """Đọc tệp nhật ký bảo vệ phần cứng sun_escp_log.gz"""
        prot_p = os.path.join(folder_path, "sun_escp_log.gz")
        if not os.path.exists(prot_p):
            return pd.DataFrame()

        try:
            with gzip.open(prot_p, "rt", encoding="utf-8", errors="ignore") as gz:
                text = gz.read()
        except Exception:
            return pd.DataFrame()

        entries = []
        chunks = text.split("\n\n") if "\n\n" in text else text.splitlines()
        for c in chunks:
            c_clean = clean_excel_string(c.strip())
            if c_clean:
                entries.append({"Nội Dung Log Bảo Vệ": c_clean})

        return pd.DataFrame(entries)


def export_inverter_log_to_excel(inv_meta: Dict[str, Any], df_alarms: pd.DataFrame, df_run_log: pd.DataFrame) -> bytes:
    """Xuất toàn bộ dữ liệu giải mã Logger Inverter sang tệp Excel chuyên nghiệp kèm Health Score"""
    output = io.BytesIO()
    health_info = calculate_inverter_health_score(df_alarms, inv_meta)
    
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_rows = [
            {"Thuộc Tính": "Mã Biến Tần", "Giá Trị": inv_meta.get("inverter_id", "")},
            {"Thuộc Tính": "Số Serial (ESN)", "Giá Trị": inv_meta.get("esn", "")},
            {"Thuộc Tính": "Trạm Biến Áp", "Giá Trị": inv_meta.get("station_tag", "")},
            {"Thuộc Tính": "Phiên Bản Firmware", "Giá Trị": inv_meta.get("firmware_version", "")},
            {"Thuộc Tính": "Thời Điểm Xuất Log", "Giá Trị": inv_meta.get("export_time", "")},
            {"Thuộc Tính": "Điểm Sức Khỏe Inverter (IHI)", "Giá Trị": f"{health_info['score']}/100 ({health_info['rating']})"},
            {"Thuộc Tính": "Sự Cố Lưới & TBA", "Giá Trị": health_info['category_counts']['GRID_TBA']},
            {"Thuộc Tính": "Sự Cố Chuỗi Pin DC", "Giá Trị": health_info['category_counts']['DC_FIELD']},
            {"Thuộc Tính": "Sự Cố Phần Cứng Máy", "Giá Trị": health_info['category_counts']['HARDWARE']},
            {"Thuộc Tính": "Tổng Số Bản Ghi Cảnh Báo", "Giá Trị": len(df_alarms)},
            {"Thuộc Tính": "Khuyến Nghị O&M Tự Động", "Giá Trị": health_info['prescription'].replace('\n\n', ' | ')},
            {"Thuộc Tính": "Thư Mục Gốc", "Giá Trị": inv_meta.get("folder_name", "")}
        ]
        df_sum = pd.DataFrame(summary_rows)
        for col in df_sum.columns:
            df_sum[col] = df_sum[col].apply(clean_excel_string)
        df_sum.to_excel(writer, sheet_name="Tong_Quan_Inverter", index=False)

        if not df_alarms.empty:
            exp_alarm = df_alarms[[
                "STT", "Mã Lỗi", "Tên Sự Cố (Việt)", "Tên Sự Cố (Anh)", "Nhóm Nguyên Nhân", "Mức Độ",
                "Thời Điểm Bắt Đầu", "Thời Điểm Kết Thúc", "Thời Lượng",
                "Nguyên Nhân Kỹ Thuật", "Biện Pháp Xử Lý"
            ]].copy()
            for col in exp_alarm.columns:
                exp_alarm[col] = exp_alarm[col].apply(clean_excel_string)
            exp_alarm.to_excel(writer, sheet_name="Lich_Su_Canh_Bao_Alarm", index=False)

        if not df_run_log.empty:
            exp_run = df_run_log[["Thời Gian", "Phân Hệ", "Module Hàm", "Nội Dung Sự Kiện"]].head(2000).copy()
            for col in exp_run.columns:
                exp_run[col] = exp_run[col].apply(clean_excel_string)
            exp_run.to_excel(writer, sheet_name="Nhat_Ky_Van_Hanh_RunLog", index=False)

    output.seek(0)
    return output.getvalue()

