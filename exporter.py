"""
Module xuất dữ liệu dự báo sản lượng chu kỳ 15 phút (Excel / CSV)
Chuẩn biểu mẫu báo cáo vận hành & điều độ hệ thống điện (EVN / A0 / A3)
Hỗ trợ: Báo Cáo Dự Báo Ngày (96 chu kỳ), Dự Báo 2 Ngày (192 chu kỳ), 7 Ngày (672 chu kỳ), 30 Ngày, Cuối Tháng, Tháng Tiếp Theo
"""

import io
import pandas as pd
from typing import Dict, Any


def prepare_export_dataframe(df_15min: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn hóa bảng dữ liệu 15 phút với tên cột tiếng Việt chuyên ngành điều độ
    """
    ts_series = pd.to_datetime(df_15min['Timestamp']) if 'Timestamp' in df_15min else pd.Series([None] * len(df_15min))
    date_col = ts_series.dt.strftime('%d/%m/%Y') if ts_series.notna().any() else df_15min.get('Date', '')
    
    irr_avg = df_15min['Irradiance_Avg_Wm2'].round(1) if 'Irradiance_Avg_Wm2' in df_15min else pd.Series([0.0] * len(df_15min))
    irr_max = df_15min['Irradiance_Max_Wm2'].round(1) if 'Irradiance_Max_Wm2' in df_15min else irr_avg
    
    amb_temp = df_15min['Amb_Temp_Avg_C'].round(1) if 'Amb_Temp_Avg_C' in df_15min else pd.Series([25.0] * len(df_15min))
    cell_temp = df_15min['Cell_Temp_Avg_C'].round(1) if 'Cell_Temp_Avg_C' in df_15min else amb_temp
    
    p_dc = df_15min['P_DC_Avg_MW'].round(3) if 'P_DC_Avg_MW' in df_15min else pd.Series([0.0] * len(df_15min))
    p_inv = df_15min['P_AC_Inv_Avg_MW'].round(3) if 'P_AC_Inv_Avg_MW' in df_15min else p_dc
    p_grid = df_15min['P_Grid_Avg_MW'].round(3) if 'P_Grid_Avg_MW' in df_15min else p_inv
    energy = df_15min['Energy_Grid_MWh'].round(4) if 'Energy_Grid_MWh' in df_15min else pd.Series([0.0] * len(df_15min))
    clipping = df_15min['Clipping_Loss_MWh'].round(4) if 'Clipping_Loss_MWh' in df_15min else pd.Series([0.0] * len(df_15min))
    
    export_df = pd.DataFrame({
        'Ngày': date_col,
        'Chu kỳ': df_15min.get('Interval_Index', range(1, len(df_15min) + 1)),
        'Thời gian Bắt đầu': df_15min.get('Start_Time', ''),
        'Thời gian Kết thúc': df_15min.get('End_Time', ''),
        'Bức xạ TB (W/m2)': irr_avg,
        'Bức xạ Max (W/m2)': irr_max,
        'Nhiệt độ Môi trường TB (°C)': amb_temp,
        'Nhiệt độ Tấm pin Cell TB (°C)': cell_temp,
        'Công suất DC TB (MW)': p_dc,
        'Công suất Inverter TB (MW)': p_inv,
        'Công suất Phát Lưới TB (MW)': p_grid,
        'Sản lượng Phát Lưới (MWh)': energy,
        'Tổn thất Xén Inverter (MWh)': clipping
    })
    return export_df


def prepare_comparison_export_dataframe(df_comp_15min: pd.DataFrame) -> pd.DataFrame:
    """
    Chuẩn hóa bảng dữ liệu Đối soát Thực Tế vs Dự Báo 96 chu kỳ
    """
    ts_series = pd.to_datetime(df_comp_15min['Timestamp']) if 'Timestamp' in df_comp_15min else pd.Series([None] * len(df_comp_15min))
    date_col = ts_series.dt.strftime('%d/%m/%Y') if ts_series.notna().any() else df_comp_15min.get('Date', '')
    
    return pd.DataFrame({
        'Ngày': date_col,
        'Chu kỳ': df_comp_15min.get('Interval_Index', range(1, len(df_comp_15min) + 1)),
        'Bắt đầu': df_comp_15min.get('Start_Time', ''),
        'Kết thúc': df_comp_15min.get('End_Time', ''),
        'Bức xạ TB (W/m2)': df_comp_15min.get('Irradiance_Avg_Wm2', 0.0).round(1),
        'P_Dự Báo (MW)': df_comp_15min.get('P_Grid_Avg_MW', 0.0).round(3),
        'P_Thực Tế 110kV (MW)': df_comp_15min.get('P_Grid_Actual_Avg_MW', 0.0).round(3),
        'Độ Lệch Công Suất (MW)': df_comp_15min.get('Diff_Power_MW', 0.0).round(3),
        'Sản Lượng Dự Báo (MWh)': df_comp_15min.get('Energy_Grid_MWh', 0.0).round(4),
        'Sản Lượng Thực Tế (MWh)': df_comp_15min.get('Energy_Actual_MWh', 0.0).round(4),
        'Chênh Lệch Điện Năng (MWh)': df_comp_15min.get('Diff_Energy_MWh', 0.0).round(4),
        'Điện Áp 110kV TB (kV)': df_comp_15min.get('U_110kV_Avg', 110.0).round(2),
        'Tần Số TB (Hz)': df_comp_15min.get('F_Hz_Avg', 50.0).round(3)
    })


def export_to_excel_bytes(df_15min: pd.DataFrame, kpi_summary: Dict[str, Any]) -> bytes:
    """
    Tạo file Excel (.xlsx) báo cáo dự báo
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#1E3A8A', 'font_color': 'white', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1E3A8A'})
        kpi_label_format = workbook.add_format({'bold': True, 'fg_color': '#F3F4F6', 'border': 1})
        kpi_val_format = workbook.add_format({'align': 'right', 'border': 1})
        num_format = workbook.add_format({'num_format': '#,##0.000', 'border': 1})
        num_format_1dp = workbook.add_format({'num_format': '#,##0.0', 'border': 1})
        num_format_4dp = workbook.add_format({'num_format': '#,##0.0000', 'border': 1})
        center_format = workbook.add_format({'align': 'center', 'border': 1})
        
        export_df = prepare_export_dataframe(df_15min)
        sheet_name = 'Du_Bao_15Phut'
        export_df.to_excel(writer, sheet_name=sheet_name, startrow=3, index=False)
        ws = writer.sheets[sheet_name]
        
        ws.write('A1', f"DỰ BÁO SẢN LƯỢNG ĐIỆN MẶT TRỜI CHU KỲ 15 PHÚT - {kpi_summary.get('plant_name', 'MỸ HIỆP')}", title_format)
        ws.write('A2', f"Công suất: {kpi_summary.get('dc_capacity_mwp', 50)} MWp DC / {kpi_summary.get('ac_capacity_mw', 40.075)} MW AC | Tấm pin Sharp NU-440")
        
        for col_num, value in enumerate(export_df.columns.values):
            ws.write(3, col_num, value, header_format)
            
        ws.set_column('A:A', 12, center_format)
        ws.set_column('B:B', 9, center_format)
        ws.set_column('C:D', 14, center_format)
        ws.set_column('E:F', 14, num_format_1dp)
        ws.set_column('G:H', 15, num_format_1dp)
        ws.set_column('I:K', 16, num_format)
        ws.set_column('L:M', 18, num_format_4dp)
        
        ws_summary = workbook.add_worksheet('Tong_Hop_KPI')
        ws_summary.write('A1', "BÁO CÁO TỔNG HỢP CHỈ SỐ KỸ THUẬT & DỰ BÁO", title_format)
        
        kpis = [
            ("Tên nhà máy", kpi_summary.get('plant_name', 'Nhà máy ĐMT Mỹ Hiệp')),
            ("Công suất lắp đặt DC tấm pin (MWp)", f"{kpi_summary.get('dc_capacity_mwp', 50.0)} MWp"),
            ("Công suất giới hạn Inverter AC (MW)", f"{kpi_summary.get('ac_capacity_mw', 40.075)} MW"),
            ("Loại tấm pin quang điện", "Sharp NU-440 (Mono-Si, -0.347%/°C, NOCT 45°C)"),
            ("Tổng sản lượng điện dự báo phát lưới (MWh)", kpi_summary.get('total_energy_mwh', 0.0)),
            ("Công suất phát lưới cực đại dự kiến (MW)", kpi_summary.get('peak_grid_mw', 0.0)),
            ("Công suất DC cực đại lý thuyết (MW)", kpi_summary.get('peak_dc_mw', 0.0)),
            ("Bức xạ cực đại ghi nhận (W/m2)", kpi_summary.get('max_irradiance_wm2', 0.0)),
            ("Hệ số hiệu suất dự kiến PR (%)", f"{kpi_summary.get('performance_ratio_pct', 0.0)}%"),
            ("Sản lượng bị cắt xén do Inverter Clipping (MWh)", kpi_summary.get('total_clipping_loss_mwh', 0.0)),
            ("Tổng số chu kỳ 15 phút phân tích", kpi_summary.get('total_15min_intervals', len(df_15min))),
        ]
        
        for idx, (label, val) in enumerate(kpis, start=3):
            ws_summary.write(idx, 0, label, kpi_label_format)
            ws_summary.write(idx, 1, val, kpi_val_format)
            
        ws_summary.set_column('A:A', 45)
        ws_summary.set_column('B:B', 30)

    output.seek(0)
    return output.getvalue()


def export_multi_day_to_excel_bytes(df_15min: pd.DataFrame, df_daily: pd.DataFrame, kpis: Dict[str, Any], title_prefix: str = "2_NGAY") -> bytes:
    """
    Xuất báo cáo dự báo đa ngày (2 ngày, 7 ngày, 30 ngày)
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#1E3A8A', 'font_color': 'white', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1E3A8A'})
        num_format = workbook.add_format({'num_format': '#,##0.000', 'border': 1})
        num_format_4dp = workbook.add_format({'num_format': '#,##0.0000', 'border': 1})
        center_format = workbook.add_format({'align': 'center', 'border': 1})

        # Sheet 1: Tổng hợp từng ngày
        df_daily_exp = pd.DataFrame({
            'Ngày': df_daily['Date_Str'],
            'Tên ngày': df_daily.get('Day_Name', df_daily['Date_Str']),
            'Sản lượng phát lưới (MWh)': df_daily['Energy_MWh'].round(3),
            'P_Grid Đỉnh (MW)': df_daily['Peak_Grid_MW'].round(3),
            'Bức xạ Đỉnh (W/m2)': df_daily['Max_Irradiance_Wm2'].round(1),
            'Cắt Inverter (MWh)': df_daily['Clipping_Loss_MWh'].round(3),
            'Sản lượng tương đương (kWh/kWp)': df_daily['Specific_Yield_kWh_kWp'].round(2)
        })
        df_daily_exp.to_excel(writer, sheet_name='Tong_Hop_Tung_Ngay', startrow=3, index=False)
        ws_d = writer.sheets['Tong_Hop_Tung_Ngay']
        ws_d.write('A1', f"BÁO CÁO DỰ BÁO SẢN LƯỢNG {kpis.get('num_days')} NGÀY TỚI - ĐMT MỸ HIỆP", title_format)
        ws_d.write('A2', f"Tổng sản lượng dự báo: {kpis.get('total_energy_mwh')} MWh ({kpis.get('total_energy_gwh')} GWh) | TB: {kpis.get('avg_daily_mwh')} MWh/ngày")
        for col_num, value in enumerate(df_daily_exp.columns.values):
            ws_d.write(3, col_num, value, header_format)
        ws_d.set_column('A:B', 16, center_format)
        ws_d.set_column('C:G', 20, num_format)

        # Sheet 2: Chi tiết từng chu kỳ 15 phút
        export_15m = prepare_export_dataframe(df_15min)
        export_15m.to_excel(writer, sheet_name='Chi_Tiet_15Phut', startrow=3, index=False)
        ws_15 = writer.sheets['Chi_Tiet_15Phut']
        ws_15.write('A1', f"DỮ LIỆU ĐIỀU ĐỘ CHU KỲ 15 PHÚT ({len(df_15min)} CHU KỲ)", title_format)
        for col_num, value in enumerate(export_15m.columns.values):
            ws_15.write(3, col_num, value, header_format)
        ws_15.set_column('A:D', 14, center_format)
        ws_15.set_column('E:K', 16, num_format)
        ws_15.set_column('L:M', 18, num_format_4dp)

    output.seek(0)
    return output.getvalue()


def export_comparison_to_excel_bytes(df_comp_15min: pd.DataFrame, comp_kpis: Dict[str, Any]) -> bytes:
    """
    Xuất báo cáo đối soát & đánh giá sai số Dự Báo vs Thực Tế sang file Excel
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#047857', 'font_color': 'white', 'border': 1})
        title_format = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#047857'})
        kpi_label_format = workbook.add_format({'bold': True, 'fg_color': '#F3F4F6', 'border': 1})
        kpi_val_format = workbook.add_format({'align': 'right', 'border': 1})
        num_format = workbook.add_format({'num_format': '#,##0.000', 'border': 1})
        num_format_4dp = workbook.add_format({'num_format': '#,##0.0000', 'border': 1})
        center_format = workbook.add_format({'align': 'center', 'border': 1})
        
        comp_df = prepare_comparison_export_dataframe(df_comp_15min)
        comp_df.to_excel(writer, sheet_name='Doi_Soat_ThucTe_DuBao', startrow=3, index=False)
        ws = writer.sheets['Doi_Soat_ThucTe_DuBao']
        
        ws.write('A1', "BÁO CÁO ĐỐI SOÁT & ĐÁNH GIÁ SAI SỐ DỰ BÁO vs ĐO ĐẾM THỰC TẾ (EVN)", title_format)
        ws.write('A2', f"Nhà máy ĐMT Mỹ Hiệp (50MWp / 40.075MW) | Độ chính xác dự báo: {comp_kpis.get('accuracy_pct')}% | MAE: {comp_kpis.get('mae_mw')} MW")
        
        for col_num, value in enumerate(comp_df.columns.values):
            ws.write(3, col_num, value, header_format)
            
        ws.set_column('A:A', 12, center_format)
        ws.set_column('B:D', 10, center_format)
        ws.set_column('E:H', 15, num_format)
        ws.set_column('I:K', 16, num_format_4dp)
        ws.set_column('L:M', 14, num_format)
        
        ws_kpi = workbook.add_worksheet('Danh_Gia_Sai_So')
        ws_kpi.write('A1', "KẾT QUẢ ĐÁNH GIÁ CHỈ SỐ SAI SỐ DỰ BÁO ĐIỀU ĐỘ (EVN / A0 / A3)", title_format)
        
        kpi_list = [
            ("Độ chính xác dự báo công suất (%)", f"{comp_kpis.get('accuracy_pct')}%"),
            ("Sai số tuyệt đối trung bình - MAE (MW)", f"{comp_kpis.get('mae_mw')} MW"),
            ("Sai số toàn phương trung bình - RMSE (MW)", f"{comp_kpis.get('rmse_mw')} MW"),
            ("Tỷ lệ sai số chuẩn hóa - NMAE / 50MWp (%)", f"{comp_kpis.get('nmae_pct')}%"),
            ("Tổng sản lượng điện dự báo (MWh)", f"{comp_kpis.get('total_energy_forecast_mwh')} MWh"),
            ("Tổng sản lượng điện đo đếm thực tế 110kV (MWh)", f"{comp_kpis.get('total_energy_actual_mwh')} MWh"),
            ("Chênh lệch điện năng (Thực tế - Dự báo) (MWh)", f"{comp_kpis.get('total_diff_energy_mwh')} MWh"),
            ("Độ chính xác tổng điện năng ngày (%)", f"{comp_kpis.get('energy_accuracy_pct')}%"),
            ("Công suất phát lưới đỉnh thực tế (MW)", f"{comp_kpis.get('peak_actual_mw')} MW"),
            ("Công suất phát lưới đỉnh dự báo (MW)", f"{comp_kpis.get('peak_forecast_mw')} MW"),
            ("Tổng số chu kỳ 15 phút đối soát", comp_kpis.get('total_compared_intervals')),
        ]
        for idx, (label, val) in enumerate(kpi_list, start=3):
            ws_kpi.write(idx, 0, label, kpi_label_format)
            ws_kpi.write(idx, 1, val, kpi_val_format)
        ws_kpi.set_column('A:A', 50)
        ws_kpi.set_column('B:B', 30)

    output.seek(0)
    return output.getvalue()


def export_to_csv_bytes(df_15min: pd.DataFrame) -> bytes:
    """
    Xuất file CSV chu kỳ 15 phút chuẩn UTF-8-SIG
    """
    export_df = prepare_export_dataframe(df_15min)
    return export_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')


def export_comparison_to_csv_bytes(df_comp_15min: pd.DataFrame) -> bytes:
    """
    Xuất file CSV đối soát thực tế vs dự báo
    """
    export_df = prepare_comparison_export_dataframe(df_comp_15min)
    return export_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')


def generate_pw_template_excel_bytes(df_15min: pd.DataFrame) -> bytes:
    """
    Tạo file Excel mẫu 96 chu kỳ để người dùng nhập/chỉnh sửa Bức xạ W (W/m2) và Công suất P (MW)
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'fg_color': '#0284C7', 'font_color': 'white', 'border': 1})
        title_fmt = workbook.add_format({'bold': True, 'font_size': 13, 'font_color': '#0369A1'})
        num_fmt_w = workbook.add_format({'num_format': '#,##0.0', 'border': 1, 'align': 'right'})
        num_fmt_p = workbook.add_format({'num_format': '#,##0.000', 'border': 1, 'align': 'right'})
        num_fmt_t = workbook.add_format({'num_format': '#,##0.0', 'border': 1, 'align': 'right'})
        center_fmt = workbook.add_format({'align': 'center', 'border': 1})

        n_rows = len(df_15min) if len(df_15min) > 0 else 96
        indices = list(range(1, n_rows + 1))
        
        start_times = []
        end_times = []
        for i in range(n_rows):
            hr_s = (i * 15) // 60
            mn_s = (i * 15) % 60
            hr_e = ((i + 1) * 15) // 60
            mn_e = ((i + 1) * 15) % 60
            start_times.append(f"{hr_s:02d}:{mn_s:02d}")
            end_times.append(f"{hr_e:02d}:{mn_e:02d}" if hr_e < 24 else "24:00")
            
        w_vals = df_15min['Irradiance_Avg_Wm2'].round(1).tolist() if 'Irradiance_Avg_Wm2' in df_15min else [0.0] * n_rows
        p_vals = df_15min['P_Grid_Avg_MW'].round(3).tolist() if 'P_Grid_Avg_MW' in df_15min else [0.0] * n_rows
        t_vals = df_15min['Cell_Temp_Avg_C'].round(1).tolist() if 'Cell_Temp_Avg_C' in df_15min else [35.0] * n_rows

        template_df = pd.DataFrame({
            'Chu_Ky': indices,
            'Bat_Dau': start_times,
            'Ket_Thuc': end_times,
            'Buc_Xa_W_Wm2': w_vals,
            'Cong_Suat_P_MW': p_vals,
            'Nhiet_Do_Cell_C': t_vals,
            'Ghi_Chu': [''] * n_rows
        })

        sheet_name = 'Mau_Nhap_P_W_96CK'
        template_df.to_excel(writer, sheet_name=sheet_name, startrow=3, index=False)
        ws = writer.sheets[sheet_name]

        ws.write('A1', "BIỂU MẪU CẬP NHẬT DỮ LIỆU BỨC XẠ (W) VÀ CÔNG SUẤT (P) 96 CHU KỲ", title_fmt)
        ws.write('A2', "Nhà máy ĐMT Mỹ Hiệp (50MWp / 40.075MW) - Nhập giá trị cột Bức xạ W (W/m2) và Công suất P (MW) rồi nạp vào hệ thống.")

        for col_num, col_name in enumerate(template_df.columns):
            ws.write(3, col_num, col_name, header_fmt)

        ws.set_column('A:A', 10, center_fmt)
        ws.set_column('B:C', 12, center_fmt)
        ws.set_column('D:D', 18, num_fmt_w)
        ws.set_column('E:E', 20, num_fmt_p)
        ws.set_column('F:F', 18, num_fmt_t)
        ws.set_column('G:G', 25)

    return output.getvalue()

