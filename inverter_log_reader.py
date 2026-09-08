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


def analyze_failure_risks_and_maintenance(
    df_alarms: Optional[pd.DataFrame] = None,
    df_telemetry: Optional[pd.DataFrame] = None,
    cur_inv: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Động cơ Chẩn đoán Dự báo Nguy cơ Hư hỏng & Khuyến nghị Bảo trì O&M Ngăn ngừa
    Dựa trên đối soát dữ liệu nhật ký sự cố (alarmg_history), dữ liệu điện học (his_inv_rd)
    và đặc thù 229 Inverter Huawei SUN2000-175KTL-H0 tại ĐMT Mỹ Hiệp.
    """
    if df_alarms is None:
        df_alarms = pd.DataFrame()
    if df_telemetry is None:
        df_telemetry = pd.DataFrame()

    # 1. Đếm các mã lỗi mấu chốt
    alarm_counts = {}
    if not df_alarms.empty and "Mã Lỗi" in df_alarms.columns:
        alarm_counts = df_alarms["Mã Lỗi"].value_counts().to_dict()

    # 2. Thống kê thông số điện học
    max_igbt_temp = 45.0
    max_cab_temp = 42.0
    min_grid_u = 800.0
    max_grid_u = 800.0
    if not df_telemetry.empty:
        if "Nhiệt Độ Khối IGBT (°C)" in df_telemetry.columns:
            max_igbt_temp = float(df_telemetry["Nhiệt Độ Khối IGBT (°C)"].max())
        if "Nhiệt Độ Vỏ Tủ (°C)" in df_telemetry.columns:
            max_cab_temp = float(df_telemetry["Nhiệt Độ Vỏ Tủ (°C)"].max())
        if "Điện Áp Lưới U_ab (V)" in df_telemetry.columns:
            min_grid_u = float(df_telemetry["Điện Áp Lưới U_ab (V)"].min())
            max_grid_u = float(df_telemetry["Điện Áp Lưới U_ab (V)"].max())

    risk_cards = []
    maintenance_checklist = []

    # -------------------------------------------------------------
    # NGUY CƠ 1: QUÁ NHIỆT VÀ HỎNG QUẠT LÀM MÁT (THERMAL & FAN RISK)
    # -------------------------------------------------------------
    n_fan = alarm_counts.get(2065, 0)
    n_temp = alarm_counts.get(2063, 0)
    thermal_indicators = []
    if n_fan > 0:
        thermal_indicators.append(f"Ghi nhận {n_fan} lần cảnh báo lỗi/kẹt quạt làm mát (2065 - Fan Fault).")
    if n_temp > 0:
        thermal_indicators.append(f"Ghi nhận {n_temp} lần nhiệt độ vỏ tủ vượt ngưỡng an toàn (2063 - Over-Temperature).")
    if max_igbt_temp >= 65.0:
        thermal_indicators.append(f"Nhiệt độ khối IGBT đỉnh đạt {max_igbt_temp:.1f}°C (nguy cơ suy giảm hiệu suất tản nhiệt).")

    if n_fan > 0 or n_temp >= 2 or max_igbt_temp >= 70.0:
        fan_risk_level = "CRITICAL"
        fan_badge = "🔴 Nguy cơ Cao"
        fan_color = "#EF4444"
        fan_risk_pct = min(95, 60 + n_fan * 15 + n_temp * 10)
    elif n_temp == 1 or max_igbt_temp >= 60.0:
        fan_risk_level = "WARNING"
        fan_badge = "🟡 Cần Lưu Ý"
        fan_color = "#F59E0B"
        fan_risk_pct = 45
    else:
        fan_risk_level = "LOW"
        fan_badge = "🟢 An Toàn"
        fan_color = "#10B981"
        fan_risk_pct = 10
        thermal_indicators.append("Nhiệt độ khối IGBT và quạt làm mát hoạt động trong giới hạn tối ưu.")

    risk_cards.append({
        "id": "THERMAL_FAN",
        "title": "🔥 Quá Nhiệt Vỏ Tủ & Suy Giảm Quạt Làm Mát",
        "level": fan_risk_level,
        "badge": fan_badge,
        "color": fan_color,
        "risk_pct": fan_risk_pct,
        "indicators": thermal_indicators,
        "root_cause": "Bụi bẩn bám dày trên cánh nhôm tản nhiệt phía sau hoặc quạt ngoài bị kẹt dị vật/suy thoái ổ bi.",
        "action": "Vệ sinh cánh nhôm tản nhiệt bằng máy thổi khí nén, kiểm tra quay tự do 4 quạt ngoài và đo dòng khởi động quạt.",
        "tools_needed": "Máy thổi khí áp lực cao, bộ lục giác mở lưới chắn quạt, quạt dự phòng Huawei 175KTL."
    })

    if fan_risk_level == "CRITICAL":
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🔴 Khẩn Cấp (24h - 48h)",
            "Hạng Mục Thiết Bị": "Cụm Quạt & Cánh Tản Nhiệt",
            "Nội Dung Kiểm Tra": "Kiểm tra thay thế quạt bị kẹt và vệ sinh toàn diện khe tản nhiệt",
            "Quy Trình Kỹ Thuật": "Cắt AC/DC, dùng que đo kiểm tra điện áp cấp quạt 12V/24V, thay cụm quạt bị rít ổ bi.",
            "Dụng Cụ / Vật Tư": "Cụm quạt ngoài Huawei, tua vít cách điện 1000V, máy thổi khí"
        })
    elif fan_risk_level == "WARNING":
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🟡 Định Kỳ (Trong tuần)",
            "Hạng Mục Thiết Bị": "Hệ Thống Tản Nhiệt Khí",
            "Nội Dung Kiểm Tra": "Thổi bụi cánh nhôm tản nhiệt Inverter giữa trưa",
            "Quy Trình Kỹ Thuật": "Vệ sinh lưới chắn bụi, đảm bảo khoảng cách thông gió mặt sau máy > 50cm.",
            "Dụng Cụ / Vật Tư": "Máy thổi bụi pin cầm tay, chổi cọ mềm"
        })

    # -------------------------------------------------------------
    # NGUY CƠ 2: PHÓNG ĐIỆN HỒ QUANG & SUY GIẢM CÁCH ĐIỆN DC (AFCI & RISO)
    # -------------------------------------------------------------
    n_riso = alarm_counts.get(2061, 0)
    n_rcd = alarm_counts.get(2062, 0)
    n_afci = alarm_counts.get(2002, 0)
    dc_iso_indicators = []
    if n_afci > 0:
        dc_iso_indicators.append(f"Ghi nhận {n_afci} lần phát sinh hồ quang điện DC (2002 - DC Arc Fault).")
    if n_riso > 0:
        dc_iso_indicators.append(f"Ghi nhận {n_riso} lần điện trở cách điện DC suy giảm dưới ngưỡng (2061 - Low Riso).")
    if n_rcd > 0:
        dc_iso_indicators.append(f"Ghi nhận {n_rcd} lần dòng điện rò tiếp địa tăng cao (2062 - Residual Current High).")

    if n_afci > 0 or n_riso >= 2 or n_rcd >= 2:
        iso_risk_level = "CRITICAL"
        iso_badge = "🔴 Nguy cơ Cao"
        iso_color = "#EF4444"
        iso_risk_pct = min(95, 65 + n_afci * 20 + (n_riso + n_rcd) * 8)
    elif n_riso == 1 or n_rcd == 1:
        iso_risk_level = "WARNING"
        iso_badge = "🟡 Cần Lưu Ý"
        iso_color = "#F59E0B"
        iso_risk_pct = 50
    else:
        iso_risk_level = "LOW"
        iso_badge = "🟢 An Toàn"
        iso_color = "#10B981"
        iso_risk_pct = 5
        dc_iso_indicators.append("Hệ thống cách điện DC và mạch bảo vệ chống hồ quang AFCI ổn định.")

    risk_cards.append({
        "id": "DC_INSULATION_ARC",
        "title": "⚡ Hồ Quang Điện (AFCI) & Suy Giảm Cách Điện Cáp DC (Riso)",
        "level": iso_risk_level,
        "badge": iso_badge,
        "color": iso_color,
        "risk_pct": iso_risk_pct,
        "indicators": dc_iso_indicators,
        "root_cause": "Đầu cắm MC4 bị lỏng tiếp xúc, cáp DC ngầm bị trầy xước vỏ cách điện tiếp xúc máng cáp hoặc ngập nước mưa.",
        "action": "Ngắt DC Switch, đo điện trở cách điện từng chuỗi String bằng Megger 1500VDC, kiểm tra siết lại toàn bộ giắc MC4.",
        "tools_needed": "Đồng hồ Megger 1500VDC, Kìm bấm cosse MC4 chuyên dụng, Băng keo cách điện 3M, Giắc MC4 1500V."
    })

    if iso_risk_level in ["CRITICAL", "WARNING"]:
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🔴 Khẩn Cấp (24h - 48h)" if iso_risk_level == "CRITICAL" else "🟡 Định Kỳ (Trong tuần)",
            "Hạng Mục Thiết Bị": "Chuỗi Cáp DC & Đầu Nối MC4",
            "Nội Dung Kiểm Tra": "Đo Megger cách điện 18 Chuỗi String và siết ép lại giắc MC4",
            "Quy Trình Kỹ Thuật": "Đo Riso cực (+) với đất và (-) với đất. Giá trị yêu cầu > 50 kΩ (khuyến nghị > 2 MΩ khi khô ráo).",
            "Dụng Cụ / Vật Tư": "Đồng hồ đo cách điện Megger 1500V, Kìm tuốt cáp DC 4mm/6mm, Kẹp MC4"
        })

    # -------------------------------------------------------------
    # NGUY CƠ 3: DÒNG NGƯỢC BACKFEED & HỎNG DIODE TẤM PIN
    # -------------------------------------------------------------
    n_backfeed = alarm_counts.get(2012, 0)
    n_reverse = alarm_counts.get(2011, 0)
    backfeed_indicators = []
    if n_backfeed > 0:
        backfeed_indicators.append(f"Ghi nhận {n_backfeed} lần dòng điện chạy ngược vào chuỗi pin (2012 - String Backfeed).")
    if n_reverse > 0:
        backfeed_indicators.append(f"Ghi nhận {n_reverse} lần đấu ngược cực tính chuỗi pin (2011 - Reverse Connection).")

    if n_reverse > 0 or n_backfeed >= 3:
        bf_risk_level = "CRITICAL"
        bf_badge = "🔴 Nguy cơ Cao"
        bf_color = "#EF4444"
        bf_risk_pct = min(90, 50 + n_backfeed * 10 + n_reverse * 30)
    elif n_backfeed > 0:
        bf_risk_level = "WARNING"
        bf_badge = "🟡 Cần Lưu Ý"
        bf_color = "#F59E0B"
        bf_risk_pct = 40
    else:
        bf_risk_level = "LOW"
        bf_badge = "🟢 An Toàn"
        bf_color = "#10B981"
        bf_risk_pct = 5
        backfeed_indicators.append("Cân bằng dòng điện giữa các chuỗi String cùng cổng MPPT đạt chuẩn.")

    risk_cards.append({
        "id": "DC_BACKFEED_DIODE",
        "title": "🔄 Dòng Điện Ngược Backfeed & Hỏng Diode Tấm Pin",
        "level": bf_risk_level,
        "badge": bf_badge,
        "color": bf_color,
        "risk_pct": bf_risk_pct,
        "indicators": backfeed_indicators,
        "root_cause": "Độ lệch điện áp lớn giữa 2 chuỗi cùng MPPT do che bóng cục bộ, nổ tấm pin hoặc hỏng Diode Bypass trong hộp nối.",
        "action": "Dùng Camera nhiệt FLIR quét bề mặt chuỗi tấm pin tìm điểm phát nhiệt (Hot-spot), kiểm tra hộp đấu nối Junction Box.",
        "tools_needed": "Camera ảnh nhiệt FLIR / HIKMICRO, Ampe kìm DC Fluke 376 FC, Đồng hồ đo VOM."
    })

    if bf_risk_level in ["CRITICAL", "WARNING"]:
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🟡 Định Kỳ (Trong tuần)",
            "Hạng Mục Thiết Bị": "Giàn Pin PV & Hộp Nối Diode",
            "Nội Dung Kiểm Tra": "Quét ảnh nhiệt phát hiện Hot-spot và đo điện áp hở mạch Voc từng chuỗi",
            "Quy Trình Kỹ Thuật": "Đo Voc so sánh giữa 2 chuỗi cùng MPPT lúc nắng đều. Độ lệch điện áp không được vượt quá 10V.",
            "Dụng Cụ / Vật Tư": "Camera nhiệt cầm tay, Ampe kìm kẹp DC, sổ tay ghi nhận vị trí tấm pin lỗi"
        })

    # -------------------------------------------------------------
    # NGUY CƠ 4: HỎNG KHỐI CÔNG SUẤT IGBT & PHẦN CỨNG (HARDWARE BREAKDOWN)
    # -------------------------------------------------------------
    n_dev = alarm_counts.get(2064, 0)
    n_oc = alarm_counts.get(2038, 0)
    n_sc = alarm_counts.get(2051, 0)
    hw_indicators = []
    if n_dev > 0:
        hw_indicators.append(f"Ghi nhận {n_dev} lần lỗi phần cứng nội bộ biến tần (2064 - Hardware Fault).")
    if n_oc > 0:
        hw_indicators.append(f"Ghi nhận {n_oc} lần quá dòng AC tức thời IGBT (2038 - Output Overcurrent).")
    if n_sc > 0:
        hw_indicators.append(f"Ghi nhận {n_sc} lần đoản mạch đầu ra AC (2051 - Output Short Circuit).")

    if n_dev > 0 or n_sc > 0:
        hw_risk_level = "CRITICAL"
        hw_badge = "🔴 Nguy cơ Cao"
        hw_color = "#EF4444"
        hw_risk_pct = 95
    elif n_oc > 0:
        hw_risk_level = "WARNING"
        hw_badge = "🟡 Cần Lưu Ý"
        hw_color = "#F59E0B"
        hw_risk_pct = 55
    else:
        hw_risk_level = "LOW"
        hw_badge = "🟢 An Toàn"
        hw_color = "#10B981"
        hw_risk_pct = 5
        hw_indicators.append("Khối công suất nghịch lưu IGBT và mạch điều khiển DSP hoạt động tin cậy.")

    risk_cards.append({
        "id": "HARDWARE_IGBT",
        "title": "💥 Lỗi Khối Công Suất IGBT & Mạch Lực Biến Tần",
        "level": hw_risk_level,
        "badge": hw_badge,
        "color": hw_color,
        "risk_pct": hw_risk_pct,
        "indicators": hw_indicators,
        "root_cause": "Suy thoái lớp cách điện bán dẫn IGBT, ngắn mạch pha AC hoặc bo mạch kích lái Driver bị xung đột điện áp.",
        "action": "Trích xuất tệp sóng dsp_wave_data.gz và dsp_log, gửi hồ sơ RMA cho Trung tâm Bảo hành Kỹ thuật Huawei TAC.",
        "tools_needed": "Cáp nạp firmware USB-RS485, Hồ sơ bảo hành RMA chuẩn hãng Huawei, Biến tần dự phòng."
    })

    if hw_risk_level == "CRITICAL":
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🔴 Khẩn Cấp (24h - 48h)",
            "Hạng Mục Thiết Bị": "Khối Nghịch Lưu Inverter",
            "Nội Dung Kiểm Tra": "Lập hồ sơ yêu cầu hỗ trợ kỹ thuật bảo hành hãng Huawei (RMA Ticket)",
            "Quy Trình Kỹ Thuật": "Khóa cách ly CB AC/DC, trích xuất toàn bộ thư mục D:\\LOG, liên hệ Huawei TAC.",
            "Dụng Cụ / Vật Tư": "Tệp Log Inverter, Biểu mẫu yêu cầu bảo hành Huawei"
        })

    # -------------------------------------------------------------
    # NGUY CƠ 5: SỰ CỐ DAO ĐỘNG LƯỚI ĐIỆN EVN / TRẠM BIẾN ÁP (GRID ANOMALY)
    # -------------------------------------------------------------
    n_grid_u = alarm_counts.get(2032, 0) + alarm_counts.get(2033, 0)
    n_freq = alarm_counts.get(2035, 0) + alarm_counts.get(2036, 0) + alarm_counts.get(2037, 0)
    grid_indicators = []
    if n_grid_u > 0:
        grid_indicators.append(f"Ghi nhận {n_grid_u} lần sụt áp / quá áp điện lưới AC 800V (2032, 2033).")
    if n_freq > 0:
        grid_indicators.append(f"Ghi nhận {n_freq} lần tần số lưới dao động nhanh hoặc vượt ngưỡng bảo vệ (2035, 2036, 2037).")

    if n_grid_u >= 10 or n_freq >= 5:
        grid_risk_level = "WARNING"
        grid_badge = "🟡 Cần Lưu Ý"
        grid_color = "#F59E0B"
        grid_risk_pct = 60
    else:
        grid_risk_level = "LOW"
        grid_badge = "🟢 Bình Thường"
        grid_color = "#10B981"
        grid_risk_pct = 15
        grid_indicators.append("Chất lượng điện áp và tần số lưới AC 800V đáp ứng tốt Grid Code.")

    risk_cards.append({
        "id": "GRID_STABILITY",
        "title": "🌐 Sụt Áp & Dao Động Lưới Điện AC / Trạm Biến Áp",
        "level": grid_risk_level,
        "badge": grid_badge,
        "color": grid_color,
        "risk_pct": grid_risk_pct,
        "indicators": grid_indicators,
        "root_cause": "Dao động điện áp trên đường dây truyền tải 110kV/22kV hoặc nấc phân áp máy biến áp chưa tối ưu.",
        "action": "Theo dõi thông số đo đếm công tơ trạm và rơ le bảo vệ TBA 22/110kV, phối hợp Điều độ viên A0/A3.",
        "tools_needed": "Phần mềm SCADA trạm, Máy phân tích chất lượng điện năng Fluke 435."
    })

    # Hạng mục kiểm tra định kỳ tiêu chuẩn nếu checklist đang trống
    if not maintenance_checklist:
        maintenance_checklist.append({
            "Mức Độ Ưu Tiên": "🟢 Định Kỳ (Hàng tháng / Quý)",
            "Hạng Mục Thiết Bị": "Toàn Bộ Biến Tần & Tủ Đấu Nối",
            "Nội Dung Kiểm Tra": "Bảo dưỡng cơ điện định kỳ và vệ sinh công nghiệp",
            "Quy Trình Kỹ Thuật": "Vệ sinh quạt, siết lực bu-lông đầu cực AC (lực siết 35 N.m), kiểm tra gioăng cao su chống nước tủ máy.",
            "Dụng Cụ / Vật Tư": "Cờ lê lực, Máy đo nhiệt độ hồng ngoại, Khí nén làm sạch"
        })

    # Đánh giá tổng thể
    crit_count = sum(1 for c in risk_cards if c["level"] == "CRITICAL")
    warn_count = sum(1 for c in risk_cards if c["level"] == "WARNING")
    if crit_count > 0:
        overall_level = "🔴 NGUY CƠ CAO"
        overall_color = "#EF4444"
        overall_summary = f"Inverter đang đối mặt với {crit_count} nguy cơ sự cố nghiêm trọng cần đội O&M xử lý ngay trong 24h - 48h để phòng ngừa dừng máy hoặc chập cháy."
    elif warn_count > 0:
        overall_level = "🟡 NGUY CƠ TRUNG BÌNH"
        overall_color = "#F59E0B"
        overall_summary = f"Ghi nhận {warn_count} nguy cơ kỹ thuật cần đưa vào lịch bảo dưỡng ngăn ngừa trong tuần tới."
    else:
        overall_level = "🟢 AN TOÀN VẬN HÀNH"
        overall_color = "#10B981"
        overall_summary = "Biến tần ở trạng thái kỹ thuật rất tốt, không phát hiện rủi ro sự cố bất thường."

    return {
        "overall_level": overall_level,
        "overall_color": overall_color,
        "overall_summary": overall_summary,
        "risk_cards": risk_cards,
        "maintenance_checklist": pd.DataFrame(maintenance_checklist)
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

    def get_inverter_telemetry_history(self, folder_path: str, max_records: int = 4320) -> pd.DataFrame:
        """
        Giải mã chuỗi dữ liệu điện học 5 phút (his_inv_rd.gz) của Biến tần.
        Bao gồm: Công suất DC, Điện áp 9 MPPT, Dòng điện 18 PV Strings, Điện áp lưới AC, Tần số, Nhiệt độ IGBT & Vỏ tủ.
        """
        p = os.path.join(folder_path, "his_inv_rd.gz")
        if not os.path.exists(p):
            return pd.DataFrame()

        try:
            with gzip.open(p, "rb") as f:
                bdata = f.read()
        except Exception:
            return pd.DataFrame()

        rec_len = 130
        header_offset = 12
        if len(bdata) <= header_offset:
            return pd.DataFrame()

        num_recs = (len(bdata) - header_offset) // rec_len
        if num_recs == 0:
            return pd.DataFrame()

        limit = min(num_recs, max_records)
        records = []
        for i in range(limit):
            chunk = bdata[header_offset + i * rec_len : header_offset + (i + 1) * rec_len]
            ts = struct.unpack("<I", chunk[0:4])[0]
            if ts == 0 or ts > 2000000000:
                continue
            dt = datetime.fromtimestamp(ts)

            # 9 MPPT voltages (scale 0.1V)
            u_mppt = [struct.unpack("<H", chunk[10 + m * 2 : 12 + m * 2])[0] / 10.0 for m in range(9)]
            # 18 PV currents (scale 0.01A)
            i_pv = [struct.unpack("<H", chunk[28 + s * 2 : 30 + s * 2])[0] / 100.0 for s in range(18)]

            # AC Grid Line Voltages (scale 0.1V)
            u_ab = struct.unpack("<H", chunk[66:68])[0] / 10.0
            u_bc = struct.unpack("<H", chunk[68:70])[0] / 10.0

            # Grid Frequency (scale 0.01Hz)
            freq = struct.unpack("<H", chunk[86:88])[0] / 100.0

            # Cabinet / IGBT Temperatures (scale 0.1C)
            temp_igbt = struct.unpack("<h", chunk[92:94])[0] / 100.0 if struct.unpack("<h", chunk[92:94])[0] < 2000 else struct.unpack("<h", chunk[92:94])[0] / 10.0
            temp_cab = struct.unpack("<h", chunk[94:96])[0] / 100.0 if struct.unpack("<h", chunk[94:96])[0] < 2000 else struct.unpack("<h", chunk[94:96])[0] / 10.0

            if temp_igbt < -20 or temp_igbt > 150:
                temp_igbt = 45.0
            if temp_cab < -20 or temp_cab > 150:
                temp_cab = 42.0

            # Total Pdc (kW)
            pdc_kw = sum(u_mppt[m] * (i_pv[m * 2] + i_pv[m * 2 + 1]) for m in range(9)) / 1000.0

            rec_dict = {
                "Thời Gian": dt.strftime("%d/%m/%Y %H:%M"),
                "Timestamp_DT": dt,
                "Công Suất DC (kW)": round(pdc_kw, 2),
                "Điện Áp Lưới U_ab (V)": round(u_ab, 1),
                "Điện Áp Lưới U_bc (V)": round(u_bc, 1),
                "Tần Số Lưới (Hz)": round(freq, 2),
                "Nhiệt Độ Khối IGBT (°C)": round(temp_igbt, 1),
                "Nhiệt Độ Vỏ Tủ (°C)": round(temp_cab, 1),
                "Điện Áp MPPT TB (V)": round(sum(u_mppt) / 9.0, 1),
                "Dòng Điện PV TB (A)": round(sum(i_pv) / 18.0, 2),
            }
            for m_idx in range(9):
                rec_dict[f"U_mppt{m_idx+1}"] = round(u_mppt[m_idx], 1)
            for s_idx in range(18):
                rec_dict[f"I_pv{s_idx+1}"] = round(i_pv[s_idx], 2)

            records.append(rec_dict)

        df = pd.DataFrame(records)
        if not df.empty:
            df.sort_values(by="Timestamp_DT", ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    # Bí danh tiện ích
    get_inverter_5min_telemetry = get_inverter_telemetry_history

    def get_fault_telemetry_blackbox(self, folder_path: str, fault_time_dt: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        """
        Trích xuất Hộp Đen Điện Học (Black-Box Telemetry) tại thời điểm xảy ra sự cố.
        Khớp thời gian sự cố với bản ghi 5 phút gần nhất trong his_inv_rd.gz.
        """
        df_telemetry = self.get_inverter_telemetry_history(folder_path)
        if df_telemetry.empty:
            return None

        if fault_time_dt is None:
            closest_row = df_telemetry.iloc[0]
        else:
            time_diffs = (df_telemetry["Timestamp_DT"] - fault_time_dt).abs()
            closest_idx = time_diffs.idxmin()
            closest_row = df_telemetry.loc[closest_idx]

        mppt_voltages = [closest_row.get(f"U_mppt{i}", 0.0) for i in range(1, 10)]
        pv_currents = [closest_row.get(f"I_pv{i}", 0.0) for i in range(1, 19)]

        return {
            "telemetry_time": closest_row["Thời Gian"],
            "pdc_kw": closest_row["Công Suất DC (kW)"],
            "u_grid_ab": closest_row["Điện Áp Lưới U_ab (V)"],
            "u_grid_bc": closest_row["Điện Áp Lưới U_bc (V)"],
            "frequency_hz": closest_row["Tần Số Lưới (Hz)"],
            "temp_igbt": closest_row["Nhiệt Độ Khối IGBT (°C)"],
            "temp_cab": closest_row["Nhiệt Độ Vỏ Tủ (°C)"],
            "mppt_voltages": mppt_voltages,
            "pv_currents": pv_currents,
            "avg_mppt_voltage": closest_row["Điện Áp MPPT TB (V)"],
            "avg_pv_current": closest_row["Dòng Điện PV TB (A)"]
        }


def export_inverter_log_to_excel(inv_meta: Dict[str, Any], df_alarms: pd.DataFrame, df_run_log: pd.DataFrame, df_telemetry: Optional[pd.DataFrame] = None) -> bytes:
    """Xuất toàn bộ dữ liệu giải mã Logger Inverter sang tệp Excel chuyên nghiệp kèm Health Score và Dữ liệu điện học 5 phút"""
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

        if df_telemetry is not None and not df_telemetry.empty:
            exp_tel = df_telemetry[[
                "Thời Gian", "Công Suất DC (kW)", "Điện Áp Lưới U_ab (V)", "Điện Áp Lưới U_bc (V)",
                "Tần Số Lưới (Hz)", "Nhiệt Độ Khối IGBT (°C)", "Nhiệt Độ Vỏ Tủ (°C)",
                "Điện Áp MPPT TB (V)", "Dòng Điện PV TB (A)"
            ]].head(2000).copy()
            for col in exp_tel.columns:
                exp_tel[col] = exp_tel[col].apply(clean_excel_string)
            exp_tel.to_excel(writer, sheet_name="Dien_Hoc_5Phut_Telemetry", index=False)

        risk_analysis = analyze_failure_risks_and_maintenance(df_alarms, df_telemetry, inv_meta)
        df_maint = risk_analysis.get("maintenance_checklist", pd.DataFrame())
        if isinstance(df_maint, pd.DataFrame) and not df_maint.empty:
            exp_maint = df_maint.copy()
            for col in exp_maint.columns:
                exp_maint[col] = exp_maint[col].apply(clean_excel_string)
            exp_maint.to_excel(writer, sheet_name="Khuyen_Nghi_Bao_Tri_OM", index=False)

    output.seek(0)
    return output.getvalue()


