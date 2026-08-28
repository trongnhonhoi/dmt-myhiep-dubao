"""
HỆ THỐNG DỰ BÁO SẢN LƯỢNG ĐIỆN MẶT TRỜI CHU KỲ 15 PHÚT
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP (50MWp / 40.075MW) - PHÙ MỸ, BÌNH ĐỊNH
Giao diện chuyên ngành năng lượng mặt trời hiện đại, trực quan, sinh động
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import io

import base64
import importlib

import solar_engine
import data_harvester
import weather_forecast_engine
import exporter

importlib.reload(solar_engine)
importlib.reload(data_harvester)
importlib.reload(weather_forecast_engine)
importlib.reload(exporter)

from solar_engine import (
    MyHiepSolarPlantConfig,
    robust_decode_bytes,
    detect_and_parse_input_data,
    parse_scada_weather_txt_advanced,
    parse_scada_power_txt_advanced,
    process_actual_power_1min_to_15min,
    calculate_forecast_vs_actual_comparison,
    process_1min_to_15min_forecast,
    forecast_rolling_intervals,
    generate_scada_txt_sample_content,
    generate_scada_power_sample_content,
    recalculate_15min_forecast_kpis,
    process_custom_pw_dataframe,
    process_any_external_scada_or_pw_file
)
from data_harvester import (
    DataHarvester,
    generate_multi_day_15min_forecast,
    forecast_end_of_month,
    forecast_next_month,
    DEFAULT_SERVER_PATH
)
from weather_forecast_engine import (
    fetch_phu_my_weather_forecast,
    convert_nwp_to_15min_dispatch,
    generate_unified_hybrid_forecast,
    forecast_18_rolling_realtime_ai
)
from exporter import (
    export_to_excel_bytes, 
    export_to_csv_bytes, 
    export_multi_day_to_excel_bytes,
    prepare_export_dataframe,
    prepare_comparison_export_dataframe,
    export_comparison_to_excel_bytes,
    export_comparison_to_csv_bytes,
    generate_pw_template_excel_bytes
)

# Cấu hình Logo Electric Bird
LOGO_PATH = os.path.join(os.path.dirname(__file__), "electric_bird_logo.png")
if not os.path.exists(LOGO_PATH):
    LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")

def get_logo_base64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""

logo_b64 = get_logo_base64()

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP - Dự Báo Sản Lượng 15 Phút",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS giao diện Đậm Chất Ngành Năng Lượng Mặt Trời (Solar Power Station Theme)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Hero Banner Header */
    .hero-solar-banner {
        background: linear-gradient(135deg, #0B132B 0%, #1C2541 45%, #002855 80%, #00509D 100%);
        border-radius: 14px;
        padding: 24px 30px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 12px 30px -8px rgba(0, 80, 157, 0.45);
        border: 1px solid rgba(255, 214, 10, 0.2);
        position: relative;
        overflow: hidden;
    }
    .hero-solar-banner::after {
        content: "☀️";
        position: absolute;
        right: 25px;
        top: 15px;
        font-size: 5.5rem;
        opacity: 0.15;
        pointer-events: none;
    }
    .plant-main-title {
        font-size: 2.35rem;
        font-weight: 800;
        letter-spacing: 0.8px;
        text-transform: uppercase;
        background: linear-gradient(90deg, #FFD60A 0%, #FFC300 40%, #00B4D8 85%, #90E0EF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
        line-height: 1.2;
    }
    .plant-sub-title {
        font-size: 1.05rem;
        color: #E2E8F0;
        font-weight: 500;
        margin-bottom: 14px;
    }
    
    /* Solar Badges */
    .solar-badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.84rem;
        font-weight: 600;
        margin-right: 8px;
        margin-bottom: 6px;
    }
    .badge-dc {
        background: rgba(255, 195, 0, 0.18);
        color: #FFD60A;
        border: 1px solid rgba(255, 214, 10, 0.4);
    }
    .badge-ac {
        background: rgba(0, 180, 216, 0.18);
        color: #90E0EF;
        border: 1px solid rgba(0, 180, 216, 0.4);
    }
    .badge-module {
        background: rgba(16, 185, 129, 0.18);
        color: #6EE7B7;
        border: 1px solid rgba(16, 185, 129, 0.4);
    }
    .badge-grid {
        background: rgba(168, 85, 247, 0.18);
        color: #D8B4FE;
        border: 1px solid rgba(168, 85, 247, 0.4);
    }
    
    /* SCADA Server Bar */
    .server-status-card {
        background: linear-gradient(90deg, #F0FDF4 0%, #ECFDF5 100%);
        border: 1px solid #6EE7B7;
        border-left: 5px solid #10B981;
        padding: 12px 18px;
        border-radius: 8px;
        margin-bottom: 18px;
        box-shadow: 0 2px 6px rgba(16, 185, 129, 0.08);
    }
    
    /* BẢN THUYẾT MINH KHÍ TƯỢNG & SẢN LƯỢNG - GIAO DIỆN SẮC NÉT HIỆN ĐẠI */
    .narrative-box {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 22px;
        margin-top: 15px;
        margin-bottom: 20px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
        font-family: 'Plus Jakarta Sans', 'Segoe UI', system-ui, sans-serif;
    }
    .narrative-top-bar {
        border-bottom: 2px solid #F1F5F9;
        padding-bottom: 16px;
        margin-bottom: 18px;
    }
    .narrative-top-title {
        font-size: 1.35rem;
        font-weight: 800;
        color: #0F172A;
        letter-spacing: 0.3px;
        margin-bottom: 6px;
    }
    .narrative-top-meta {
        font-size: 0.92rem;
        color: #475569;
        margin-bottom: 12px;
    }
    .narrative-badge-wrap {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    .nbadge {
        display: inline-flex;
        align-items: center;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.88rem;
        font-weight: 600;
    }
    .nbadge-day {
        background: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
    }
    .nbadge-weather {
        background: #F0FDF4;
        color: #15803D;
        border: 1px solid #BBF7D0;
    }
    .nbadge-energy {
        background: #FEF3C7;
        color: #B45309;
        border: 1px solid #FDE68A;
    }
    .nbadge-peak {
        background: #F3E8FF;
        color: #7E22CE;
        border: 1px solid #E9D5FF;
    }
    
    .narrative-cards-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 16px;
    }
    @media (max-width: 900px) {
        .narrative-cards-grid {
            grid-template-columns: 1fr;
        }
    }
    
    .ncard {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px 18px;
        transition: all 0.2s ease;
    }
    .ncard:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0,0,0,0.05);
    }
    .ncard-weather {
        border-left: 5px solid #0284C7;
    }
    .ncard-power {
        border-left: 5px solid #10B981;
    }
    .ncard-temp {
        border-left: 5px solid #F59E0B;
    }
    .ncard-dispatch {
        border-left: 5px solid #8B5CF6;
    }
    
    .ncard-head {
        font-size: 1.0rem;
        font-weight: 750;
        color: #0F172A;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .ncard-body {
        font-size: 0.94rem;
        color: #334155;
        line-height: 1.65;
    }
    .dispatch-item {
        margin-bottom: 6px;
        line-height: 1.55;
    }
</style>
""", unsafe_allow_html=True)


# --- SIDEBAR CẤU HÌNH THÔNG SỐ VẬN HÀNH ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=190)
    else:
        st.markdown("⚡ **ELECTRIC BIRD**")
    st.markdown("## ⚙️ Cấu Hình Thông Số")
    st.caption("🏢 **Nhà Máy ĐMT Mỹ Hiệp - Phù Mỹ**")
    
    dc_capacity = st.number_input(
        "⚡ Công suất DC tấm pin (MWp)", 
        min_value=1.0, max_value=200.0, 
        value=float(MyHiepSolarPlantConfig.DC_CAPACITY_MWP), 
        step=1.0,
        help="Tổng công suất lắp đặt các tấm pin DC của nhà máy Mỹ Hiệp."
    )

    ac_capacity = st.number_input(
        "🔌 Giới hạn Inverter AC (MW)", 
        min_value=1.0, max_value=200.0, 
        value=float(MyHiepSolarPlantConfig.AC_CAPACITY_MW), 
        step=0.025,
        format="%.3f",
        help="Tổng công suất định mức xoay chiều AC của hệ thống Inverter."
    )

    st.markdown(f"**Tỉ số DC/AC:** `{dc_capacity / ac_capacity:.3f}` *(Over-paneling: {(dc_capacity/ac_capacity - 1)*100:.1f}%)*")

    with st.expander("🔧 Thông số Tấm Pin Sharp NU-440", expanded=False):
        st.caption("Datasheet: Sharp NU-440 (NU-JD440) Monocrystalline")
        temp_coeff_pct = st.number_input(
            "Hệ số nhiệt độ Pmp (%/°C)", 
            value=-0.347, 
            step=0.01, 
            format="%.3f",
            help="Hệ số suy giảm công suất khi nhiệt độ cell > 25°C."
        )
        temp_coeff = temp_coeff_pct / 100.0
        
        noct_val = st.number_input(
            "Nhiệt độ danh định cell NOCT (°C)", 
            value=float(MyHiepSolarPlantConfig.NOCT_C), 
            step=1.0
        )

    with st.expander("📉 Các Hệ số Tổn thất Kỹ thuật (%)", expanded=False):
        soiling_pct = st.slider("Tổn thất bụi bẩn (Soiling %)", 0.0, 10.0, MyHiepSolarPlantConfig.DEFAULT_SOILING_LOSS * 100.0, 0.1)
        dc_cable_pct = st.slider("Tổn thất cáp DC (%)", 0.0, 5.0, MyHiepSolarPlantConfig.DEFAULT_DC_CABLE_LOSS * 100.0, 0.1)
        mismatch_pct = st.slider("Tổn thất Mismatch & LID (%)", 0.0, 5.0, MyHiepSolarPlantConfig.DEFAULT_MISMATCH_LID_LOSS * 100.0, 0.1)
        inv_eff_pct = st.slider("Hiệu suất Inverter (%)", 90.0, 99.5, MyHiepSolarPlantConfig.DEFAULT_INVERTER_EFF * 100.0, 0.1)
        trafo_loss_pct = st.slider("Tổn thất MBA & Cáp AC (%)", 0.0, 5.0, MyHiepSolarPlantConfig.DEFAULT_AC_TRAFO_LOSS * 100.0, 0.1)
        aux_loss_pct = st.slider("Tự dùng trạm (%)", 0.0, 2.0, MyHiepSolarPlantConfig.DEFAULT_AUX_LOSS * 100.0, 0.1)

calc_params = {
    'dc_capacity_mwp': dc_capacity,
    'ac_capacity_mw': ac_capacity,
    'temp_coeff': temp_coeff,
    'noct_c': noct_val,
    'soiling_loss': soiling_pct / 100.0,
    'dc_cable_loss': dc_cable_pct / 100.0,
    'mismatch_loss': mismatch_pct / 100.0,
    'inverter_eff': inv_eff_pct / 100.0,
    'ac_trafo_loss': trafo_loss_pct / 100.0,
    'aux_loss': aux_loss_pct / 100.0
}


# =========================================================================
# BANNER TIÊU ĐỀ ĐẦU TRANG WEB - NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP
# =========================================================================
logo_img_tag = f'<img src="data:image/png;base64,{logo_b64}" style="width: 105px; height: 105px; object-fit: contain; background: #FFFFFF; border-radius: 12px; padding: 6px; box-shadow: 0 4px 14px rgba(0,0,0,0.3); border: 2px solid rgba(255, 214, 10, 0.4);" />' if logo_b64 else ''

banner_html = f"""
<div class="hero-solar-banner">
    <div style="display: flex; align-items: center; gap: 22px; flex-wrap: wrap;">
        {logo_img_tag}
        <div style="flex: 1; min-width: 280px;">
            <div class="plant-main-title">NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP</div>
            <div class="plant-sub-title">HỆ THỐNG DỰ BÁO SẢN LƯỢNG ĐIỆN QUANG ĐIỆN CHU KỲ 15 PHÚT (EVN / A0 / A3)</div>
            <div style="margin-top: 6px;">
                <span class="solar-badge badge-dc">☀️ DC: 50.00 MWp</span>
                <span class="solar-badge badge-ac">⚡ AC Inverter: 40.075 MW</span>
                <span class="solar-badge badge-module">🔷 Tấm Pin: Sharp NU-440 (-0.347%/°C)</span>
                <span class="solar-badge badge-grid">🔌 Trạm Nâng Áp: 110kV / 22kV</span>
                <span class="solar-badge badge-dc">📍 Vị trí: Thôn Vạn Phước, Xã Phù Mỹ Nam, T. Gia Lai (SĐT: 0256 3856 667)</span>
            </div>
        </div>
    </div>
</div>
"""
st.markdown(banner_html, unsafe_allow_html=True)


# =========================================================================
# KHỞI TẠO VÀ QUÉT MÁY CHỦ SCADA (D:\DATA SERVER PV 01)
# =========================================================================
@st.cache_resource
def get_harvester():
    return DataHarvester(DEFAULT_SERVER_PATH)

harvester = get_harvester()
server_connected = harvester.check_server_connection()

if server_connected:
    available_dates = harvester.scan_available_dates()
    latest_entry = harvester.get_latest_date_entry()
    latest_date_str = latest_entry['date_str'] if latest_entry else "26/08/2026"
    
    st.markdown(f"""
    <div class="server-status-card">
        <b>🟢 Máy Chủ Dữ Liệu SCADA Trực Tuyến:</b> <code>{DEFAULT_SERVER_PATH}</code><br>
        • <b>Cơ sở dữ liệu lịch sử:</b> <code>{len(available_dates):,} ngày đo đếm</code> (2020 - 2026).<br>
        • <b>Dữ liệu SCADA mới nhất:</b> Ngày <code>{latest_date_str}</code> (gồm đầy đủ <code>W.txt</code> trạm thời tiết và <code>P.txt</code> đo đếm 110kV).
    </div>
    """, unsafe_allow_html=True)
else:
    available_dates = []
    latest_entry = None


# Quản lý Session State ngày đang chọn
if 'active_date_entry' not in st.session_state and latest_entry:
    st.session_state.active_date_entry = latest_entry

with st.expander("📂 Chọn Ngày Dữ Liệu Lịch Sử Từ Server SCADA / Tải File Ngoài", expanded=False):
    col_sc1, col_sc2 = st.columns([3, 1])
    with col_sc1:
        if available_dates:
            date_options = {d['date_str']: d for d in reversed(available_dates)}
            selected_date_str = st.selectbox(
                "Chọn ngày dữ liệu SCADA từ máy chủ:",
                list(date_options.keys()),
                index=0
            )
            if st.button("🔄 Nạp Dữ Liệu Ngày Này", type="primary"):
                st.session_state.active_date_entry = date_options[selected_date_str]
                st.success(f"✅ Đã nạp dữ liệu ngày **{selected_date_str}**!")
    with col_sc2:
        st.write("")
        st.write("")
        if st.button("⚡ Quét Lại Server"):
            harvester.scan_available_dates(force_rescan=True)
            st.rerun()

st.markdown("---")

# Tải dữ liệu ngày đang chọn từ Server
current_day_data = None
if st.session_state.get('active_date_entry'):
    current_day_data = harvester.load_day_data(st.session_state.active_date_entry, params=calc_params)

if current_day_data is None or current_day_data.get('forecast_15min') is None:
    w_sample = generate_scada_txt_sample_content()
    df_w_raw, w_meta = parse_scada_weather_txt_advanced(w_sample)
    df_1m, df_15min_f, kpi_f = process_1min_to_15min_forecast(df_w_raw, params=calc_params)
    current_day_data = {
        'forecast_15min': df_15min_f,
        'forecast_kpis': kpi_f,
        'actual_15min': None,
        'comparison_df': None,
        'comparison_kpis': None
    }


# =========================================================================
# 4 TAB ĐIỀU HÀNH & DỰ BÁO ĐA CHU KỲ
# =========================================================================
tab_1day, tab_18c, tab_comp, tab_multi = st.tabs([
    "📊 1. Dự Báo 96 Chu Kỳ Ngày (File Đang Chọn)",
    "⚡ 2. Dự Báo 18 Chu Kỳ Cuốn Chiếu (4.5h)",
    "⚖️ 3. So Sánh & Đánh Giá Sai Số (Thực Tế vs Dự Báo)",
    "🔮 4. Dự Báo Đa Chu Kỳ & Thuyết Minh Thời Tiết (Phù Mỹ Nam)"
])


# -------------------------------------------------------------------------
# TAB 1: DỰ BÁO 96 CHU KỲ NGÀY & CẬP NHẬT DỮ LIỆU P / W TÙY BIẾN
# -------------------------------------------------------------------------
with tab_1day:
    # 1. Xác định dữ liệu 96 chu kỳ đang kích hoạt (Gốc hoặc Tùy chỉnh P & W)
    is_custom_pw = st.session_state.get('custom_pw_15min') is not None
    if is_custom_pw:
        df_f15 = st.session_state.custom_pw_15min
        kpi_f = st.session_state.custom_pw_kpis
    else:
        df_f15 = current_day_data['forecast_15min']
        kpi_f = current_day_data['forecast_kpis']

    # Header & Thông báo trạng thái kịch bản
    h_col1, h_col2 = st.columns([3.5, 1.5])
    with h_col1:
        st.subheader(f"📊 Báo Cáo Dự Báo Sản Lượng 96 Chu Kỳ ({kpi_f['start_time'].strftime('%d/%m/%Y')})")
        if is_custom_pw:
            st.info(f"✨ **Đang hiển thị kịch bản P & W tùy chỉnh**: Sản lượng ước đạt **{kpi_f['total_energy_mwh']:.2f} MWh** | P_Grid Đỉnh: **{kpi_f['peak_grid_mw']:.2f} MW** | Bức xạ đỉnh: **{kpi_f['max_irradiance_wm2']:.0f} W/m²**")
    with h_col2:
        if is_custom_pw:
            st.write("")
            if st.button("🔄 Khôi Phục Dữ Liệu Gốc SCADA", type="secondary", use_container_width=True):
                st.session_state.custom_pw_15min = None
                st.session_state.custom_pw_kpis = None
                st.rerun()

    # =====================================================================
    # KHU VỰC CẬP NHẬT DỮ LIỆU P VÀ W TỪ NGOÀI VÀO (FILE / BẢNG SỬA / HỆ SỐ)
    # =====================================================================
    with st.expander("📥 **CẬP NHẬT / NẠP DỮ LIỆU P VÀ W TỪ NGOÀI VÀO (TẢI FILE EXCEL / SỬA TRỰC TIẾP / ĐIỀU CHỈNH NHANH)**", expanded=False):
        st.caption("Cho phép nạp dữ liệu Bức xạ W (W/m2) và Công suất P (MW) từ bên ngoài để mô phỏng sa thải công suất, điều độ khẩn cấp hoặc đánh giá các kịch bản thời tiết khác nhau.")
        
        pw_subtab_file, pw_subtab_edit, pw_subtab_scale = st.tabs([
            "📁 1. Nạp File Excel / CSV (P & W)",
            "✏️ 2. Chỉnh Sửa Trực Tiếp Trên Bảng",
            "🎛️ 3. Điều Chỉnh Tỉ Lệ Nhanh (What-If)"
        ])
        
        # --- SUBTAB 1: TẢI FILE SCADA TEST / EXCEL / CSV ---
        with pw_subtab_file:
            st.markdown("##### 📁 Nạp dữ liệu từ File Test SCADA (.txt, .dat) hoặc Bảng tính (.xlsx, .csv):")
            col_f_in, col_f_mode = st.columns([2, 1.5])
            with col_f_in:
                uploaded_pw_file = st.file_uploader(
                    "Chọn file SCADA mẫu (.txt, .dat, .csv) hoặc Excel (.xlsx):",
                    type=['txt', 'csv', 'xlsx', 'xls', 'dat', 'log'],
                    key="uploader_pw_tab1",
                    help="Hệ thống tự động nhận diện file SCADA thời tiết (GHI/Bức xạ), SCADA công suất điện lực (110kV/Inverter) hoặc bảng 96 chu kỳ."
                )
            with col_f_mode:
                calc_mode = st.radio(
                    "Chế độ tính toán / áp dụng:",
                    [
                        "1. Tự động nhận diện định dạng file (SCADA Thời Tiết / SCADA Công Suất / Bảng 96 CK)",
                        "2. Bắt buộc TÍNH LẠI P từ cột Bức xạ W theo mô hình pin Sharp NU-440 (k=0.8252)",
                        "3. Bắt buộc DÙNG TRỰC TIẾP giá trị P và W có sẵn trong file"
                    ],
                    key="mode_pw_file_tab1"
                )
            
            c_act1, c_act2, c_act3, c_act4 = st.columns([2, 2, 2, 2])
            with c_act1:
                if uploaded_pw_file is not None:
                    if st.button("🚀 Nạp & Cập Nhật Dữ Liệu", type="primary", use_container_width=True):
                        try:
                            file_bytes = uploaded_pw_file.getvalue()
                            recalc_p = "TÍNH LẠI P" in calc_mode
                            base_ref = current_day_data['forecast_15min']
                            
                            df_new, kpi_new, msg_info = process_any_external_scada_or_pw_file(
                                file_bytes,
                                uploaded_pw_file.name,
                                base_ref,
                                params=calc_params,
                                recalculate_p_from_w=recalc_p
                            )
                            
                            st.session_state.custom_pw_15min = df_new
                            st.session_state.custom_pw_kpis = kpi_new
                            st.success(f"✅ {msg_info} từ file **{uploaded_pw_file.name}**! (Tổng sản lượng: **{kpi_new['total_energy_mwh']:.2f} MWh** | P_Grid Đỉnh: **{kpi_new['peak_grid_mw']:.2f} MW**)")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"❌ Lỗi khi đọc file SCADA/Test: {ex}")
            with c_act2:
                # Nút tải file SCADA Thời Tiết mẫu (W.txt)
                scada_w_content = generate_scada_txt_sample_content()
                st.download_button(
                    "⛅ Tải File SCADA Thời Tiết Mẫu (W.txt)",
                    data=scada_w_content.encode('utf-8'),
                    file_name="W_SCADA_Thoi_Tiet_Mau_MyHiep.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with c_act3:
                # Nút tải file SCADA Công Suất mẫu (P.txt)
                scada_p_content = generate_scada_power_sample_content()
                st.download_button(
                    "⚡ Tải File SCADA Công Suất Mẫu (P.txt)",
                    data=scada_p_content.encode('utf-8'),
                    file_name="P_SCADA_Cong_Suat_Mau_MyHiep.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            with c_act4:
                # Nút tải file Excel mẫu
                template_excel = generate_pw_template_excel_bytes(current_day_data['forecast_15min'])
                st.download_button(
                    "📊 Tải File Excel Mẫu 96 Chu Kỳ (.xlsx)",
                    data=template_excel,
                    file_name="Mau_Nhap_Du_Lieu_P_W_96CK_MyHiep.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                
        # --- SUBTAB 2: CHỈNH SỬA TRỰC TIẾP TRÊN BẢNG ---
        with pw_subtab_edit:
            st.markdown("##### ✏️ Chỉnh sửa nhanh các giá trị Bức xạ W và Công suất P từng chu kỳ:")
            
            edit_base = df_f15.copy()
            table_editor_df = pd.DataFrame({
                'Chu_Ky': edit_base['Interval_Index'],
                'Khung_Gio': edit_base['Start_Time'] + ' - ' + edit_base['End_Time'],
                'Buc_Xa_W_Wm2': edit_base['Irradiance_Avg_Wm2'].round(1),
                'Cong_Suat_P_MW': edit_base['P_Grid_Avg_MW'].round(3),
                'Nhiet_Do_Cell_C': edit_base['Cell_Temp_Avg_C'].round(1) if 'Cell_Temp_Avg_C' in edit_base else 35.0
            })
            
            edited_result = st.data_editor(
                table_editor_df,
                num_rows="fixed",
                use_container_width=True,
                height=320,
                key="data_editor_pw_tab1"
            )
            
            c_ed1, c_ed2, _ = st.columns([2, 2.5, 2])
            with c_ed1:
                if st.button("⚡ Áp Dụng Bảng Chỉnh Sửa", type="primary", use_container_width=True):
                    base_ref = current_day_data['forecast_15min']
                    df_new, kpi_new = process_custom_pw_dataframe(edited_result, base_ref, params=calc_params, recalculate_p_from_w=False)
                    st.session_state.custom_pw_15min = df_new
                    st.session_state.custom_pw_kpis = kpi_new
                    st.success(f"✅ Đã cập nhật bảng 96 chu kỳ! (Sản lượng: {kpi_new['total_energy_mwh']:.2f} MWh)")
                    st.rerun()
            with c_ed2:
                if st.button("🎯 Tính Lại Toàn Bộ P Từ Bức Xạ W Trên Bảng", use_container_width=True):
                    base_ref = current_day_data['forecast_15min']
                    df_new, kpi_new = process_custom_pw_dataframe(edited_result, base_ref, params=calc_params, recalculate_p_from_w=True)
                    st.session_state.custom_pw_15min = df_new
                    st.session_state.custom_pw_kpis = kpi_new
                    st.success(f"✅ Đã tính toán lại P từ cột W! (Sản lượng: {kpi_new['total_energy_mwh']:.2f} MWh)")
                    st.rerun()

        # --- SUBTAB 3: ĐIỀU CHỈNH TỈ LỆ NHANH ---
        with pw_subtab_scale:
            st.markdown("##### 🎛️ Điều chỉnh nhanh biểu đồ 96 chu kỳ theo hệ số:")
            sc_col1, sc_col2, sc_col3 = st.columns(3)
            with sc_col1:
                scale_w_pct = st.slider("Hệ số Bức xạ W (%):", min_value=30, max_value=150, value=100, step=5, key="scale_w_slider")
            with sc_col2:
                curtail_p_mw = st.slider("Trần giới hạn công suất P (MW) (Lệnh A0/A3):", min_value=5.0, max_value=40.075, value=40.075, step=0.5, key="curtail_p_slider")
            with sc_col3:
                delta_t_c = st.slider("Độ lệch nhiệt độ tấm pin ΔT (°C):", min_value=-15, max_value=20, value=0, step=1, key="delta_t_slider")
                
            if st.button("⚡ Áp Dụng Hệ Số Điều Chỉnh Nhanh", type="primary"):
                base_ref = current_day_data['forecast_15min'].copy()
                base_ref['Irradiance_Avg_Wm2'] = (base_ref['Irradiance_Avg_Wm2'] * (scale_w_pct / 100.0)).clip(lower=0.0)
                if 'Cell_Temp_Avg_C' in base_ref:
                    base_ref['Cell_Temp_Avg_C'] = (base_ref['Cell_Temp_Avg_C'] + delta_t_c).clip(lower=0.0)
                
                custom_calc_params = calc_params.copy() if calc_params else {}
                custom_calc_params['ac_capacity_mw'] = curtail_p_mw
                
                df_new, kpi_new = process_custom_pw_dataframe(base_ref, base_ref, params=custom_calc_params, recalculate_p_from_w=True)
                st.session_state.custom_pw_15min = df_new
                st.session_state.custom_pw_kpis = kpi_new
                st.success(f"✅ Đã áp dụng hệ số! (Bức xạ: {scale_w_pct}%, P_Trần: {curtail_p_mw:.2f}MW -> Sản lượng: {kpi_new['total_energy_mwh']:.2f} MWh)")
                st.rerun()

    st.markdown("---")

    # 6 Thẻ KPI tổng hợp
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("⚡ Tổng Sản Lượng", f"{kpi_f['total_energy_mwh']:,.2f} MWh")
    with k2:
        st.metric("📈 P_Grid Đỉnh", f"{kpi_f['peak_grid_mw']:.2f} MW", delta=f"Trần Inverter: {ac_capacity:.2f} MW", delta_color="off")
    with k3:
        st.metric("🔥 P_DC Đỉnh", f"{kpi_f['peak_dc_mw']:.2f} MW")
    with k4:
        st.metric("✂️ Inverter Clipping", f"{kpi_f['total_clipping_loss_mwh']:.2f} MWh", delta=f"-{kpi_f['clipping_loss_ratio_pct']}%", delta_color="inverse")
    with k5:
        st.metric("🎯 Hệ Số PR", f"{kpi_f['performance_ratio_pct']:.1f}%")
    with k6:
        st.metric("☀️ Bức Xạ Đỉnh", f"{kpi_f['max_irradiance_wm2']:.0f} W/m²")

    # Đồ thị công suất P và Bức xạ W (2 Trục Y)
    st.markdown("### 📈 Biểu Đồ Công Suất P (MW) & Bức Xạ W (W/m²) 96 Chu Kỳ")
    fig_p = go.Figure()
    
    # Trục Y trái: Công suất P
    fig_p.add_trace(go.Scatter(
        x=df_f15['Timestamp'], 
        y=df_f15['P_DC_Avg_MW'], 
        mode='lines', 
        name='Công suất DC Tấm Pin (50MWp)', 
        line=dict(color='#F59E0B', width=2, dash='dot'),
        yaxis='y1'
    ))
    fig_p.add_trace(go.Scatter(
        x=df_f15['Timestamp'], 
        y=df_f15['P_Grid_Avg_MW'], 
        mode='lines+markers', 
        name='Công suất Phát Lưới P_Grid (MW)', 
        line=dict(color='#10B981', width=3), 
        fill='tozeroy', 
        fillcolor='rgba(16, 185, 129, 0.18)',
        yaxis='y1'
    ))
    fig_p.add_hline(
        y=ac_capacity, 
        line_dash="dash", 
        line_color="#EF4444", 
        line_width=2.5, 
        annotation_text=f"Trần Inverter {ac_capacity:.3f} MW"
    )
    
    # Trục Y phải: Bức xạ W (W/m2)
    fig_p.add_trace(go.Scatter(
        x=df_f15['Timestamp'],
        y=df_f15['Irradiance_Avg_Wm2'],
        mode='lines',
        name='Bức xạ Mặt Trời W (W/m²)',
        line=dict(color='#38BDF8', width=2, dash='dashdot'),
        yaxis='y2'
    ))
    
    fig_p.update_layout(
        xaxis_title="Thời gian (Chu kỳ 15 phút)",
        yaxis=dict(
            title=dict(text="<b>Công suất (MW)</b>", font=dict(color="#10B981")),
            tickfont=dict(color="#10B981"),
            side="left"
        ),
        yaxis2=dict(
            title=dict(text="<b>Bức xạ W (W/m²)</b>", font=dict(color="#0284C7")),
            tickfont=dict(color="#0284C7"),
            overlaying="y",
            side="right",
            range=[0, max(1100, float(df_f15['Irradiance_Avg_Wm2'].max() * 1.25))]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        template="plotly_white",
        height=480
    )
    st.plotly_chart(fig_p, width='stretch')

    exp_df = prepare_export_dataframe(df_f15)
    c_dl1, c_dl2, _ = st.columns([1.8, 1.5, 3.5])
    with c_dl1:
        st.download_button(
            "📥 Tải Báo Cáo Excel 96 Chu Kỳ (.xlsx)", 
            data=export_to_excel_bytes(df_f15, kpi_f), 
            file_name=f"Du_Bao_15Phut_MyHiep_{kpi_f['start_time'].strftime('%Y%m%d')}.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
            type="primary", 
            use_container_width=True
        )
    with c_dl2:
        st.download_button(
            "📄 Tải File CSV (.csv)", 
            data=export_to_csv_bytes(df_f15), 
            file_name=f"Du_Bao_15Phut_MyHiep_{kpi_f['start_time'].strftime('%Y%m%d')}.csv", 
            mime="text/csv", 
            use_container_width=True
        )
    st.dataframe(exp_df, width='stretch', height=350, hide_index=True)


# -------------------------------------------------------------------------
# TAB 2: DỰ BÁO 18 CHU KỲ CUỐN CHIẾU THEO THỜI GIAN THỰC (TÍCH HỢP AI & UPDATE W/P)
# -------------------------------------------------------------------------
with tab_18c:
    st.subheader("⚡ Dự Báo 18 Chu Kỳ Tiếp Theo Thời Gian Thực (Ultra-Short-Term Rolling Forecast)")
    st.caption("Dự báo cuốn chiếu 18 chu kỳ 15 phút (4.5 giờ tới) tích hợp AI tự động học sai số từ dữ liệu đo đếm W (Bức xạ) & P (Công suất) thực tế phục vụ đăng ký biểu đồ điều độ tức thời A0 / A3.")
    
    # 1. Cấu hình thời gian và chế độ AI
    col_fc1, col_fc2, col_fc3 = st.columns([1.6, 1.2, 2.0])
    with col_fc1:
        c_date_pick, c_time_pick = st.columns(2)
        with c_date_pick:
            fc_date_in = st.date_input("📅 Ngày dự báo:", value=datetime(2026, 8, 27), key="fc_date_tab2")
        with c_time_pick:
            fc_start_time = st.time_input("⏱️ Giờ bắt đầu:", value=datetime.strptime("14:15", "%H:%M").time(), key="fc_time_tab2")
            
    with col_fc2:
        fc_intervals = st.number_input("🔢 Số chu kỳ dự báo (15p):", min_value=4, max_value=36, value=18, step=1, key="fc_int_tab2", help="Mặc định 18 chu kỳ tương đương 4.5 giờ tới.")
        
    with col_fc3:
        c_ai_tog, c_ai_w = st.columns([1.3, 1.2])
        with c_ai_tog:
            fc_enable_ai = st.toggle("🧠 Bật AI Học Sai Số", value=True, key="fc_enable_ai_tab2", help="AI tự động phân tích độ lệch giữa thực tế và dự báo ở các chu kỳ trước để nắn chỉnh 18 chu kỳ tới.")
        with c_ai_w:
            fc_ai_weight = st.slider("Trọng số AI bám thực tế:", min_value=0.0, max_value=1.0, value=0.85, step=0.05, key="fc_ai_w_tab2", disabled=not fc_enable_ai)

    start_dt_fc = datetime.combine(fc_date_in, fc_start_time)
    
    # 2. KHU VỰC CẬP NHẬT DỮ LIỆU THỜI TIẾT W VÀ CÔNG SUẤT P CÁC CHU KỲ ĐÃ QUA
    with st.expander("📝 **CẬP NHẬT DỮ LIỆU THỜI TIẾT (W) & SẢN LƯỢNG (P) CÁC CHU KỲ TRƯỚC ĐỂ AI TỰ ĐỘNG HIỆU CHỈNH**", expanded=True):
        st.caption("Nhập hoặc cập nhật nhanh số liệu đo đếm Bức xạ $W (W/m^2)$ và Công suất phát lưới $P (MW)$ thực tế của các chu kỳ đã qua trong ngày. AI sẽ sử dụng độ lệch này làm căn cứ nắn chỉnh chính xác 18 chu kỳ tiếp theo.")
        
        # Khởi tạo dữ liệu mẫu các chu kỳ trước mốc bắt đầu
        cur_interval_idx = (fc_start_time.hour * 60 + fc_start_time.minute) // 15 + 1
        
        # Tạo danh sách các chu kỳ trước
        past_rows = []
        # Lấy từ current_day_data nếu có
        actual_df_ref = current_day_data.get('actual_15min')
        forecast_df_ref = current_day_data.get('forecast_15min')
        
        for p_idx in range(max(1, cur_interval_idx - 8), cur_interval_idx):
            p_start_m = (p_idx - 1) * 15
            p_end_m = p_idx * 15
            t_s = f"{p_start_m // 60:02d}:{p_start_m % 60:02d}"
            t_e = f"{p_end_m // 60:02d}:{p_end_m % 60:02d}"
            
            # Giá trị mặc định
            w_val = 0.0
            p_val = 0.0
            
            # Lấy từ dữ liệu SCADA thực tế nếu có
            if actual_df_ref is not None and len(actual_df_ref) >= p_idx:
                r_act = actual_df_ref.iloc[p_idx - 1]
                p_val = float(r_act.get('P_Grid_Actual_Avg_MW', r_act.get('P_Grid_Avg_MW', 0.0)))
            
            if forecast_df_ref is not None and len(forecast_df_ref) >= p_idx:
                r_fc = forecast_df_ref.iloc[p_idx - 1]
                w_val = float(r_fc.get('Irradiance_Avg_Wm2', 0.0))
                if p_val <= 0:
                    p_val = float(r_fc.get('P_Grid_Avg_MW', 0.0))
                    
            if w_val == 0 and p_val == 0:
                # Ước lượng mẫu thực tế giờ chiều
                mid_h = (p_start_m + 7.5) / 60.0
                if 6.0 <= mid_h <= 18.0:
                    w_val = round(max(0.0, 950.0 * np.sin(np.pi * (mid_h - 6.0) / 12.0)), 1)
                    p_val = round(min(40.075, (w_val / 1000.0) * 39.2), 2)
                    
            past_rows.append({
                'Interval_Index': p_idx,
                'Khung_Gio': f"{t_s} - {t_e}",
                'Buc_Xa_Thuc_Te_Wm2': w_val,
                'Cong_Suat_Thuc_Te_MW': p_val
            })
            
        df_past_init = pd.DataFrame(past_rows)
        
        c_ed_tab, c_ed_act = st.columns([3, 1])
        with c_ed_tab:
            edited_past_df = st.data_editor(
                df_past_init,
                num_rows="dynamic",
                key="editor_past_scada_tab2",
                use_container_width=True,
                column_config={
                    "Interval_Index": st.column_config.NumberColumn("Chu Kỳ", disabled=True),
                    "Khung_Gio": st.column_config.TextColumn("Khung Giờ (15p)", disabled=True),
                    "Buc_Xa_Thuc_Te_Wm2": st.column_config.NumberColumn("Bức Xạ Thực Tế W (W/m²)", min_value=0.0, max_value=1400.0, step=10.0, format="%.1f"),
                    "Cong_Suat_Thuc_Te_MW": st.column_config.NumberColumn("Công Suất Phát Lưới P (MW)", min_value=0.0, max_value=45.0, step=0.1, format="%.2f")
                }
            )
        with c_ed_act:
            st.markdown("##### ⚙️ Tùy chọn nạp:")
            if st.button("🔄 Nạp Dữ Liệu SCADA Hôm Nay", use_container_width=True):
                st.rerun()
            st.info("💡 **Gợi ý**: Bạn có thể click trực tiếp vào ô số liệu ở bảng bên trái để chỉnh sửa Bức xạ W và Công suất P thực tế vừa đo được. AI sẽ tự động học sai số và tính toán lại ngay!")

    # 3. THỰC HIỆN DỰ BÁO 18 CHU KỲ TÍCH HỢP AI
    # Chuẩn hóa bảng quá khứ đưa vào AI
    df_obs_feed = edited_past_df.copy()
    df_obs_feed.rename(columns={
        'Buc_Xa_Thuc_Te_Wm2': 'Irradiance_Actual_Wm2',
        'Cong_Suat_Thuc_Te_MW': 'P_Grid_Actual_MW'
    }, inplace=True)
    
    with st.spinner("Đang chạy mô hình AI phân tích chu kỳ quá khứ và dự báo 18 chu kỳ tới..."):
        df_18_ai, kpis_18_ai, df_18_timeline = forecast_18_rolling_realtime_ai(
            start_dt=start_dt_fc,
            historical_observed_df=df_obs_feed,
            nwp_data=None,
            params=calc_params,
            n_intervals=int(fc_intervals),
            enable_ai=fc_enable_ai,
            ai_bias_weight=fc_ai_weight
        )

    # 4. 4 THẺ KPI 18 CHU KỲ
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "⚡ Tổng Sản Lượng 18 Chu Kỳ",
            f"{kpis_18_ai['total_energy_mwh']:.2f} MWh",
            delta=f"TB: {kpis_18_ai['total_energy_mwh']/int(fc_intervals):.2f} MWh/CK"
        )
    with k2:
        st.metric(
            "📈 P_Grid Đỉnh Dự Báo",
            f"{kpis_18_ai['peak_grid_mw']:.2f} MW",
            delta=f"Bức xạ đỉnh: {df_18_ai['Irradiance_Avg_Wm2'].max():.0f} W/m²"
        )
    with k3:
        bias_val = kpis_18_ai['recent_bias_mw']
        bias_label = f"{bias_val:+.2f} MW" if bias_val != 0 else "0.00 MW"
        st.metric(
            "🧠 Độ Lệch AI Hiệu Chỉnh",
            bias_label,
            delta="AI đang bù trừ theo SCADA" if bias_val != 0 else "Chuẩn mô hình lý thuyết",
            delta_color="normal" if bias_val >= 0 else "inverse"
        )
    with k4:
        st.metric(
            "⏱️ Khung Thời Gian",
            f"{kpis_18_ai['start_time'].strftime('%H:%M')} - {kpis_18_ai['end_time'].strftime('%H:%M')}",
            delta=f"{fc_intervals} Chu kỳ (4.5 Giờ)"
        )

    # 5. BIỂU ĐỒ 18 CHU KỲ NỐI LIỀN THỜI GIAN THỰC (PLOTLY DUAL-AXIS)
    from plotly.subplots import make_subplots
    fig_18 = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Trace 1: Dải tin cậy P10 - P90 cho 18 chu kỳ tới
    x_fc_times = df_18_ai['Time_Range'].tolist()
    y_p90 = df_18_ai['P90_Upper_MW'].tolist()
    y_p10 = df_18_ai['P10_Lower_MW'].tolist()
    
    fig_18.add_trace(go.Scatter(
        x=x_fc_times + x_fc_times[::-1],
        y=y_p90 + y_p10[::-1],
        fill='toself',
        fillcolor='rgba(16, 185, 129, 0.12)',
        line=dict(color='rgba(255,255,255,0)'),
        hoverinfo="skip",
        showlegend=True,
        name='Dải Tin Cậy AI (P10 - P90)'
    ), secondary_y=False)

    # Trace 2: Công suất P_Grid Dự Báo AI (Area Chart)
    fig_18.add_trace(go.Scatter(
        x=x_fc_times,
        y=df_18_ai['P_Grid_Avg_MW'],
        mode='lines+markers',
        name='P_Grid Dự Báo AI (MW)',
        line=dict(color='#10B981', width=3),
        marker=dict(size=6, color='#10B981'),
        fill='tozeroy',
        fillcolor='rgba(16, 185, 129, 0.18)'
    ), secondary_y=False)

    # Trace 3: Công suất DC Dàn Pin
    fig_18.add_trace(go.Scatter(
        x=x_fc_times,
        y=df_18_ai['P_DC_Avg_MW'],
        mode='lines',
        name='P_DC Tấm Pin (MW)',
        line=dict(color='#F59E0B', width=2, dash='dot')
    ), secondary_y=False)

    # Trace 4: Baseline nếu không có AI (để so sánh)
    if fc_enable_ai and abs(bias_val) > 0.05:
        fig_18.add_trace(go.Scatter(
            x=x_fc_times,
            y=df_18_ai['P_Grid_Baseline_MW'],
            mode='lines',
            name='P_Grid Gốc (Chưa AI)',
            line=dict(color='#94A3B8', width=1.8, dash='dash')
        ), secondary_y=False)

    # Trace 5: Bức xạ Mặt Trời Dự Báo AI (Trục Y phụ bên phải)
    fig_18.add_trace(go.Scatter(
        x=x_fc_times,
        y=df_18_ai['Irradiance_Avg_Wm2'],
        mode='lines+markers',
        name='Bức Xạ Hiệu Chỉnh AI (W/m²)',
        line=dict(color='#0EA5E9', width=2, dash='dashdot'),
        marker=dict(size=5, color='#0EA5E9')
    ), secondary_y=True)

    # Đường giới hạn Inverter
    fig_18.add_hline(y=ac_capacity, line_dash="dash", line_color="#EF4444", line_width=2, annotation_text=f"Trần Inverter {ac_capacity:.3f} MW", secondary_y=False)

    fig_18.update_layout(
        title=f"<b>Biểu Đồ Công Suất & Bức Xạ {fc_intervals} Chu Kỳ Cuốn Chiếu ({kpis_18_ai['start_time'].strftime('%H:%M')} - {kpis_18_ai['end_time'].strftime('%H:%M')}) - Tích Hợp AI</b>",
        xaxis_title="Khung Giờ 15 Phút (Chu Kỳ Dự Báo)",
        yaxis_title="Công Suất Phát Điện (MW)",
        hovermode="x unified",
        template="plotly_white",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
    )
    fig_18.update_yaxes(title_text="Công Suất (MW)", secondary_y=False, range=[0, 45])
    fig_18.update_yaxes(title_text="Bức Xạ (W/m²)", secondary_y=True, showgrid=False, range=[0, 1200])
    
    st.plotly_chart(fig_18, use_container_width=True)

    # 6. BẢNG DỮ LIỆU 18 CHU KỲ VÀ NÚT XUẤT BÁO CÁO
    st.markdown("##### 📋 Bảng Chi Tiết 18 Chu Kỳ Dự Báo & Độ Lệch Hiệu Chỉnh AI:")
    
    col_dl1, col_dl2, _ = st.columns([1.8, 1.8, 3.5])
    with col_dl1:
        st.download_button(
            "📥 Tải File Excel 18 Chu Kỳ (.xlsx)",
            data=export_to_excel_bytes(df_18_ai, kpis_18_ai),
            file_name=f"Du_Bao_18_Chu_Ky_MyHiep_{kpis_18_ai['start_time'].strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    with col_dl2:
        st.download_button(
            "📄 Tải File CSV (.csv)",
            data=export_to_csv_bytes(df_18_ai),
            file_name=f"Du_Bao_18_Chu_Ky_MyHiep_{kpis_18_ai['start_time'].strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    st.dataframe(
        prepare_export_dataframe(df_18_ai),
        use_container_width=True,
        height=320,
        hide_index=True
    )


# -------------------------------------------------------------------------
# TAB 3: SO SÁNH & ĐÁNH GIÁ SAI SỐ (THỰC TẾ VS DỰ BÁO)
# -------------------------------------------------------------------------
with tab_comp:
    comp_df = current_day_data.get('comparison_df')
    comp_kpi = current_day_data.get('comparison_kpis')
    
    if comp_df is not None and comp_kpi is not None:
        st.subheader("⚖️ Đánh Giá Độ Chính Xác & Sai Số Dự Báo (Quy Chuẩn EVN / A0 / A3)")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("🎯 Độ Chính Xác Dự Báo", f"{comp_kpi['accuracy_pct']:.1f}%", delta=f"NMAE: {comp_kpi['nmae_pct']}%")
        with m2:
            st.metric("📉 Sai Số Tuyệt Đối (MAE)", f"{comp_kpi['mae_mw']:.3f} MW")
        with m3:
            st.metric("📊 Sai Số Toàn Phương (RMSE)", f"{comp_kpi['rmse_mw']:.3f} MW")
        with m4:
            st.metric("⚡ Chênh Lệch Điện Năng", f"{comp_kpi['total_energy_actual_mwh']:.2f} MWh", delta=f"{comp_kpi['total_diff_energy_mwh']:+.2f} MWh vs DB")
            
        fig_c = go.Figure()
        fig_c.add_trace(go.Scatter(x=comp_df['Timestamp'], y=comp_df['P_Grid_Avg_MW'], mode='lines', name='P_Grid Dự Báo (MW)', line=dict(color='#2563EB', width=2.5, dash='dash')))
        fig_c.add_trace(go.Scatter(x=comp_df['Timestamp'], y=comp_df['P_Grid_Actual_Avg_MW'], mode='lines+markers', name='P_Grid Thực Tế Đo Đếm 110kV (MW)', line=dict(color='#EA580C', width=3)))
        fig_c.add_trace(go.Bar(x=comp_df['Timestamp'], y=comp_df['Diff_Power_MW'], name='Độ Lệch (Thực tế - DB) (MW)', marker_color=np.where(comp_df['Diff_Power_MW'] >= 0, 'rgba(16, 185, 129, 0.5)', 'rgba(239, 68, 68, 0.5)')))
        fig_c.update_layout(title="<b>So Khớp Công Suất Dự Báo vs Thực Tế 110kV & Độ Lệch</b>", xaxis_title="Thời gian", yaxis_title="Công suất (MW)", hovermode="x unified", template="plotly_white", height=450)
        st.plotly_chart(fig_c, width='stretch')
        
        c_cdl1, c_cdl2, _ = st.columns([1.5, 1.5, 4])
        with c_cdl1:
            st.download_button("📥 Tải Báo Cáo Đối Soát (.xlsx)", data=export_comparison_to_excel_bytes(comp_df, comp_kpi), file_name="Bao_Cao_Doi_Soat_MyHiep.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", width='stretch')
        with c_cdl2:
            st.download_button("📄 Tải File CSV (.csv)", data=export_comparison_to_csv_bytes(comp_df), file_name="Bao_Cao_Doi_Soat_MyHiep.csv", mime="text/csv", width='stretch')
        st.dataframe(prepare_comparison_export_dataframe(comp_df), width='stretch', height=350, hide_index=True)
    else:
        st.info("💡 Ngày hiện tại chưa có đồng thời file Bức xạ và Công suất 110kV. Bạn có thể chọn ngày 25.08 hoặc nạp file P.txt để xem đối soát.")


# -------------------------------------------------------------------------
# TAB 4: DỰ BÁO ĐA CHU KỲ & THUYẾT MINH THỜI TIẾT (PHÙ MỸ NAM)
# -------------------------------------------------------------------------
with tab_multi:
    st.subheader("🔮 Hệ Thống Dự Báo Đa Khung Thời Gian & Khí Tượng Số (Phù Mỹ Nam)")
    st.caption("Tích hợp dự báo thời tiết vệ tinh số, lập lịch điều độ thị trường điện ngày tới D+1/D+2 (2 ngày), lập lịch tuần A0/A3 (7 ngày), dự báo 30 ngày và sản lượng tháng.")
    
    subtab_unified, subtab_2d, subtab_7d, subtab_30d, subtab_eom, subtab_nextm = st.tabs([
        "🌟 1. Mô Hình Dự Báo Thống Nhất (Lai Ghép Khí Tượng & Lịch Sử SCADA)",
        "📅 2. Dự Báo 2 Ngày Tới (192 Chu Kỳ - D+1, D+2)",
        "🗓️ 3. Dự Báo 7 Ngày Tới (672 Chu Kỳ - Lịch Tuần)",
        "📊 4. Dự Báo 30 Ngày Tới (Month-Ahead)",
        "🏁 5. Dự Báo Cuối Tháng 8/2026 (MTD + Còn lại)",
        "📈 6. Dự Báo Toàn Bộ Tháng 9/2026"
    ])
    
    # 1. MÔ HÌNH DỰ BÁO LAI GHÉP THỐNG NHẤT (UNIFIED HYBRID ENSEMBLE)
    with subtab_unified:
        st.markdown("#### 🌟 Mô Hình Dự Báo Lai Ghép Thống Nhất (Unified Ensemble Solar Forecasting)")
        st.caption("Thuật toán kết hợp đa trọng số giữa **Mô hình Khí tượng Số trị (NWP)** và **Mô hình Đo đếm Lịch sử SCADA Mỹ Hiệp** nhằm tối ưu độ chính xác và giảm thiểu sai số đối soát EVN / A0 / A3.")
        
        # Bảng điều khiển tham số lai ghép
        col_ens1, col_ens2, col_ens3 = st.columns([1.8, 1.5, 1.2])
        with col_ens1:
            ensemble_strategy = st.selectbox(
                "🎯 Chiến Lược Lai Ghép Thống Nhất:",
                [
                    "🌟 Tự Động Tối Ưu (Auto Dynamic Weighting)",
                    "⚖️ Cân Bằng 50% Khí Tượng - 50% Lịch Sử",
                    "⛅ Ưu Tiên Khí Tượng NWP (75% Khí Tượng - 25% Lịch Sử)",
                    "📈 Ưu Tiên Lịch Sử SCADA (25% Khí Tượng - 75% Lịch Sử)",
                    "🎛️ Tùy Chỉnh Trọng Số Thủ Công (Custom Weight)"
                ],
                index=0,
                key="select_ens_strat"
            )
        with col_ens2:
            forecast_horizon = st.selectbox(
                "⏱️ Khung Thời Gian Dự Báo:",
                [
                    "1 Ngày (96 Chu kỳ 15 phút)",
                    "2 Ngày Tới (192 Chu kỳ - D+1, D+2)",
                    "7 Ngày Tới (672 Chu kỳ - Kế hoạch Tuần)"
                ],
                index=0,
                key="select_ens_horizon"
            )
        with col_ens3:
            start_ens_date = st.date_input(
                "📅 Ngày Bắt Đầu:",
                value=datetime(2026, 8, 28),
                key="ens_start_date_pick"
            )

        # Mapping mode
        if "Tự Động" in ensemble_strategy:
            ens_mode_key = "AUTO"
            w_custom = 0.50
        elif "Cân Bằng" in ensemble_strategy:
            ens_mode_key = "EQUAL"
            w_custom = 0.50
        elif "Ưu Tiên Khí Tượng" in ensemble_strategy:
            ens_mode_key = "NWP_PRIORITY"
            w_custom = 0.75
        elif "Ưu Tiên Lịch Sử" in ensemble_strategy:
            ens_mode_key = "HIST_PRIORITY"
            w_custom = 0.25
        else:
            ens_mode_key = "CUSTOM"
            w_slider = st.slider(
                "🎚️ Trọng số Khí Tượng NWP (%) vs Lịch Sử SCADA (%):",
                min_value=0, max_value=100, value=50, step=5,
                help="100% = Hoàn toàn theo Khí tượng, 0% = Hoàn toàn theo Lịch sử SCADA."
            )
            w_custom = w_slider / 100.0

        enable_ai_flag = st.toggle("🧠 Tích Hợp AI (Machine Learning Error Correction)", value=True, help="Bật để AI tự động điều chỉnh bù suy hao do mây, quá nhiệt Inverter và hiệu ứng góc chiếu buổi sáng/chiều.")

        n_days_ens = 1 if "1 Ngày" in forecast_horizon else (2 if "2 Ngày" in forecast_horizon else 7)

        with st.spinner("Đang tổng hợp mô hình khí tượng vệ tinh và dữ liệu lịch sử SCADA Mỹ Hiệp..."):
            nwp_data = fetch_phu_my_weather_forecast(days=max(n_days_ens, 2))
            df_uni_15, df_uni_daily, uni_narratives = generate_unified_hybrid_forecast(
                start_date=start_ens_date,
                num_days=n_days_ens,
                nwp_data=nwp_data,
                params=calc_params,
                ensemble_mode=ens_mode_key,
                custom_nwp_weight=w_custom,
                enable_ai=enable_ai_flag
            )

        if len(df_uni_15) > 0 and len(df_uni_daily) > 0:
            # Lựa chọn ngày xem chi tiết nếu dự báo nhiều ngày
            if n_days_ens > 1:
                day_options = {r['Day_Name'] + ' (' + r['Date_Str'] + ')': r['Date_Str'] for _, r in df_uni_daily.iterrows()}
                selected_day_label = st.selectbox("📅 Chọn ngày hiển thị biểu đồ & thuyết minh chi tiết:", list(day_options.keys()), index=0)
                selected_date_str = day_options[selected_day_label]
                df_plot_15 = df_uni_15[df_uni_15['Date'] == selected_date_str].copy()
                cur_day_summary = df_uni_daily[df_uni_daily['Date_Str'] == selected_date_str].iloc[0]
                cur_nar = next((n for n in uni_narratives if n['date_str'] == selected_date_str), uni_narratives[0])
            else:
                df_plot_15 = df_uni_15.copy()
                cur_day_summary = df_uni_daily.iloc[0]
                cur_nar = uni_narratives[0]

            # 4 Thẻ KPI Dự Báo Thống Nhất
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric(
                    "⚡ Sản Lượng Thống Nhất",
                    f"{cur_day_summary['Energy_Unified_MWh']:.2f} MWh",
                    delta=f"NWP: {cur_day_summary['Energy_NWP_MWh']:.1f} | SCADA: {cur_day_summary['Energy_Hist_MWh']:.1f} MWh"
                )
            with k2:
                st.metric(
                    "📈 P_Grid Đỉnh Thống Nhất",
                    f"{cur_day_summary['Peak_Grid_MW']:.2f} MW",
                    delta=f"Bức xạ đỉnh: {cur_day_summary['Max_Irradiance_Wm2']:.0f} W/m²"
                )
            with k3:
                st.metric(
                    "⚖️ Tỷ Lệ Lai Ghép",
                    f"{cur_day_summary['Weight_NWP_Pct']:.0f}% NWP / {cur_day_summary['Weight_Hist_Pct']:.0f}% SCADA",
                    delta="Đã hiệu chuẩn trần 40.075 MW"
                )
            with k4:
                st.metric(
                    "🎯 Dải Tin Cậy P10 - P90",
                    f"{df_plot_15['P10_Lower_MW'].max():.1f} - {df_plot_15['P90_Upper_MW'].max():.1f} MW",
                    delta=f"Độ phủ mây TB: {cur_day_summary['Avg_Cloud_Pct']:.0f}%"
                )

            from plotly.subplots import make_subplots
            fig_uni = make_subplots(specs=[[{"secondary_y": True}]])
            x_vals = pd.to_datetime(df_plot_15['Timestamp'])

            # Công suất DC Tấm Pin (50MWp)
            fig_uni.add_trace(go.Scatter(
                x=x_vals,
                y=df_plot_15['P_DC_Avg_MW'],
                mode='lines',
                name='Công suất DC Tấm Pin (50MWp)',
                line=dict(color='#F59E0B', width=2, dash='dot')
            ), secondary_y=False)

            # Công suất Phát Lưới P_Grid (MW)
            fig_uni.add_trace(go.Scatter(
                x=x_vals,
                y=df_plot_15['P_Grid_Unified_MW'],
                mode='lines+markers',
                name='Công suất Phát Lưới P_Grid (MW)',
                line=dict(color='#10B981', width=3),
                fill='tozeroy',
                fillcolor='rgba(16, 185, 129, 0.18)',
                marker=dict(size=4)
            ), secondary_y=False)

            # Bức xạ Mặt Trời W (W/m²)
            fig_uni.add_trace(go.Scatter(
                x=x_vals,
                y=df_plot_15['Irradiance_Unified_Wm2'],
                mode='lines',
                name='Bức xạ Mặt Trời W (W/m²)',
                line=dict(color='#0EA5E9', width=2, dash='dashdot')
            ), secondary_y=True)

            # Đường trần Inverter 40.075 MW
            fig_uni.add_hline(
                y=ac_capacity,
                line_dash="dash",
                line_color="#EF4444",
                line_width=2,
                annotation_text=f"Trần Inverter {ac_capacity:.3f} MW",
                annotation_position="top right",
                secondary_y=False
            )

            fig_uni.update_layout(
                title=dict(
                    text=f"📈 <b>Biểu Đồ Công Suất P (MW) & Bức Xạ W (W/m²) 96 Chu Kỳ (Ngày {cur_nar['date_str']})</b>",
                    font=dict(size=18, color="#1E293B")
                ),
                xaxis_title="Thời gian (Chu kỳ 15 phút)",
                hovermode="x unified",
                template="plotly_white",
                height=480,
                legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
            )
            
            fig_uni.update_yaxes(title_text="Công suất (MW)", secondary_y=False, range=[0, 50])
            fig_uni.update_yaxes(title_text="Bức xạ W (W/m²)", secondary_y=True, range=[0, 1200], showgrid=False)

            st.plotly_chart(fig_uni, width='stretch')

            # BẢN THUYẾT MINH KHÍ TƯỢNG & VẬN HÀNH THỐNG NHẤT
            import textwrap
            ens_narrative_html = textwrap.dedent(f"""
            <div class="narrative-box">
                <div class="narrative-top-bar">
                    <div class="narrative-top-title">📑 BẢN THUYẾT MINH DỰ BÁO THỐNG NHẤT (LAI GHÉP KHÍ TƯỢNG & LỊCH SỬ SCADA)</div>
                    <div class="narrative-top-meta">
                        <span>🏢 <b>Nhà máy:</b> NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP (50MWp / 40.075MW)</span>
                        <span style="margin: 0 10px; color: #CBD5E1;">|</span>
                        <span>📍 <b>Tọa độ:</b> Thôn Vạn Phước, Xã Phù Mỹ Nam, Tỉnh Gia Lai (SĐT: 0256 3856 667)</span>
                    </div>
                    <div class="narrative-badge-wrap">
                        <span class="nbadge nbadge-day">📅 {cur_nar['day_name']} ({cur_nar['date_str']})</span>
                        <span class="nbadge nbadge-weather">⛅ {cur_nar['weather_type']}</span>
                        <span class="nbadge nbadge-energy">⚡ Sản lượng Thống Nhất: <b>{cur_day_summary['Energy_Unified_MWh']:.2f} MWh</b></span>
                        <span class="nbadge nbadge-peak">📈 Đỉnh: <b>{cur_day_summary['Peak_Grid_MW']:.2f} MW</b></span>
                    </div>
                </div>
                
                <div class="narrative-cards-grid">
                    <div class="ncard ncard-weather">
                        <div class="ncard-head">⛅ 1. TÌNH HÌNH KHÍ TƯỢNG & HÌNH THẾ THỜI TIẾT TẠI PHÙ MỸ</div>
                        <div class="ncard-body">{cur_nar['weather_desc']}</div>
                    </div>
                    
                    <div class="ncard ncard-power">
                        <div class="ncard-head">⚡ 2. ĐÁNH GIÁ TỔNG HỢP MÔ HÌNH THỐNG NHẤT & SẢN LƯỢNG</div>
                        <div class="ncard-body">
                            {cur_nar['impact_desc']}<br>
                            <span style="color: #0284C7; font-weight: 600;">• {cur_nar.get('ensemble_info', '')}</span>
                        </div>
                    </div>
                    
                    <div class="ncard ncard-temp">
                        <div class="ncard-head">🌡️ 3. PHÂN TÍCH NHIỆT ĐỘ CELL TẤM PIN SHARP NU-440 (-0.347%/°C)</div>
                        <div class="ncard-body">{cur_nar['thermal_analysis']}</div>
                    </div>
                    
                    <div class="ncard ncard-dispatch">
                        <div class="ncard-head">📋 4. KHUYẾN NGHỊ ĐIỀU ĐỘ VẬN HÀNH & ĐĂNG KÝ EVN / A0 / A3</div>
                        <div class="ncard-body">
                            <div class="dispatch-item">• {cur_nar['recommendations'][0]}</div>
                            <div class="dispatch-item">• {cur_nar['recommendations'][1]}</div>
                            <div class="dispatch-item">• {cur_nar['recommendations'][2]}</div>
                        </div>
                    </div>
                </div>
            </div>
            """)
            st.html(ens_narrative_html)

            # TẢI BÁO CÁO & XEM BẢNG DỮ LIỆU
            c_dl_u1, c_dl_u2, _ = st.columns([2, 1.8, 3.2])
            with c_dl_u1:
                st.download_button(
                    "📥 Tải Báo Cáo Thống Nhất Excel (.xlsx)",
                    data=export_to_excel_bytes(df_plot_15, {
                        'plant_name': 'NHÀ MÁY ĐMT MỸ HIỆP',
                        'start_time': datetime.strptime(cur_nar['date_str'], '%d/%m/%Y'),
                        'dc_capacity_mwp': 50.0,
                        'ac_capacity_mw': 40.075,
                        'total_energy_mwh': cur_day_summary['Energy_Unified_MWh'],
                        'peak_grid_mw': cur_day_summary['Peak_Grid_MW'],
                        'total_clipping_loss_mwh': cur_day_summary['Clipping_Loss_MWh'],
                        'total_15min_intervals': len(df_plot_15),
                        'performance_ratio_pct': 82.5,
                        'max_irradiance_wm2': cur_day_summary['Max_Irradiance_Wm2']
                    }),
                    file_name=f"Du_Bao_Thong_Nhat_MyHiep_{cur_nar['date_str'].replace('/', '')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
            with c_dl_u2:
                st.download_button(
                    "📄 Tải File CSV 96 Chu Kỳ (.csv)",
                    data=export_to_csv_bytes(df_plot_15),
                    file_name=f"Du_Bao_Thong_Nhat_MyHiep_{cur_nar['date_str'].replace('/', '')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            # Bảng số liệu chi tiết
            exp_uni_table = df_plot_15[[
                'Interval_Index', 'Start_Time', 'End_Time',
                'P_Grid_Unified_MW', 'P_Grid_NWP_MW', 'P_Grid_Hist_MW',
                'Irradiance_Unified_Wm2', 'Amb_Temp_Avg_C', 'Cell_Temp_Avg_C',
                'Energy_Unified_MWh', 'P10_Lower_MW', 'P90_Upper_MW'
            ]].copy()
            exp_uni_table.columns = [
                'Chu kỳ', 'Bắt đầu', 'Kết thúc',
                'P_Thống Nhất (MW)', 'P_Khí Tượng (MW)', 'P_Lịch Sử (MW)',
                'Bức Xạ W (W/m²)', 'T_Môi Trường (°C)', 'T_Cell (°C)',
                'Sản Lượng (MWh)', 'P10 (MW)', 'P90 (MW)'
            ]
            st.dataframe(exp_uni_table, width='stretch', height=320, hide_index=True)
        else:
            st.warning("⚠️ Không có dữ liệu dự báo. Vui lòng kiểm tra kết nối mạng và thử lại.")

    # 2. DỰ BÁO 2 NGÀY (D+1, D+2)
    with subtab_2d:
        st.markdown("#### ⚡ Dự Báo Thị Trường Điện Ngày Tới (D+1, D+2 Theo Chu Kỳ 15 Phút)")
        
        col_2d1, col_2d2 = st.columns([2, 2])
        with col_2d1:
            view_mode_2d = st.radio(
                "Chọn chế độ xem:",
                ["⚡ Ngày D+2 (29/08/2026 - 96 Chu kỳ)", "☀️ Ngày D+1 (28/08/2026 - 96 Chu kỳ)", "📑 Cả 2 Ngày (D+1 & D+2 - 192 Chu kỳ)"],
                horizontal=True,
                key="radio_d2_mode"
            )
        with col_2d2:
            date_base = st.date_input("Ngày mốc D (Hôm nay):", value=datetime(2026, 8, 27), key="d_base_date")
            
        dt_d1 = date_base + timedelta(days=1)
        dt_d2 = date_base + timedelta(days=2)

        df_2d_15_all, df_2d_daily_all, kpi_2d_all = generate_multi_day_15min_forecast(start_date=dt_d1, num_days=2, params=calc_params)
        
        if "D+2" in view_mode_2d:
            df_display_15 = df_2d_15_all[df_2d_15_all['Date'] == dt_d2.strftime('%d/%m/%Y')].copy()
            df_display_15['Interval_Index'] = range(1, len(df_display_15) + 1)
            target_title = f"DỰ BÁO NGÀY D+2 ({dt_d2.strftime('%d/%m/%Y')}) - 96 CHU KỲ 15 PHÚT"
            k1_val = df_display_15['Energy_Grid_MWh'].sum()
            k2_val = df_display_15['P_Grid_Avg_MW'].max()
            k3_val = df_display_15['Clipping_Loss_MWh'].sum()
            k4_val = "96 Chu kỳ (00:00 - 24:00)"
            file_suffix = f"D2_{dt_d2.strftime('%Y%m%d')}"
        elif "D+1" in view_mode_2d:
            df_display_15 = df_2d_15_all[df_2d_15_all['Date'] == dt_d1.strftime('%d/%m/%Y')].copy()
            df_display_15['Interval_Index'] = range(1, len(df_display_15) + 1)
            target_title = f"DỰ BÁO NGÀY D+1 ({dt_d1.strftime('%d/%m/%Y')}) - 96 CHU KỲ 15 PHÚT"
            k1_val = df_display_15['Energy_Grid_MWh'].sum()
            k2_val = df_display_15['P_Grid_Avg_MW'].max()
            k3_val = df_display_15['Clipping_Loss_MWh'].sum()
            k4_val = "96 Chu kỳ (00:00 - 24:00)"
            file_suffix = f"D1_{dt_d1.strftime('%Y%m%d')}"
        else:
            df_display_15 = df_2d_15_all
            target_title = f"DỰ BÁO 2 NGÀY D+1 & D+2 ({dt_d1.strftime('%d/%m')} & {dt_d2.strftime('%d/%m/%Y')}) - 192 CHU KỲ"
            k1_val = kpi_2d_all['total_energy_mwh']
            k2_val = kpi_2d_all['peak_grid_mw']
            k3_val = kpi_2d_all['total_clipping_loss_mwh']
            k4_val = "192 Chu kỳ (2 Ngày)"
            file_suffix = f"D1_D2_{dt_d1.strftime('%Y%m%d')}"

        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("⚡ Tổng Sản Lượng", f"{k1_val:.2f} MWh")
        with k2:
            st.metric("📈 P_Grid Đỉnh Phát Lưới", f"{k2_val:.2f} MW")
        with k3:
            st.metric("✂️ Cắt Inverter", f"{k3_val:.2f} MWh")
        with k4:
            st.metric("⏱️ Tổng Số Chu Kỳ 15 Phút", k4_val)
            
        from plotly.subplots import make_subplots
        fig_2d = make_subplots(specs=[[{"secondary_y": True}]])
        x_vals_2d = pd.to_datetime(df_display_15['Timestamp'])
        
        # Công suất DC Tấm Pin (50MWp)
        fig_2d.add_trace(go.Scatter(
            x=x_vals_2d, 
            y=df_display_15['P_DC_Avg_MW'], 
            mode='lines', 
            name='Công suất DC Tấm Pin (50MWp)', 
            line=dict(color='#F59E0B', width=2, dash='dot')
        ), secondary_y=False)

        # Công suất Phát Lưới P_Grid (MW)
        fig_2d.add_trace(go.Scatter(
            x=x_vals_2d, 
            y=df_display_15['P_Grid_Avg_MW'], 
            mode='lines+markers', 
            name='Công suất Phát Lưới P_Grid (MW)', 
            line=dict(color='#10B981', width=3), 
            fill='tozeroy', 
            fillcolor='rgba(16, 185, 129, 0.18)',
            marker=dict(size=4)
        ), secondary_y=False)

        # Bức xạ Mặt Trời W (W/m²)
        fig_2d.add_trace(go.Scatter(
            x=x_vals_2d, 
            y=df_display_15['Irradiance_Avg_Wm2'], 
            mode='lines', 
            name='Bức xạ Mặt Trời W (W/m²)', 
            line=dict(color='#0EA5E9', width=2, dash='dashdot')
        ), secondary_y=True)

        fig_2d.add_hline(
            y=ac_capacity,
            line_dash="dash",
            line_color="#EF4444",
            line_width=2,
            annotation_text=f"Trần Inverter {ac_capacity:.3f} MW",
            annotation_position="top right",
            secondary_y=False
        )
        
        fig_2d.update_layout(
            title=dict(
                text=f"📈 <b>Biểu Đồ Công Suất P (MW) & Bức Xạ W (W/m²) {target_title}</b>",
                font=dict(size=18, color="#1E293B")
            ),
            xaxis_title="Thời gian (Chu kỳ 15 phút)", 
            hovermode="x unified", 
            template="plotly_white", 
            height=480,
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1)
        )
        
        fig_2d.update_yaxes(title_text="Công suất (MW)", secondary_y=False, range=[0, 50])
        fig_2d.update_yaxes(title_text="Bức xạ W (W/m²)", secondary_y=True, range=[0, 1200], showgrid=False)

        st.plotly_chart(fig_2d, width='stretch')
        
        exp_display_df = prepare_export_dataframe(df_display_15)
        c_d2_1, c_d2_2, _ = st.columns([2, 2, 3])
        with c_d2_1:
            st.download_button(
                f"📥 Tải Biểu Mẫu Điều Độ Excel (.xlsx)", 
                data=export_to_excel_bytes(df_display_15, {'plant_name': 'NHÀ MÁY ĐMT MỸ HIỆP', 'dc_capacity_mwp': 50.0, 'ac_capacity_mw': 40.075, 'total_energy_mwh': k1_val, 'peak_grid_mw': k2_val, 'total_clipping_loss_mwh': k3_val, 'total_15min_intervals': len(df_display_15)}), 
                file_name=f"Du_Bao_{file_suffix}.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                type="primary",
                width='stretch'
            )
        with c_d2_2:
            st.download_button(
                f"📄 Tải File CSV Chu Kỳ 15 Phút (.csv)", 
                data=export_to_csv_bytes(df_display_15), 
                file_name=f"Du_Bao_{file_suffix}.csv", 
                mime="text/csv",
                width='stretch'
            )
            
        st.dataframe(exp_display_df, width='stretch', height=380, hide_index=True)

    # 3. DỰ BÁO 7 NGÀY (672 CHU KỲ)
    with subtab_7d:
        st.markdown("#### 🗓️ Dự Báo Lập Kế Hoạch Vận Hành Tuần (7 Ngày: 672 Chu Kỳ 15 Phút)")
        date_7d_start = st.date_input("Ngày bắt đầu tuần dự báo:", value=datetime(2026, 8, 28), key="d7_start")
        df_7d_15, df_7d_daily, kpi_7d = generate_multi_day_15min_forecast(start_date=date_7d_start, num_days=7, params=calc_params)
        
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("⚡ Tổng Sản Lượng Tuần", f"{kpi_7d['total_energy_mwh']:,.2f} MWh", delta=f"{kpi_7d['total_energy_gwh']:.3f} GWh")
        with k2:
            st.metric("📊 Sản Lượng TB/Ngày", f"{kpi_7d['avg_daily_mwh']:.2f} MWh/ngày")
        with k3:
            st.metric("📈 P_Grid Đỉnh", f"{kpi_7d['peak_grid_mw']:.2f} MW")
        with k4:
            st.metric("⏱️ Tổng Số Chu Kỳ 15 Phút", f"{kpi_7d['total_15min_intervals']} chu kỳ")
            
        fig_7d = go.Figure()
        fig_7d.add_trace(go.Bar(x=df_7d_daily['Day_Name'], y=df_7d_daily['Energy_MWh'], text=df_7d_daily['Energy_MWh'].round(1), textposition='auto', marker_color='#0284C7', name='Sản lượng ngày (MWh)'))
        fig_7d.update_layout(title="<b>Dự Báo Sản Lượng Từng Ngày Trong Tuần (MWh)</b>", xaxis_title="Ngày trong tuần", yaxis_title="Sản lượng (MWh)", template="plotly_white", height=380)
        st.plotly_chart(fig_7d, width='stretch')
        
        st.download_button("📥 Tải Báo Cáo Tuần (.xlsx - 672 Chu Kỳ)", data=export_multi_day_to_excel_bytes(df_7d_15, df_7d_daily, kpi_7d, "7_NGAY"), file_name=f"Du_Bao_Tuan_{date_7d_start.strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        st.dataframe(df_7d_daily, width='stretch', hide_index=True)

    # 4. DỰ BÁO 30 NGÀY TỚI
    with subtab_30d:
        st.markdown("#### 📊 Dự Báo Sản Lượng 30 Ngày Tiếp Theo (Month-Ahead)")
        date_30d_start = st.date_input("Ngày bắt đầu 30 ngày:", value=datetime(2026, 8, 28), key="d30_start")
        df_30d_15, df_30d_daily, kpi_30d = generate_multi_day_15min_forecast(start_date=date_30d_start, num_days=30, params=calc_params)
        
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("⚡ Tổng Sản Lượng 30 Ngày", f"{kpi_30d['total_energy_mwh']:,.2f} MWh", delta=f"{kpi_30d['total_energy_gwh']:.3f} GWh")
        with k2:
            st.metric("📊 Sản Lượng TB/Ngày", f"{kpi_30d['avg_daily_mwh']:.2f} MWh/ngày")
        with k3:
            st.metric("📈 P_Grid Đỉnh", f"{kpi_30d['peak_grid_mw']:.2f} MW")
            
        fig_30d = go.Figure()
        fig_30d.add_trace(go.Bar(x=df_30d_daily['Date_Str'], y=df_30d_daily['Energy_MWh'], marker_color='#F59E0B', name='Sản lượng (MWh)'))
        fig_30d.update_layout(title="<b>Dự Báo Sản Lượng 30 Ngày Tiếp Theo (MWh)</b>", xaxis_title="Ngày", yaxis_title="Sản lượng (MWh)", template="plotly_white", height=400, xaxis=dict(tickangle=-45))
        st.plotly_chart(fig_30d, width='stretch')
        
        st.download_button("📥 Tải Báo Cáo 30 Ngày (.xlsx)", data=export_multi_day_to_excel_bytes(df_30d_15, df_30d_daily, kpi_30d, "30_NGAY"), file_name=f"Du_Bao_30Ngay_{date_30d_start.strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")

    # 5. DỰ BÁO CUỐI THÁNG 8/2026
    with subtab_eom:
        st.markdown("#### 🏁 Dự Báo Tổng Sản Lượng Cuối Tháng 8/2026")
        st.caption("Tổng hợp từ dữ liệu đo đếm thực tế SCADA (từ ngày 01 đến 26/08) cộng với Dự báo các ngày còn lại (27 đến 31/08).")
        
        eom_res = forecast_end_of_month(harvester, year=2026, month=8, params=calc_params)
        
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("🏆 Dự Báo Cả Tháng 8", f"{eom_res['total_projected_month_mwh']:,.2f} MWh", delta=f"{eom_res['total_projected_month_gwh']:.3f} GWh")
        with k2:
            st.metric("🟢 Thực Tế Đã Phát (01-26/08)", f"{eom_res['total_actual_mwh']:,.2f} MWh", delta=f"{eom_res['recorded_days']} ngày đã đo")
        with k3:
            st.metric("🔮 Dự Báo Còn Lại (27-31/08)", f"{eom_res['total_forecast_remaining_mwh']:,.2f} MWh", delta=f"{eom_res['remaining_days']} ngày còn lại")
        with k4:
            st.metric("📊 Sản Lượng TB Ngày", f"{eom_res['avg_daily_yield_mwh']:.2f} MWh/ngày")
            
        fig_eom = go.Figure()
        df_fm = eom_res['df_full_month']
        colors = np.where(df_fm['Loại'].str.contains('Thực tế'), '#10B981', '#F59E0B')
        fig_eom.add_trace(go.Bar(x=df_fm['Date_Str'], y=df_fm['Sản lượng (MWh)'], marker_color=colors, name='Sản lượng ngày (MWh)'))
        fig_eom.update_layout(title="<b>Sản Lượng Từng Ngày Tháng 8/2026 (Xanh: Thực tế SCADA đo đếm | Vàng: Dự báo)</b>", xaxis_title="Ngày", yaxis_title="Sản lượng (MWh)", template="plotly_white", height=400, xaxis=dict(tickangle=-45))
        st.plotly_chart(fig_eom, width='stretch')
        
        st.dataframe(df_fm, width='stretch', hide_index=True)

    # 6. DỰ BÁO THÁNG TIẾP THEO (THÁNG 9/2026)
    with subtab_nextm:
        st.markdown("#### 📈 Dự Báo Toàn Bộ Sản Lượng Tháng Tiếp Theo (Tháng 9/2026)")
        st.caption("Dự báo toàn bộ 30 ngày của Tháng 9/2026 dựa trên mô hình bức xạ mùa vụ Nam Trung Bộ (Bình Định) và cấu hình 50MWp / 40.075MW ĐMT Mỹ Hiệp.")
        
        next_m_res = forecast_next_month(current_year=2026, current_month=8, params=calc_params)
        
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("🏆 Tổng Sản Lượng Tháng 9", f"{next_m_res['total_energy_mwh']:,.2f} MWh", delta=f"{next_m_res['total_energy_gwh']:.3f} GWh")
        with k2:
            st.metric("📊 Sản Lượng TB Ngày", f"{next_m_res['avg_daily_mwh']:.2f} MWh/ngày")
        with k3:
            st.metric("📈 P_Grid Đỉnh Dự Kiến", f"{next_m_res['peak_grid_mw']:.2f} MW")
        with k4:
            st.metric("☀️ Bức Xạ TB Mùa Vụ", f"{next_m_res.get('avg_insolation_kwh_m2', 4.06):.2f} kWh/m²/ngày")
            
        fig_nextm = go.Figure()
        fig_nextm.add_trace(go.Bar(x=next_m_res['df_daily']['Date_Str'], y=next_m_res['df_daily']['Energy_MWh'], marker_color='#8B5CF6', name='Sản lượng dự báo (MWh)'))
        fig_nextm.update_layout(title="<b>Dự Báo Sản Lượng 30 Ngày Tháng 9/2026 (MWh)</b>", xaxis_title="Ngày", yaxis_title="Sản lượng (MWh)", template="plotly_white", height=400, xaxis=dict(tickangle=-45))
        st.plotly_chart(fig_nextm, width='stretch')
        
        st.dataframe(next_m_res['df_daily'], width='stretch', hide_index=True)
