# -*- coding: utf-8 -*-
"""
Module Đa Ngôn Ngữ (Internationalization - i18n) cho Hệ Thống Dự Báo & Vận Hành ĐMT Mỹ Hiệp
Hỗ trợ chuyển đổi song ngữ Tiếng Việt (VI) và Tiếng Anh (EN).
"""

import streamlit as st

LANG_VI = "vi"
LANG_EN = "en"

LANG_OPTIONS = {
    "vi": "🇻🇳 Tiếng Việt",
    "en": "🇬🇧 English"
}

NAV_OPTIONS_VI = [
    "📊 1. Dự Báo 96 Chu Kỳ Ngày (File Đang Chọn)",
    "⚡ 2. Dự Báo 18 Chu Kỳ Cuốn Chiếu (4.5h)",
    "⚖️ 3. So Sánh & Đánh Giá Sai Số (Thực Tế vs Dự Báo)",
    "🔮 4. Dự Báo Chu Kỳ & Thuyết Minh Thời Tiết (Phù Mỹ Nam)",
    "📈 5. Phân Tích & Đối Soát Lịch Sử 4 Công Tơ (2020 - 2026)",
    "📋 6. Báo Cáo Vận Hành & Hiệu Suất PR (IEC 61724)",
    "🚨 7. Chẩn Đoán Bất Thường Inverter (S1 - S7 SCADA)",
    "🔌 8. Giám Sát & Chẩn Đoán 4.058 Chuỗi String DC (D:\\STRING_INV)",
    "📑 9. Đọc & Giải Mã Log Biến Tần Huawei (D:\\LOG)",
    "🛡️ 10. Phân Tích Sự Cố Rơ Le Bảo Vệ (D:\\PT_RL)"
]

NAV_OPTIONS_EN = [
    "📊 1. 96-Interval Daily Forecast (Active File)",
    "⚡ 2. 18-Interval Rolling Forecast (4.5h)",
    "⚖️ 3. Forecast vs Actual Error Evaluation",
    "🔮 4. Multi-Cycle Forecast & Weather Statement (Phu My Nam)",
    "📈 5. Historical Analysis & 4-Meter Audit (2020 - 2026)",
    "📋 6. PR & Operations Performance Report (IEC 61724)",
    "🚨 7. Inverter Anomaly Diagnostics (S1 - S7 SCADA)",
    "🔌 8. 4,058 DC String Monitoring & Diagnostics (D:\\STRING_INV)",
    "📑 9. Huawei Inverter Log Reader & Decoder (D:\\LOG)",
    "🛡️ 10. Protection Relay Fault Analysis (D:\\PT_RL)"
]

TRANSLATIONS = {
    "vi": {
        # App Header & Banner
        "page_title": "NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - Dự Báo Sản Lượng 15 Phút",
        "plant_title": "NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP",
        "plant_subtitle": "HỆ THỐNG DỰ BÁO SẢN LƯỢNG QUANG ĐIỆN 15 PHÚT (EVN / A0 / A3)",
        "telemetry_live": "TELEMETRY SCADA LIVE",
        "badge_dc": "DC: 50.00 MWp",
        "badge_ac": "AC Inverter: 40.075 MW",
        "badge_panel": "Sharp NU-440 (-0.347%/°C)",
        "badge_grid": "TBA 110kV Mỹ Hiệp ⇌ 220kV Phù Mỹ (Lộ 171)",
        "badge_location": "Phù Mỹ Nam, T. Gia Lai",
        
        # Sidebar
        "lang_select_label": "🌐 Chuyển Đổi Ngôn Ngữ / Language:",
        "sidebar_nav_header": "DANH MỤC ĐIỀU HÀNH HỆ THỐNG",
        "sidebar_scada_date": "📂 Chọn Ngày Dữ Liệu SCADA",
        "scada_date_select": "Ngày SCADA:",
        "btn_load_date": "🔄 Nạp Dữ Liệu Ngày Này",
        "btn_rescan_server": "⚡ Quét Lại Server",
        "sidebar_tech_config": "⚙️ Cấu Hình Thông Số Kỹ Thuật (50MWp / 40.075MW)",
        "plant_subtitle_sb": "🏢 Nhà Máy ĐMT Mỹ Hiệp - Phù Mỹ",
        "dc_capacity_label": "⚡ Công suất DC tấm pin (MWp)",
        "ac_capacity_label": "🔌 Giới hạn Inverter AC (MW)",
        "dc_ac_ratio": "Tỉ số DC/AC:",
        "temp_coeff_label": "Hệ số nhiệt độ Pmp (%/°C)",
        "noct_label": "Nhiệt độ danh định cell NOCT (°C)",
        "loss_factors": "Hệ số tổn thất (%):",
        "soiling_loss": "Tổn thất bụi bẩn (Soiling %)",
        "dc_cable_loss": "Tổn thất cáp DC (%)",
        "mismatch_loss": "Tổn thất Mismatch & LID (%)",
        "inv_eff_loss": "Hiệu suất Inverter (%)",
        "trafo_loss": "Tổn thất MBA & Cáp AC (%)",
        "aux_loss": "Tự dùng trạm (%)",
        
        # Auto Sync Sidebar
        "auto_sync_expander": "🤖 Tự Động Đồng Bộ (08:00 Sáng)",
        "auto_sync_schedule_badge": "Lịch: 08:00 Sáng",
        "auto_sync_desc": "Hệ thống tự động đồng bộ SCADA, NWP, String, Meter kể cả khi phần mềm tắt.",
        "last_sync_time": "Lần đồng bộ gần nhất:",
        "sync_status_success": "✅ Trạng thái: Hoàn tất trọn vẹn",
        "sync_status_error": "⚠️ Trạng thái: Có lỗi xảy ra",
        "sync_duration": "Thời gian xử lý:",
        "btn_sync_now": "🚀 Kích Hoạt Đồng Bộ Ngay",
        "sync_running_msg": "Đang chạy đồng bộ toàn diện SCADA, NWP, Inverter, Meter, Relay...",
        "sync_success_msg": "Đã hoàn thành đồng bộ trong {s}s!",
        
        # Common Actions
        "btn_export_excel": "📥 Tải Báo Cáo Excel (.xlsx)",
        "btn_export_csv": "📥 Tải Báo Cáo CSV (.csv)",
        "btn_refresh": "🔄 Làm Mới Dữ Liệu",
        "status_ok": "Bình Thường / Đạt Chuẩn",
        "status_warning": "Cảnh Báo",
        "status_danger": "Nguy Hiểm / Bất Thường",
        "energy_unit": "MWh",
        "power_unit": "MW",
        "irr_unit": "W/m²",
        "temp_unit": "°C"
    },
    "en": {
        # App Header & Banner
        "page_title": "MY HIEP SOLAR POWER PLANT - 15-Minute Generation Forecasting",
        "plant_title": "MY HIEP SOLAR POWER PLANT",
        "plant_subtitle": "15-MINUTE PV GENERATION FORECASTING & DISPATCH SYSTEM (EVN / NLDC / A3)",
        "telemetry_live": "SCADA TELEMETRY LIVE",
        "badge_dc": "DC: 50.00 MWp",
        "badge_ac": "AC Inverter: 40.075 MW",
        "badge_panel": "Sharp NU-440 (-0.347%/°C)",
        "badge_grid": "110kV My Hiep Substation ⇌ 220kV Phu My (Feeder 171)",
        "badge_location": "Phu My Nam, Gia Lai Province",
        
        # Sidebar
        "lang_select_label": "🌐 Language Selection / Ngôn ngữ:",
        "sidebar_nav_header": "SYSTEM OPERATION DISPATCH MENU",
        "sidebar_scada_date": "📂 Select SCADA Data Date",
        "scada_date_select": "SCADA Date:",
        "btn_load_date": "🔄 Load This Date Data",
        "btn_rescan_server": "⚡ Rescan Server",
        "sidebar_tech_config": "⚙️ Technical Parameters Configuration (50MWp / 40.075MW)",
        "plant_subtitle_sb": "🏢 My Hiep Solar Power Plant - Phu My",
        "dc_capacity_label": "⚡ DC Peak Capacity (MWp)",
        "ac_capacity_label": "🔌 AC Inverter Limit (MW)",
        "dc_ac_ratio": "DC/AC Ratio:",
        "temp_coeff_label": "Temperature Coefficient Pmp (%/°C)",
        "noct_label": "Nominal Operating Cell Temp NOCT (°C)",
        "loss_factors": "Loss Factors (%):",
        "soiling_loss": "Soiling Loss (%)",
        "dc_cable_loss": "DC Cable Loss (%)",
        "mismatch_loss": "Mismatch & LID Loss (%)",
        "inv_eff_loss": "Inverter Efficiency (%)",
        "trafo_loss": "Transformer & AC Cable Loss (%)",
        "aux_loss": "Auxiliary / Station Consumption (%)",
        
        # Auto Sync Sidebar
        "auto_sync_expander": "🤖 Background Auto-Sync (08:00 AM)",
        "auto_sync_schedule_badge": "Schedule: 08:00 AM Daily",
        "auto_sync_desc": "Autonomous background sync for SCADA, NWP, String and Meter telemetry.",
        "last_sync_time": "Last Synchronized:",
        "sync_status_success": "✅ Status: Completed Successfully",
        "sync_status_error": "⚠️ Status: Error occurred",
        "sync_duration": "Execution Duration:",
        "btn_sync_now": "🚀 Trigger Immediate Sync",
        "sync_running_msg": "Running full sync across SCADA, NWP, Inverters, Meters, Relays...",
        "sync_success_msg": "Sync completed successfully in {s}s!",
        
        # Common Actions
        "btn_export_excel": "📥 Download Excel Report (.xlsx)",
        "btn_export_csv": "📥 Download CSV Report (.csv)",
        "btn_refresh": "🔄 Refresh Data",
        "status_ok": "Normal / Standard",
        "status_warning": "Warning",
        "status_danger": "Critical / Anomaly",
        "energy_unit": "MWh",
        "power_unit": "MW",
        "irr_unit": "W/m²",
        "temp_unit": "°C"
    }
}

def get_current_lang():
    if "app_lang" not in st.session_state:
        st.session_state.app_lang = LANG_VI
    return st.session_state.app_lang

def set_current_lang(lang_code):
    if lang_code in [LANG_VI, LANG_EN]:
        st.session_state.app_lang = lang_code

def t(key, default=None):
    """Lấy chuỗi dịch theo ngôn ngữ hiện hành"""
    lang = get_current_lang()
    tr = TRANSLATIONS.get(lang, TRANSLATIONS[LANG_VI])
    if key in tr:
        return tr[key]
    if lang != LANG_VI and key in TRANSLATIONS[LANG_VI]:
        return TRANSLATIONS[LANG_VI][key]
    return default if default is not None else key

def get_nav_options():
    lang = get_current_lang()
    return NAV_OPTIONS_EN if lang == LANG_EN else NAV_OPTIONS_VI

def get_nav_index(selected_menu_text):
    """Xác định index menu từ 0 đến 9 bất kể ngôn ngữ hiện tại"""
    if selected_menu_text in NAV_OPTIONS_VI:
        return NAV_OPTIONS_VI.index(selected_menu_text)
    if selected_menu_text in NAV_OPTIONS_EN:
        return NAV_OPTIONS_EN.index(selected_menu_text)
    return 0
