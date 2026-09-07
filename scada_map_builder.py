import json
import os
import plotly.graph_objects as go
import pandas as pd
import numpy as np

LAYOUT_JSON_PATH = os.path.join(os.path.dirname(__file__), 'scada_layout_config.json')

# Fallback config builder if json not found
def get_scada_layout_config():
    if os.path.exists(LAYOUT_JSON_PATH):
        with open(LAYOUT_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Return empty dict if missing
    return {}

def create_scada_overview_figure(df_strings: pd.DataFrame, station_filter: str = "Tất Cả 7 Trạm (S1 - S7)"):
    config = get_scada_layout_config()
    if not config:
        # Load from default brain scratch if in dev
        scratch_json = r"C:\Users\Dell\.gemini\antigravity\brain\b8633267-b26f-494f-a358-1881db8d5f38\scratch\scada_layout_config.json"
        if os.path.exists(scratch_json):
            with open(scratch_json, "r", encoding="utf-8") as f:
                config = json.load(f)

    # Index df_strings by Inverter_ID
    inv_map = {}
    if not df_strings.empty and 'Inverter_ID' in df_strings.columns:
        for _, r in df_strings.iterrows():
            inv_map[str(r['Inverter_ID']).strip()] = r

    fig = go.Figure()

    # 1. Background dark canvas matching SCADA HMI
    fig.add_shape(
        type="rect",
        x0=0, y0=90, x1=1020, y1=850,
        fillcolor="#050B14",
        line=dict(color="#1E293B", width=2),
        layer="below"
    )

    # 2. Main Cable & Road Arteries (matching SCADA Overview lines)
    fig.add_shape(type="line", x0=390, y0=180, x1=390, y1=720, line=dict(color="#334155", width=4, dash="dot"))
    fig.add_shape(type="line", x0=660, y0=180, x1=660, y1=720, line=dict(color="#334155", width=4, dash="dot"))
    fig.add_shape(type="line", x0=260, y0=385, x1=660, y1=385, line=dict(color="#1E293B", width=3))
    fig.add_shape(type="line", x0=260, y0=510, x1=660, y1=510, line=dict(color="#1E293B", width=3))
    fig.add_shape(type="line", x0=260, y0=630, x1=660, y1=630, line=dict(color="#1E293B", width=3))

    # 3. 110kV Substation Box (Top Left)
    fig.add_shape(
        type="rect",
        x0=300, y0=120, x1=460, y1=165,
        fillcolor="#0F172A",
        line=dict(color="#38BDF8", width=2)
    )
    fig.add_annotation(
        x=380, y=142,
        text="⚡ <b>TRẠM 110kV PHÙ MỸ NAM</b><br><span style='font-size:9px;color:#94A3B8'>110kV SUBSTATION DEIVCE</span>",
        showarrow=False,
        font=dict(color="#38BDF8", size=10),
        align="center"
    )

    # 4. Inverter Badges and Station Houses
    scatter_x = []
    scatter_y = []
    scatter_text = []
    scatter_hover = []

    target_st_tag = station_filter.split(' ')[0] if "Tất Cả" not in station_filter else "ALL"

    for s_tag, s_data in config.items():
        if target_st_tag != "ALL" and s_tag != target_st_tag:
            continue

        # Station Control House
        st_box = s_data['station_box']
        
        # Check how many inverters are faulty in this station
        st_inv_ids = list(s_data['inverters'].keys())
        st_faults = sum(1 for iid in st_inv_ids if inv_map.get(iid, {}).get('Health_Status', 'NORMAL') != 'NORMAL')
        st_color = "#EF4444" if st_faults >= 10 else ("#F59E0B" if st_faults > 0 else "#10B981")

        fig.add_shape(
            type="rect",
            x0=st_box['x'] - 42, y0=st_box['y'] - 11,
            x1=st_box['x'] + 42, y1=st_box['y'] + 11,
            fillcolor=st_color,
            line=dict(color="#FFFFFF", width=1.5),
            layer="above"
        )
        fig.add_annotation(
            x=st_box['x'], y=st_box['y'],
            text=f"<b>{st_box['label']}</b>",
            showarrow=False,
            font=dict(color="#FFFFFF", size=10, family="monospace"),
            align="center"
        )

        # Inverters in this station
        for inv_id, pos in s_data['inverters'].items():
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
            else:
                h_st = 'CRITICAL'
                p_dc = 0.0
                act_s = 0
                inst_s = 18
                loss_kw = 175.0
                anomaly = 'Thiếu Dữ Liệu SmartLogger'
                root_cause = 'Inverter chưa add vào SmartLogger hoặc mất kết nối RS485.'
                rec = 'Quét lại mạng RS485 và thêm Inverter vào SmartLogger.'

            if h_st == 'CRITICAL':
                border_color = "#EF4444"
                status_icon = "🔴"
                dot_color = "#EF4444"
            elif h_st == 'MAJOR':
                border_color = "#EA580C"
                status_icon = "🟠"
                dot_color = "#EA580C"
            elif h_st in ['MINOR', 'WARNING']:
                border_color = "#F59E0B"
                status_icon = "🟡"
                dot_color = "#F59E0B"
            else:
                border_color = "#10B981"
                status_icon = "🟢"
                dot_color = "#10B981"

            disp_name = inv_id.replace('INV', '')

            hover_html = (
                f"<b>{status_icon} INVERTER {inv_id} ({s_tag})</b><br>"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
                f"• <b>Tình trạng:</b> {anomaly}<br>"
                f"• <b>Công suất Pdc:</b> {p_dc:.1f} kW<br>"
                f"• <b>Chuỗi hoạt động:</b> {act_s}/{inst_s} Strings ({'17S Thiết kế' if inst_s==17 else '18S Đủ'})<br>"
                f"• <b>Tổn thất ước tính:</b> {loss_kw:.1f} kW<br>"
                f"• <b>Chẩn đoán:</b> {root_cause}<br>"
                f"• <b>Khuyến nghị O&M:</b> {rec}"
            )

            box_w = 34
            box_h = 11
            fig.add_shape(
                type="rect",
                x0=pos['x'] - box_w/2, y0=pos['y'] - box_h/2,
                x1=pos['x'] + box_w/2, y1=pos['y'] + box_h/2,
                fillcolor="#1E293B",
                line=dict(color=border_color, width=1.5),
                layer="above"
            )

            # Dot indicator matching SCADA
            fig.add_shape(
                type="rect",
                x0=pos['x'] + box_w/2 - 5, y0=pos['y'] - box_h/2 + 2,
                x1=pos['x'] + box_w/2 - 1, y1=pos['y'] + box_h/2 - 2,
                fillcolor=dot_color,
                line=dict(color="#FFFFFF", width=0.5),
                layer="above"
            )

            scatter_x.append(pos['x'] - 2)
            scatter_y.append(pos['y'])
            scatter_text.append(f"<b>{disp_name}</b>")
            scatter_hover.append(hover_html)

    # Add text labels on inverters
    fig.add_trace(go.Scatter(
        x=scatter_x,
        y=scatter_y,
        mode="text",
        text=scatter_text,
        textfont=dict(size=8.5, color="#F8FAFC", family="monospace"),
        hoverinfo="text",
        hovertext=scatter_hover,
        hoverlabel=dict(bgcolor="#0F172A", font_size=12, font_family="sans-serif"),
        showlegend=False
    ))

    # Zoom bounds if filtered by station
    x_range = [0, 1020]
    y_range = [850, 90]
    if target_st_tag != "ALL" and target_st_tag in config:
        st_xs = [pos['x'] for pos in config[target_st_tag]['inverters'].values()]
        st_ys = [pos['y'] for pos in config[target_st_tag]['inverters'].values()]
        x_min, x_max = min(st_xs) - 60, max(st_xs) + 60
        y_min, y_max = min(st_ys) - 40, max(st_ys) + 40
        x_range = [x_min, x_max]
        y_range = [y_max, y_min]

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=x_range),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=y_range, autorange="reversed"),
        paper_bgcolor="#0F172A",
        plot_bgcolor="#0F172A",
        height=720 if target_st_tag == "ALL" else 550,
        margin=dict(l=15, r=15, t=15, b=15)
    )

    return fig
