import json
import os
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import plotly.graph_objects as go
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(__file__)
BASE_IMG_PATH = os.path.join(BASE_DIR, 'scada_overview_base.png')
COORDS_PATH = os.path.join(BASE_DIR, 'scada_coords_1080p.json')

def load_scada_coords():
    if os.path.exists(COORDS_PATH):
        with open(COORDS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def generate_annotated_scada_image(df_strings: pd.DataFrame, station_filter: str = "Tất Cả 7 Trạm (S1 - S7)") -> Image.Image:
    """Tạo ảnh SCADA 1920x1082 chuẩn từ OVERVIEW229.pdf kèm đánh dấu vị trí các Inverter lỗi"""
    if os.path.exists(BASE_IMG_PATH):
        img = Image.open(BASE_IMG_PATH).convert('RGB')
    else:
        # Fallback create dark canvas
        img = Image.new('RGB', (1920, 1082), color=(11, 15, 25))

    draw = ImageDraw.Draw(img, 'RGBA')
    coords = load_scada_coords()

    inv_map = {}
    if not df_strings.empty and 'Inverter_ID' in df_strings.columns:
        for _, r in df_strings.iterrows():
            inv_map[str(r['Inverter_ID']).strip()] = r

    target_st_tag = station_filter.split(' ')[0] if "Tất Cả" not in station_filter else "ALL"

    for s_tag, inverters in coords.items():
        if target_st_tag != "ALL" and s_tag != target_st_tag:
            continue

        for inv_id, pos in inverters.items():
            r = inv_map.get(inv_id)
            
            if r is not None:
                h_st = r.get('Health_Status', 'NORMAL')
                dead_s = int(r.get('Dead_Strings_Count', 0))
                act_s = int(r.get('Active_Strings', 18))
                inst_s = int(r.get('Installed_Strings', 18))
                loss_kw = float(r.get('Est_Loss_kW', 0.0))
            else:
                h_st = 'CRITICAL'
                dead_s = 18
                act_s = 0
                inst_s = 18
                loss_kw = 175.0

            x = pos['x']
            y = pos['y']
            box_w = 64
            box_h = 16

            # Determine fault colors & highlight
            if h_st == 'CRITICAL':
                # Bright Red glowing box on inverter
                draw.rectangle([x - box_w/2 - 2, y - box_h/2 - 2, x + box_w/2 + 2, y + box_h/2 + 2], outline=(239, 68, 68, 255), width=2)
                draw.rectangle([x - box_w/2, y - box_h/2, x + box_w/2, y + box_h/2], fill=(239, 68, 68, 120))
                # Red dot
                draw.rectangle([x - box_w/2 + 2, y - box_h/2 + 2, x - box_w/2 + 12, y + box_h/2 - 2], fill=(239, 68, 68, 255))
            elif h_st == 'MAJOR':
                # Bright Orange box
                draw.rectangle([x - box_w/2 - 2, y - box_h/2 - 2, x + box_w/2 + 2, y + box_h/2 + 2], outline=(234, 88, 12, 255), width=2)
                draw.rectangle([x - box_w/2, y - box_h/2, x + box_w/2, y + box_h/2], fill=(234, 88, 12, 100))
                draw.rectangle([x - box_w/2 + 2, y - box_h/2 + 2, x - box_w/2 + 12, y + box_h/2 - 2], fill=(234, 88, 12, 255))
            elif h_st in ['MINOR', 'WARNING']:
                # Yellow box
                draw.rectangle([x - box_w/2 - 2, y - box_h/2 - 2, x + box_w/2 + 2, y + box_h/2 + 2], outline=(245, 158, 11, 255), width=2)
                draw.rectangle([x - box_w/2, y - box_h/2, x + box_w/2, y + box_h/2], fill=(245, 158, 11, 80))
                draw.rectangle([x - box_w/2 + 2, y - box_h/2 + 2, x - box_w/2 + 12, y + box_h/2 - 2], fill=(245, 158, 11, 255))
            else:
                # Normal green dot
                draw.rectangle([x - box_w/2 + 2, y - box_h/2 + 2, x - box_w/2 + 12, y + box_h/2 - 2], fill=(16, 185, 129, 255))

    return img


def create_scada_overview_figure(df_strings: pd.DataFrame, station_filter: str = "Tất Cả 7 Trạm (S1 - S7)") -> go.Figure:
    """Tạo biểu đồ Plotly tương tác trên nền ảnh gốc chuẩn OVERVIEW229.pdf"""
    annotated_img = generate_annotated_scada_image(df_strings, station_filter)
    coords = load_scada_coords()

    # Convert PIL Image to Base64 for Plotly background
    buffered = io.BytesIO()
    annotated_img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    img_uri = f"data:image/png;base64,{img_b64}"

    inv_map = {}
    if not df_strings.empty and 'Inverter_ID' in df_strings.columns:
        for _, r in df_strings.iterrows():
            inv_map[str(r['Inverter_ID']).strip()] = r

    target_st_tag = station_filter.split(' ')[0] if "Tất Cả" not in station_filter else "ALL"

    scatter_x = []
    scatter_y = []
    scatter_hover = []
    scatter_text = []

    for s_tag, inverters in coords.items():
        if target_st_tag != "ALL" and s_tag != target_st_tag:
            continue

        for inv_id, pos in inverters.items():
            r = inv_map.get(inv_id)
            
            if r is not None:
                h_st = r.get('Health_Status', 'NORMAL')
                p_dc = float(r.get('Total_Pdc_kW', 0.0))
                act_s = int(r.get('Active_Strings', 18))
                inst_s = int(r.get('Installed_Strings', 18))
                loss_kw = float(r.get('Est_Loss_kW', 0.0))
                anomaly = r.get('Anomaly_Type', 'Bình Thường')
                root_cause = r.get('Root_Cause', '')
                rec = r.get('Action_Recommendation', '')
                sn = r.get('SN', '--')
            else:
                h_st = 'CRITICAL'
                p_dc = 0.0
                act_s = 0
                inst_s = 18
                loss_kw = 175.0
                anomaly = 'Thiếu Dữ Liệu SmartLogger'
                root_cause = 'Inverter chưa add vào SmartLogger hoặc mất kết nối RS485.'
                rec = 'Quét lại mạng RS485 và thêm Inverter vào SmartLogger.'
                sn = '--'

            status_icon = "🔴" if h_st == 'CRITICAL' else ("🟠" if h_st == 'MAJOR' else ("🟡" if h_st in ['MINOR', 'WARNING'] else "🟢"))

            hover_html = (
                f"<b>{status_icon} INVERTER {inv_id} ({s_tag})</b><br>"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
                f"• <b>Tình trạng:</b> {anomaly}<br>"
                f"• <b>Công suất Pdc:</b> {p_dc:.1f} kW<br>"
                f"• <b>Chuỗi hoạt động:</b> {act_s}/{inst_s} Strings ({'17S Thiết kế' if inst_s==17 else '18S Đủ'})<br>"
                f"• <b>Tổn thất ước tính:</b> {loss_kw:.1f} kW<br>"
                f"• <b>Số Seri (SN):</b> {sn}<br>"
                f"• <b>Chẩn đoán:</b> {root_cause}<br>"
                f"• <b>Khuyến nghị O&M:</b> {rec}<extra></extra>"
            )

            scatter_x.append(pos['x'])
            scatter_y.append(pos['y'])
            scatter_hover.append(hover_html)
            scatter_text.append(inv_id)

    fig = go.Figure()

    # Interactive Scatter Hover Layer over exact Inverter coordinates
    fig.add_trace(go.Scatter(
        x=scatter_x,
        y=scatter_y,
        mode="markers",
        marker=dict(
            size=18,
            color='rgba(0,0,0,0)', # transparent clickable hitbox
            line=dict(width=0)
        ),
        hoverinfo="text",
        hovertext=scatter_hover,
        hoverlabel=dict(bgcolor="#0F172A", font_size=12, font_family="sans-serif"),
        showlegend=False
    ))

    # Zoom bounds
    x_range = [0, 1920]
    y_range = [1082, 0] # Top-down reversed

    if target_st_tag != "ALL" and target_st_tag in coords:
        st_xs = [pos['x'] for pos in coords[target_st_tag].values()]
        st_ys = [pos['y'] for pos in coords[target_st_tag].values()]
        x_min = max(0, min(st_xs) - 100)
        x_max = min(1920, max(st_xs) + 100)
        y_min = max(0, min(st_ys) - 70)
        y_max = min(1082, max(st_ys) + 70)
        x_range = [x_min, x_max]
        y_range = [y_max, y_min]

    # Background layout image from OVERVIEW229.pdf
    fig.add_layout_image(
        dict(
            source=img_uri,
            xref="x",
            yref="y",
            x=0,
            y=0,
            sizex=1920,
            sizey=1082,
            sizing="stretch",
            opacity=1.0,
            layer="below"
        )
    )

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=x_range),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=y_range, autorange="reversed"),
        paper_bgcolor="#0B0F19",
        plot_bgcolor="#0B0F19",
        height=720 if target_st_tag == "ALL" else 580,
        margin=dict(l=10, r=10, t=10, b=10)
    )

    return fig
