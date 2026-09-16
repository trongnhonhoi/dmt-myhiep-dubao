# -*- coding: utf-8 -*-
"""
CƠ SỞ DỮ LIỆU PHIẾU CHỈNH ĐỊNH RƠ LE BẢO VỆ (TRẠM 110kV ĐMT MỸ HIỆP)
Ban hành bởi: Trung Tâm Điều Độ Hệ Thống Điện Miền Trung (A3)
Bao gồm đầy đủ 04 Phiếu Chỉnh Định Chính Thức:
  1. A3-01-2020/MYHS110: Rơ le RED 670 (ABB) - Bảo vệ so lệch đường dây 110kV XT 171
  2. A3-02-2020/MYHS110: Rơ le REF 615 (ABB) - Bảo vệ quá dòng hợp bộ XT 171
  3. A3-03-2020/MYHS110: Rơ le REC 670 (ABB) - Kiểm tra đồng bộ XT 171
  4. A3-04-2020/MYHS110: Rơ le REB 670 (ABB) - Bảo vệ so lệch thanh cái 110kV (MC 171, MC 131)
"""

import pandas as pd
import numpy as np
import io

# =========================================================================
# DỮ LIỆU CẤU HÌNH & THÔNG SỐ CHỈNH ĐỊNH CHI TIẾT
# =========================================================================

RELAY_SETTING_SHEETS = {
    "A3-01-2020/MYHS110": {
        "sheet_id": "A3-01-2020/MYHS110",
        "title": "Phiếu Chỉnh Định Rơ Le RED 670 - Bảo Vệ So Lệch Đường Dây 110kV (Lộ 171)",
        "station": "Trạm 110kV ĐMT Mỹ Hiệp",
        "protected_device": "XT 171 ĐMT Mỹ Hiệp – Phù Mỹ 220 (Lộ 171)",
        "circuit_breaker": "171",
        "decision_no": "1742/QĐ-ĐĐMT ngày 08/09/2020",
        "relay_model": "RED 670",
        "relay_order_code": "RED670*2.2-C42X00-B24C16F01H04P23-B1X0-AE-CB-B-B6X0-CE1AX-PPXXABXXXXXY",
        "manufacturer": "ABB",
        "year": 2020,
        "panel": "CRP2 +E02 (Mạch 1)",
        "software": "PCM600",
        "protection_type": "Bảo vệ so lệch đường dây - F87L (kèm F21, 67/67N, 50BF, 85, FL & FR)",
        "ct_ratio": "800/1A - TI MC 171",
        "vt_ratio": "115/√3 / 0.11/√3 kV - TU 171, C11",
        "power_system": {
            "UBase_kV": 115.0,
            "IBase_A": 800.0,
            "SBase_MVA": 159.3,
            "Frequency_Hz": 50.0,
            "PhaseRotation": "Normal=L1L2L3"
        },
        "summary_table": [
            {"function": "F87L", "stage": "Cấp 1 (IdMin)", "threshold": "0.20 IB (160 A)", "time_delay": "0.00 s", "action": "Cắt MC 171 ĐMT Mỹ Hiệp & 171 Phù Mỹ 220", "note": "So lệch dòng điện đường dây"},
            {"function": "F87L", "stage": "Cấp 2 (IdUnre)", "threshold": "4.00 IB (3200 A)", "time_delay": "0.00 s", "action": "Cắt MC 171 ĐMT Mỹ Hiệp & 171 Phù Mỹ 220", "note": "Cắt tức thời không hãm"},
            {"function": "F21", "stage": "Zone 1", "threshold": "X1 = 4.90 Ω (R1=1.92Ω, X0=14.70Ω)", "time_delay": "0.00 s", "action": "Cắt MC 171", "note": "80-85% chiều dài đường dây 14.83km"},
            {"function": "F21", "stage": "Zone 2", "threshold": "X2 = 7.35 Ω (R1=2.88Ω, X0=22.04Ω)", "time_delay": "0.60 s", "action": "Cắt MC 171", "note": "Bảo vệ dự phòng đoạn 1"},
            {"function": "F21", "stage": "Zone 3", "threshold": "X3 = 28.50 Ω (R1=9.43Ω, X0=84.06Ω)", "time_delay": "3.30 s", "action": "Cắt MC 171", "note": "Bảo vệ dự phòng đoạn 2 (Nhìn về phía Phù Mỹ)"},
            {"function": "F85", "stage": "Kênh truyền bảo vệ", "threshold": "SchemeType = POR (Permissive OR)", "time_delay": "0.00 s", "action": "Cắt MC 171 & Truyền tín hiệu cắt Phù Mỹ 220", "note": "Phối hợp liên động cắt 2 đầu ĐZ"},
            {"function": "F67", "stage": "Cấp 1 (I>)", "threshold": "30% IB (240 A)", "time_delay": "3.00 s", "action": "Cắt MC 171", "note": "Quá dòng có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "F67", "stage": "Cấp 2 (I>>)", "threshold": "40% IB (320 A)", "time_delay": "0.90 s", "action": "Cắt MC 171", "note": "Quá dòng có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "F67N", "stage": "Cấp 1 (IN>)", "threshold": "40% IB (320 A)", "time_delay": "3.00 s", "action": "Cắt MC 171", "note": "Chạm đất có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "F67N", "stage": "Cấp 2 (IN>>)", "threshold": "180% IB (1440 A)", "time_delay": "0.90 s", "action": "Cắt MC 171", "note": "Chạm đất có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "F25/79", "stage": "Hòa đồng bộ & TĐL", "threshold": "ΔU = 10%V, Δf = 0.20Hz, φ = 30°", "time_delay": "1.00 s (TĐL 3 pha 1 lần)", "action": "Cho phép đóng lại MC 171", "note": "Đóng lặp lại khi thỏa mãn điều kiện"}
        ],
        "detailed_settings": [
            # Analog Inputs
            {"group": "Analog Inputs", "param": "CTStarPoint1", "desc": "CT connection towards protected object", "value": "1 (Towards Object)", "unit": "-", "note": "TI pha A"},
            {"group": "Analog Inputs", "param": "CTPrim1", "desc": "Rated CT primary current", "value": "800", "unit": "A", "note": "TI pha A"},
            {"group": "Analog Inputs", "param": "CTSec1", "desc": "Rated CT secondary current", "value": "1", "unit": "A", "note": "TI pha A"},
            {"group": "Analog Inputs", "param": "VTPrim7", "desc": "Rated VT primary voltage", "value": "115", "unit": "kV", "note": "TU TC C11"},
            {"group": "Analog Inputs", "param": "VTSec7", "desc": "Rated VT secondary voltage", "value": "110", "unit": "V", "note": "TU TC C11"},
            # F87L
            {"group": "F87L Differential", "param": "DiffMode", "desc": "Differential function mode", "value": "0 (Master)", "unit": "-", "note": "Master Mode"},
            {"group": "F87L Differential", "param": "IdMin", "desc": "Restrained charact. sensitivity", "value": "0.20", "unit": "IB", "note": "160 A"},
            {"group": "F87L Differential", "param": "IdUnre", "desc": "Unrestrained diff current limit", "value": "4.00", "unit": "IB", "note": "3200 A"},
            {"group": "F87L Differential", "param": "OpenCTEnable", "desc": "Open CT enable Off/On", "value": "1 (On)", "unit": "-", "note": "Hở mạch TI"},
            {"group": "F87L Differential", "param": "tOCTResetDelay", "desc": "Reset delay after diff activate", "value": "0.25", "unit": "s", "note": ""},
            {"group": "F87L Differential", "param": "IdiffAlarm", "desc": "Sustained diff current alarm", "value": "0.15", "unit": "IB", "note": "120 A"},
            {"group": "F87L Differential", "param": "tAlarmDelay", "desc": "Alarm delay for sustained diff", "value": "2.00", "unit": "s", "note": ""},
            # F85 Scheme Comm
            {"group": "F85 Scheme Comm", "param": "CurrRev", "desc": "Current reversal logic", "value": "1 (On)", "unit": "-", "note": "tPickUp=0.02s, tDelay=0.06s"},
            {"group": "F85 Scheme Comm", "param": "WEI", "desc": "Weak End Infeed logic", "value": "2 (Echo & Trip)", "unit": "-", "note": "Nguồn yếu đầu đường dây"},
            {"group": "F85 Scheme Comm", "param": "UPP< / UPN<", "desc": "Undervoltage detection of fault", "value": "70 / 70", "unit": "%UB", "note": ""},
            {"group": "F85 Scheme Comm", "param": "SchemeType", "desc": "Scheme type", "value": "3 (Permissive OR)", "unit": "-", "note": "POR"},
            # Fault Locator
            {"group": "Fault Locator (FL)", "param": "LineLength", "desc": "Length of transmission line", "value": "14.83", "unit": "km", "note": "Chiều dài ĐZ 110kV Lộ 171"},
            {"group": "Fault Locator (FL)", "param": "R1L / X1L", "desc": "Pos seq line resistance & reactance", "value": "2.40 / 6.13", "unit": "Ohm/p", "note": "Tổng trở thứ tự thuận"},
            {"group": "Fault Locator (FL)", "param": "R0L / X0L", "desc": "Zero seq line resistance & reactance", "value": "4.63 / 18.37", "unit": "Ohm/p", "note": "Tổng trở thứ tự không"},
            {"group": "Fault Locator (FL)", "param": "R1A / X1A", "desc": "Source impedance A (near end)", "value": "98.14 / 255.82", "unit": "Ohm/p", "note": "Phía TBA Mỹ Hiệp"},
            {"group": "Fault Locator (FL)", "param": "R1B / X1B", "desc": "Source impedance B (far end)", "value": "3.16 / 9.79", "unit": "Ohm/p", "note": "Phía TBA Phù Mỹ 220"},
            # F21 Distance
            {"group": "F21 Zone 1", "param": "X1PPZ1 / R1PPZ1", "desc": "Positive seq reactance & resistance", "value": "4.90 / 1.92", "unit": "Ohm/p", "note": "Tứ giác (Quadrilateral)"},
            {"group": "F21 Zone 1", "param": "X0Z1 / R0Z1", "desc": "Zero seq reactance & resistance", "value": "14.70 / 3.70", "unit": "Ohm/p", "note": ""},
            {"group": "F21 Zone 1", "param": "RFPPZ1 / RFPEZ1", "desc": "Fault resistance reach Ph-Ph / Ph-E", "value": "20.0 / 20.0", "unit": "Ohm/l", "note": ""},
            {"group": "F21 Zone 1", "param": "tPPZ1 / tPEZ1", "desc": "Time delay to trip Zone 1", "value": "0.00 / 0.00", "unit": "s", "note": "Cắt tức thời MC 171"},
            {"group": "F21 Zone 2", "param": "X1Z2 / R1Z2", "desc": "Pos seq reach Zone 2", "value": "7.35 / 2.88", "unit": "Ohm/p", "note": ""},
            {"group": "F21 Zone 2", "param": "X0Z2 / R0Z2", "desc": "Zero seq reach Zone 2", "value": "22.04 / 5.55", "unit": "Ohm/p", "note": ""},
            {"group": "F21 Zone 2", "param": "RFPPZ2 / RFPEZ2", "desc": "Fault resistance reach Zone 2", "value": "30.0 / 30.0", "unit": "Ohm/l", "note": ""},
            {"group": "F21 Zone 2", "param": "tPPZ2 / tPEZ2", "desc": "Time delay to trip Zone 2", "value": "0.60 / 0.60", "unit": "s", "note": "Thời gian trễ Zone 2"},
            {"group": "F21 Zone 3", "param": "X1Z3 / R1Z3", "desc": "Pos seq reach Zone 3 (Forward)", "value": "28.50 / 9.43", "unit": "Ohm/p", "note": "Hướng Forward"},
            {"group": "F21 Zone 3", "param": "X0Z3 / R0Z3", "desc": "Zero seq reach Zone 3", "value": "84.06 / 25.66", "unit": "Ohm/p", "note": ""},
            {"group": "F21 Zone 3", "param": "RFPPZ3 / RFPEZ3", "desc": "Fault resistance reach Zone 3", "value": "40.0 / 40.0", "unit": "Ohm/l", "note": ""},
            {"group": "F21 Zone 3", "param": "tPPZ3 / tPEZ3", "desc": "Time delay to trip Zone 3", "value": "3.30 / 3.30", "unit": "s", "note": "Thời gian trễ Zone 3"},
            # F68 Power Swing
            {"group": "F68 Power Swing", "param": "X1InFw / R1LIn", "desc": "Inner boundary forward", "value": "65.00 / 12.50", "unit": "Ohm/p", "note": "Dao động công suất"},
            {"group": "F68 Power Swing", "param": "RLDOutFw / ArgLd", "desc": "Outer resistive load boundary & angle", "value": "70.00 / 45", "unit": "Ohm/p / Deg", "note": ""},
            # F67 Overcurrent
            {"group": "F67 Overcurrent", "param": "DirMode1 / I1> / t1", "desc": "OC Step 1 setting", "value": "Forward / 30% IB / 3.00s", "unit": "-", "note": "IEC Def. Time, RCA=55°"},
            {"group": "F67 Overcurrent", "param": "DirMode2 / I2> / t2", "desc": "OC Step 2 setting", "value": "Forward / 40% IB / 0.90s", "unit": "-", "note": "IEC Def. Time"},
            # F67N Earth Fault
            {"group": "F67N Earth Fault", "param": "DirMode1 / IN1> / t1", "desc": "EF Step 1 setting", "value": "Forward / 40% IB / 3.00s", "unit": "-", "note": "Zero seq, RCA=65°"},
            {"group": "F67N Earth Fault", "param": "DirMode2 / IN2> / t2", "desc": "EF Step 2 setting", "value": "Forward / 180% IB / 0.90s", "unit": "-", "note": "HarmBlock1 = On"},
            # F25 / F79
            {"group": "F25 Synchrocheck", "param": "FreqDiffMax / PhaseDiffM", "desc": "Max frequency & phase diff", "value": "0.20 Hz / 30.0 Deg", "unit": "-", "note": "ΔU = 10%V"},
            {"group": "F79 Auto-Reclosing", "param": "ARMode / tReclaim / tSync", "desc": "Auto-reclose config", "value": "3 phase / 180.00s / 3.0s", "unit": "-", "note": "TĐL 3 pha 1 lần"}
        ],
        "notes": [
            "Chức năng F79 khởi tạo từ tín hiệu Trip của bảo vệ 87L, Z1, Z2, POTT.",
            "Đóng lặp lại 3 pha 1 lần khi thỏa mãn điều kiện 'DL/LB' hoặc 'LL/DB' hoặc 'LL/LB' và thỏa mãn điều kiện hòa đồng bộ F25."
        ]
    },
    
    "A3-02-2020/MYHS110": {
        "sheet_id": "A3-02-2020/MYHS110",
        "title": "Phiếu Chỉnh Định Rơ Le REF 615 - Bảo Vệ Quá Dòng Hợp Bộ (Kèm 59/27) XT 171",
        "station": "Trạm 110kV ĐMT Mỹ Hiệp",
        "protected_device": "XT 171 ĐMT Mỹ Hiệp – Phù Mỹ 220",
        "circuit_breaker": "171",
        "decision_no": "1742/QĐ-ĐĐMT ngày 08/09/2020",
        "relay_model": "REF 615",
        "relay_order_code": "HBFNAEAGNCA1AAA11G",
        "manufacturer": "ABB",
        "year": 2020,
        "panel": "E02 +CRP2 (Mạch 1)",
        "software": "PCM600",
        "protection_type": "Bảo vệ quá dòng hợp bộ (Kèm 59/27)",
        "ct_ratio": "800/1A - TI MC 171",
        "vt_ratio": "115/√3 / 0.11/√3 kV - TU 171",
        "summary_table": [
            {"function": "67", "stage": "Cấp 1 (I>)", "threshold": "0.30 In (240 A)", "time_delay": "3.00 s", "action": "Cắt MC 171", "note": "Quá dòng pha có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "67", "stage": "Cấp 2 (I>>)", "threshold": "0.40 In (320 A)", "time_delay": "0.90 s", "action": "Cắt MC 171", "note": "Quá dòng pha có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "67N", "stage": "Cấp 1 (IN>)", "threshold": "0.40 In (320 A)", "time_delay": "3.00 s", "action": "Cắt MC 171", "note": "Quá dòng chạm đất có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "67N", "stage": "Cấp 2 (IN>>)", "threshold": "1.80 In (1440 A)", "time_delay": "0.90 s", "action": "Cắt MC 171", "note": "Quá dòng chạm đất có hướng ra ĐZ (IEC Def. Time)"},
            {"function": "59", "stage": "Quá áp (U>)", "threshold": "U >= 1.21 Un (139.15 kV)", "time_delay": "2.10 s (2100 ms)", "action": "Cắt MC 171", "note": "Bảo vệ quá điện áp thanh cái/đường dây"},
            {"function": "27", "stage": "Kém áp (U<)", "threshold": "U <= 0.80 Un (92.00 kV)", "time_delay": "9.00 s (9000 ms)", "action": "Báo tín hiệu", "note": "Bảo vệ kém điện áp hệ thống"}
        ],
        "detailed_settings": [
            {"group": "Analog Inputs", "param": "Primary voltage", "desc": "VT Primary Rated Voltage", "value": "115.00", "unit": "kV", "note": "TU 171"},
            {"group": "Analog Inputs", "param": "Secondary voltage", "desc": "VT Secondary Rated Voltage", "value": "110.00", "unit": "V", "note": ""},
            {"group": "67-1 DPHLPDOC", "param": "Start value / Operate delay", "desc": "I> Pickup & Time delay", "value": "0.30 In / 3.00 s", "unit": "-", "note": "Forward, RCA=60°, IEC Def. Time"},
            {"group": "67-2 DPHHPDOC", "param": "Start value / Operate delay", "desc": "I>> Pickup & Time delay", "value": "0.40 In / 0.90 s", "unit": "-", "note": "Forward, RCA=60°, IEC Def. Time"},
            {"group": "67N-1 DEFLPDEEF", "param": "Start value / Operate delay", "desc": "IN> Pickup & Time delay", "value": "0.40 In / 3.00 s", "unit": "-", "note": "Forward, RCA=-60°, Zero seq"},
            {"group": "67N-2 DEFHPDEF", "param": "Start value / Operate delay", "desc": "IN>> Pickup & Time delay", "value": "1.80 In / 0.90 s", "unit": "-", "note": "Forward, RCA=-60°, Zero seq"},
            {"group": "59 PHPTOV1", "param": "Start value / Operate delay", "desc": "Overvoltage Pickup & Delay", "value": "1.21 Un / 2100.00 ms", "unit": "-", "note": "Cắt MC 171"},
            {"group": "27 PHPTUV1", "param": "Start value / Operate delay", "desc": "Undervoltage Pickup & Delay", "value": "0.80 Un / 9000.00 ms", "unit": "-", "note": "Báo tín hiệu"}
        ],
        "notes": [
            "Khi dùng MC 171 đóng xung kích đề nghị chỉnh các giá trị t1 (F67, F67N) = 0.50 s. Sau khi đóng xung kích xong đề nghị chỉnh định lại theo giá trị ghi trong phiếu chỉnh định.",
            "Đề nghị kiểm tra đấu nối cực tính và góc pha để bảo vệ tác động đúng hướng.",
            "Hướng tác động của bảo vệ là hướng ra đường dây."
        ]
    },

    "A3-03-2020/MYHS110": {
        "sheet_id": "A3-03-2020/MYHS110",
        "title": "Phiếu Chỉnh Định Rơ Le REC 670 - Kiểm Tra Đồng Bộ XT 171",
        "station": "Trạm 110kV ĐMT Mỹ Hiệp",
        "protected_device": "XT 171 ĐMT Mỹ Hiệp – Phù Mỹ 220",
        "circuit_breaker": "171",
        "decision_no": "1742/QĐ-ĐĐMT ngày 08/09/2020",
        "relay_model": "REC 670",
        "relay_order_code": "REC670*2.2-A30X00-P23-B1X0-BE-CB-B-B6X0-CE1AE1AE1XXX-PPXXXXXXXXXX",
        "manufacturer": "ABB",
        "year": 2020,
        "panel": "E02 (Mạch 1)",
        "software": "PCM600",
        "protection_type": "Kiểm tra đồng bộ (F25)",
        "ct_ratio": "800/1A - TI MC 171",
        "vt_ratio": "115/√3 / 0.11/√3 kV - TU 171, C11",
        "summary_table": [
            {"function": "F25", "stage": "Hòa đồng bộ tay (Synchrocheck)", "threshold": "Δf = 0.20 Hz, ΔU = 10% UB, φ = 30°", "time_delay": "-", "action": "Đóng MC bằng tay", "note": "Hòa đồng bộ kiểm tra điện áp và góc pha"}
        ],
        "detailed_settings": [
            {"group": "Analog Input", "param": "CTSec / CTPrim", "desc": "CT Rating", "value": "1A / 800A", "unit": "-", "note": "CT chân sứ"},
            {"group": "Analog Input", "param": "VTSec / VTPrim", "desc": "VT Rating", "value": "110V / 115kV", "unit": "-", "note": ""},
            {"group": "F25 Synchrocheck", "param": "Operation", "desc": "Operation Mode", "value": "ON", "unit": "-", "note": "Đóng MC bằng tay"},
            {"group": "F25 Synchrocheck", "param": "FreqDiffMin / FreqDiffMax", "desc": "Frequency Difference Limits", "value": "0.01 Hz / 0.20 Hz", "unit": "Hz", "note": ""},
            {"group": "F25 Synchrocheck", "param": "FreqRateChange", "desc": "Rate of change of frequency", "value": "0.30", "unit": "Hz/s", "note": ""},
            {"group": "F25 Synchrocheck", "param": "tBreaker / tClosePulse", "desc": "Breaker operating time & pulse", "value": "0.50 s / 0.80 s", "unit": "s", "note": ""},
            {"group": "F25 Synchrocheck", "param": "UDiffSC / PhaseDiffM", "desc": "Voltage diff & Phase angle diff limit", "value": "10.0% UB / 30.0 Deg", "unit": "-", "note": ""},
            {"group": "F25 Synchrocheck", "param": "AutoEnerg / ManEnerg", "desc": "Energizing Check Mode", "value": "Off / Both (ManEnergDBDL=On)", "unit": "-", "note": "tAuto=1.00s, tMan=1.00s"}
        ],
        "notes": [
            "Kiểm tra đấu nối cực tính TI/TU để đảm bảo chức năng hòa đồng bộ hoạt động chính xác.",
            "Phục vụ đóng điện bằng tay máy cắt 171 an toàn."
        ]
    },

    "A3-04-2020/MYHS110": {
        "sheet_id": "A3-04-2020/MYHS110",
        "title": "Phiếu Chỉnh Định Rơ Le REB 670 - Bảo Vệ So Lệch Thanh Cái 110kV & 50BF",
        "station": "Trạm 110kV ĐMT Mỹ Hiệp",
        "protected_device": "Thanh cái 110kV (TBA 110kV Mỹ Hiệp)",
        "circuit_breaker": "171, 131",
        "decision_no": "1742/QĐ-ĐĐMT ngày 08/09/2020",
        "relay_model": "REB 670",
        "relay_order_code": "REB670*2.2-A20X01-C06C10P23-B1X0-AX-CB-B-B1X0-CE1E1A-PPXXXXXXXXXX",
        "manufacturer": "ABB",
        "year": 2020,
        "panel": "CRP2 +E02 (Mạch 1)",
        "software": "PCM600",
        "protection_type": "Bảo vệ so lệch thanh cái hợp bộ (87B, 50BF, Intertrip)",
        "ct_ratio": "800/1A (TI MC 171, E02), 300/1A (TI MC 131, E01)",
        "vt_ratio": "115/√3 / 0.11/√3 kV - TU C11",
        "summary_table": [
            {"function": "87B", "stage": "So lệch thanh cái", "threshold": "Idiff = 560 A", "time_delay": "0.00 s", "action": "Cắt các MC nối vào TC 110kV (MC 171, MC 131)", "note": "Slope = 0.15, OperLevel = 1000A"},
            {"function": "50BF", "stage": "Hư hỏng máy cắt", "threshold": "IP = 20% IB, IN = 20% IB", "time_delay": "t1 = 0.10s (cắt lại) / t2 = 0.20s (cắt liên quan)", "action": "Cắt lại MC & Cắt các MC liên quan 110kV", "note": "Khởi tạo từ Trip 3 pha các ngăn E0x"},
            {"function": "Intertrip", "stage": "Cắt liên động", "threshold": "50BF đầu đối diện", "time_delay": "0.00 s", "action": "Cắt MC 171", "note": "Nhận lệnh liên động từ TBA Phù Mỹ 220"}
        ],
        "detailed_settings": [
            {"group": "Analog Inputs", "param": "CT_WyePoint1-3 (E01)", "desc": "CT E01 (MC 131 - MBA T1)", "value": "300 / 1 A", "unit": "-", "note": "FromObject, TI pha A, B, C ngăn 131"},
            {"group": "Analog Inputs", "param": "CT_WyePoint4-6 (E02)", "desc": "CT E02 (MC 171 - XT 171)", "value": "800 / 1 A", "unit": "-", "note": "TI pha A, B, C ngăn 171"},
            {"group": "87B BCZTPDIF", "param": "OperLevel / Slope", "desc": "Operating current level & Slope", "value": "1000 A / 0.15", "unit": "-", "note": "Đặc tuyến hãm so lệch"},
            {"group": "87B BZNTPDIF", "param": "DiffOperLev / tTripHold", "desc": "Diff current operate & Trip hold", "value": "560.00 A / 0.20 s", "unit": "-", "note": "Cắt các MC nối vào TC"},
            {"group": "87B BZNTPDIF", "param": "OCTOperLev / tSlowOCT", "desc": "Open CT current & slow delay", "value": "200.00 A / 20.00 s", "unit": "-", "note": "Khóa khi hở mạch TI"},
            {"group": "87B BZNTPDIF", "param": "IdAlarmLev / IinAlarmLev", "desc": "Alarm levels for diff & in currents", "value": "200.00 A / 3000.00 A", "unit": "-", "note": "tIdAlarm = 30.00 s"},
            {"group": "87B BZNTPDIF", "param": "SensOperLev / SensIInBlock", "desc": "Sensitive diff current level & block", "value": "560.00 A / 1000.00 A", "unit": "-", "note": "tSensDiff = 0.40 s"},
            {"group": "50BF CCRBRF", "param": "IP> / IN>", "desc": "Phase & Residual current pickup", "value": "20.0 %IB / 20.0 %IB", "unit": "-", "note": "Dòng khởi động 50BF"},
            {"group": "50BF CCRBRF", "param": "t1 / t2 / t2MPh", "desc": "Time delay step 1 & step 2", "value": "0.10 s / 0.20 s / 0.20 s", "unit": "s", "note": "t1: Cắt lại MC, t2: Cắt MC liên quan"},
            {"group": "50BF CCRBRF", "param": "tCBAlarm / tPulse", "desc": "CB Alarm delay & Output pulse", "value": "5.00 s / 0.20 s", "unit": "s", "note": ""}
        ],
        "notes": [
            "Chức năng bảo vệ 50BF MC 131 tương tự MC 171.",
            "Đề nghị kiểm tra cực tính của TI phù hợp với thực tế để bảo vệ so lệch tác động chính xác tuyệt đối."
        ]
    }
}


# =========================================================================
# CÁC HÀM TRUY VẤN, ĐỐI SOÁT & XUẤT BÁO CÁO EXCEL
# =========================================================================

def get_all_relay_setting_sheets():
    """Trả về toàn bộ danh mục phiếu chỉnh định rơ le"""
    return RELAY_SETTING_SHEETS

def get_setting_sheet_by_id(sheet_id):
    """Truy vấn thông tin chi tiết một phiếu chỉnh định theo ID"""
    return RELAY_SETTING_SHEETS.get(sheet_id, None)

def evaluate_fault_against_settings(measured_fault_data):
    """
    Hàm đối soát tự động: So sánh dữ liệu đo đếm sự cố thực tế với trị số chỉnh định A3
    measured_fault_data: dict chứa {
        'fault_type': 'F21' | 'F87L' | 'F67' | 'F67N' | 'F87B' | 'F59' | 'F27',
        'current_ka': float,
        'reactance_ohm': float (cho F21),
        'voltage_kv': float (cho 59/27),
        'duration_ms': float,
        'direction': 'Forward' | 'Reverse'
    }
    """
    ftype = measured_fault_data.get('fault_type', '').upper()
    eval_result = {
        'expected_relay': '--',
        'expected_stage': '--',
        'expected_time_s': '--',
        'is_normal_trip': False,
        'diagnosis_note': ''
    }
    
    # 1. Bảo vệ khoảng cách F21 (RED 670)
    if '21' in ftype or 'DISTANCE' in ftype:
        X = measured_fault_data.get('reactance_ohm', 999.0)
        t_ms = measured_fault_data.get('duration_ms', 0.0)
        eval_result['expected_relay'] = 'RED 670 (Lộ 171)'
        
        if X <= 4.90:
            eval_result['expected_stage'] = 'Zone 1 (X1 <= 4.90 Ω)'
            eval_result['expected_time_s'] = '0.00 s (Tức thời)'
            eval_result['is_normal_trip'] = (t_ms <= 80.0)  # Cắt tức thời <= 80ms cả thời gian cơ khí MC
            eval_result['diagnosis_note'] = f'Sự cố nằm trong vùng Zone 1 (X={X:.2f}Ω <= 4.90Ω). Rơ le RED 670 tác động cắt tức thời không thời gian trễ.'
        elif X <= 7.35:
            eval_result['expected_stage'] = 'Zone 2 (4.90 < X2 <= 7.35 Ω)'
            eval_result['expected_time_s'] = '0.60 s'
            eval_result['is_normal_trip'] = (550.0 <= t_ms <= 750.0)
            eval_result['diagnosis_note'] = f'Sự cố nằm trong vùng Zone 2 (X={X:.2f}Ω). Rơ le RED 670 tác động sau thời gian trễ chỉnh định 0.60s.'
        elif X <= 28.50:
            eval_result['expected_stage'] = 'Zone 3 (7.35 < X3 <= 28.50 Ω)'
            eval_result['expected_time_s'] = '3.30 s'
            eval_result['is_normal_trip'] = (3200.0 <= t_ms <= 3500.0)
            eval_result['diagnosis_note'] = f'Sự cố nằm trong vùng Zone 3 (X={X:.2f}Ω). Rơ le RED 670 tác động sau thời gian trễ chỉnh định 3.30s.'
        else:
            eval_result['expected_stage'] = 'Ngoài vùng bảo vệ F21 (> 28.50 Ω)'
            eval_result['expected_time_s'] = '--'
            eval_result['is_normal_trip'] = False
            eval_result['diagnosis_note'] = f'Tổng trở đo được X={X:.2f}Ω vượt quá phạm vi Zone 3. F21 không khởi phát.'

    # 2. Bảo vệ so lệch đường dây F87L (RED 670)
    elif '87L' in ftype or 'DIFF_LINE' in ftype:
        Idiff_A = measured_fault_data.get('current_ka', 0.0) * 1000.0
        t_ms = measured_fault_data.get('duration_ms', 0.0)
        eval_result['expected_relay'] = 'RED 670 (Lộ 171)'
        
        if Idiff_A >= 3200.0:
            eval_result['expected_stage'] = 'F87L Cấp 2 (IdUnre >= 4.00 IB = 3200A)'
            eval_result['expected_time_s'] = '0.00 s (Không hãm)'
            eval_result['is_normal_trip'] = (t_ms <= 60.0)
            eval_result['diagnosis_note'] = f'Dòng so lệch Idiff={Idiff_A:.0f}A vượt ngưỡng không hãm IdUnre (3200A). Tác động cắt tức thời 2 đầu ĐZ 171.'
        elif Idiff_A >= 160.0:
            eval_result['expected_stage'] = 'F87L Cấp 1 (IdMin >= 0.20 IB = 160A)'
            eval_result['expected_time_s'] = '0.00 s'
            eval_result['is_normal_trip'] = (t_ms <= 80.0)
            eval_result['diagnosis_note'] = f'Dòng so lệch Idiff={Idiff_A:.0f}A vượt ngưỡng hãm IdMin (160A). Tác động cắt có hãm 2 đầu ĐZ 171.'

    # 3. Bảo vệ so lệch thanh cái F87B (REB 670)
    elif '87B' in ftype or 'BUS' in ftype:
        Idiff_A = measured_fault_data.get('current_ka', 0.0) * 1000.0
        eval_result['expected_relay'] = 'REB 670 (Thanh Cái 110kV)'
        if Idiff_A >= 560.0:
            eval_result['expected_stage'] = 'F87B So Lệch Thanh Cái (Idiff >= 560A)'
            eval_result['expected_time_s'] = '0.00 s'
            eval_result['is_normal_trip'] = True
            eval_result['diagnosis_note'] = f'Dòng so lệch thanh cái Idiff={Idiff_A:.0f}A >= 560A. Rơ le REB 670 phát lệnh cắt tức thời toàn bộ MC 171 & MC 131.'

    # 4. Quá dòng có hướng F67 / F67N (REF 615 / RED 670)
    elif '67' in ftype:
        I_A = measured_fault_data.get('current_ka', 0.0) * 1000.0
        eval_result['expected_relay'] = 'REF 615 / RED 670'
        if I_A >= 320.0:
            eval_result['expected_stage'] = 'F67 Cấp 2 (I>> >= 40% IB = 320A)'
            eval_result['expected_time_s'] = '0.90 s'
            eval_result['is_normal_trip'] = True
            eval_result['diagnosis_note'] = f'Dòng quá dòng I={I_A:.0f}A >= 320A (Hướng ra ĐZ). Tác động sau thời gian trễ 0.90s.'
        elif I_A >= 240.0:
            eval_result['expected_stage'] = 'F67 Cấp 1 (I> >= 30% IB = 240A)'
            eval_result['expected_time_s'] = '3.00 s'
            eval_result['is_normal_trip'] = True
            eval_result['diagnosis_note'] = f'Dòng quá dòng I={I_A:.0f}A >= 240A (Hướng ra ĐZ). Tác động sau thời gian trễ 3.00s.'

    return eval_result


def export_all_relay_settings_to_excel_bytes():
    """Xuất toàn bộ 04 phiếu chỉnh định A3 thành file Excel chuyên nghiệp nhiều Sheet"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Tổng hợp danh mục
        summary_rows = []
        for sid, sdata in RELAY_SETTING_SHEETS.items():
            summary_rows.append({
                "Số Phiếu A3": sid,
                "Tên Rơ Le": sdata['relay_model'],
                "Mã Đặt Hàng / Serial": sdata['relay_order_code'],
                "Hãng SX": sdata['manufacturer'],
                "Thiết Bị Bảo Vệ": sdata['protected_device'],
                "Máy Cắt": sdata['circuit_breaker'],
                "Tủ Bảo Vệ": sdata['panel'],
                "Tỷ Số Biến Dòng TI": sdata['ct_ratio'],
                "Tỷ Số Biến Điện Áp TU": sdata['vt_ratio'],
                "Chức Năng Chính": sdata['protection_type']
            })
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_excel(writer, sheet_name="DANH MUC RƠ LE A3", index=False)
        
        # Từng Sheet chi tiết cho 4 phiếu
        for sid, sdata in RELAY_SETTING_SHEETS.items():
            sheet_name_clean = sid.replace('/', '_').replace('-', '_')[:31]
            
            # 1. Bảng nguyên tắc tác động
            df_principle = pd.DataFrame(sdata['summary_table'])
            df_principle.to_excel(writer, sheet_name=sheet_name_clean, startrow=3, index=False)
            
            # 2. Bảng cài đặt chi tiết
            df_detail = pd.DataFrame(sdata['detailed_settings'])
            start_detail_row = len(df_principle) + 7
            df_detail.to_excel(writer, sheet_name=sheet_name_clean, startrow=start_detail_row, index=False)
            
            # Ghi tiêu đề vào header
            ws = writer.sheets[sheet_name_clean]
            ws.cell(row=1, column=1, value=f"{sdata['title']} - {sdata['sheet_id']}")
            ws.cell(row=2, column=1, value=f"Thiết bị: {sdata['protected_device']} | MC: {sdata['circuit_breaker']} | Tủ: {sdata['panel']} | Quyết định: {sdata['decision_no']}")
            ws.cell(row=len(df_principle) + 6, column=1, value="CÀI ĐẶT THÔNG SỐ CHI TIẾT THEO PHIẾU CHỈNH ĐỊNH:")
            
    output.seek(0)
    return output.getvalue()
