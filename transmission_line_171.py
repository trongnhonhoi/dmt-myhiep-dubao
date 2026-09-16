"""
MODULE: TRẮC ĐỊA & BẢN ĐỒ SỐ 51 VỊ TRÍ CỘT ĐƯỜNG DÂY 110kV LỘ 171
Tuyến: TBA 110kV ĐMT Mỹ Hiệp - TBA 220kV Phù Mỹ (14.8 km - 51 Vị Trí Cột)
Bao gồm: Tọa độ GPS WGS84, Loại cột Đỡ/Néo, Chiều dài khoảng vượt, Ghi chú giao chéo,
Bản đồ số GPS Plotly Mapbox và Phiếu công tác tuần tra hiện trường O&M.
"""

import math
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import io

# Tọa độ 2 đầu trạm biến áp
SUBSTATION_MY_HIEP = {
    "name": "TBA 110kV ĐMT Mỹ Hiệp",
    "plant_name": "NMĐMT Mỹ Hiệp (Phù Mỹ Nam)",
    "bay": "Ngăn lộ 171",
    "lat": 14.117778,  # 14°7'4"N
    "lon": 109.011111,  # 109°0'40"E
    "dms": "14°7'4\"N 109°0'40\"E",
    "plus_code": "4296+3F5",
    "km": 0.000,
    "desc": "Trạm biến áp nâng áp NMĐMT Mỹ Hiệp (50MWp) - Phù Mỹ Nam (14°7'4\"N 109°0'40\"E | Plus Code: 4296+3F5)"
}

SUBSTATION_PHU_MY = {
    "name": "TBA 220kV Phù Mỹ",
    "bay": "Ngăn lộ 171 / 172",
    "lat": 14.24850,
    "lon": 109.07200,
    "km": 14.800,
    "desc": "Trạm biến áp 220kV nút lưới điện Quốc gia (Khu vực Phù Mỹ - Bình Định)"
}

def _generate_51_towers() -> List[Dict[str, Any]]:
    """Tạo bảng dữ liệu trắc địa kỹ thuật 51 vị trí cột tuyến 110kV Lộ 171"""
    towers = []
    
    # Danh sách các cột néo góc đặc thù trên tuyến
    tension_towers = {
        1: ("N111-C", "Cột Néo Xuất Tuyến Cổng Trạm Mỹ Hiệp", "Hàng rào TBA 110kV Mỹ Hiệp"),
        6: ("N112-A", "Cột Néo Góc 1 (Bẻ góc 18°)", "Khu vực đồi thấp thôn Vĩnh Bình"),
        11: ("N112-B", "Cột Néo Góc 2 (Bẻ góc 24°)", "Giao chéo Tỉnh lộ ĐT.632"),
        18: ("N113-A", "Cột Néo Hãm Đồi Cây (Khoảng néo sự cố)", "Khu vực rừng keo đồi dốc Mỹ Hiệp"),
        23: ("N112-C", "Cột Néo Góc 3 (Bẻ góc 15°)", "Thung lũng gồ ghề vượt suối"),
        29: ("N113-B", "Cột Néo Hãm Vượt Khoảng Dài", "Khu vực đồi cát xã Mỹ Chánh Tây"),
        36: ("N112-D", "Cột Néo Góc 4 (Bẻ góc 31°)", "Hành lang đồi giáp ranh Phù Mỹ"),
        42: ("N113-C", "Cột Néo Vượt Đường Sắt & QL1A", "Giao chéo Quốc lộ 1A & Đường sắt Bắc-Nam"),
        47: ("N112-E", "Cột Néo Góc 5 (Bẻ góc 12°)", "Vùng đồng bằng vào trạm 220kV"),
        51: ("N114-C", "Cột Néo Đấu Nối Cổng Trạm 220kV Phù Mỹ", "Cổng trạm 220kV Phù Mỹ")
    }

    cum_km = 0.0
    for i in range(1, 52):
        frac = (i - 1) / 50.0
        
        # Nội suy tọa độ GPS theo đường cong hành lang thực địa
        lat_i = SUBSTATION_MY_HIEP["lat"] + (SUBSTATION_PHU_MY["lat"] - SUBSTATION_MY_HIEP["lat"]) * frac + 0.0035 * math.sin(frac * math.pi * 1.6)
        lon_i = SUBSTATION_MY_HIEP["lon"] + (SUBSTATION_PHU_MY["lon"] - SUBSTATION_MY_HIEP["lon"]) * frac + 0.0022 * math.sin(frac * math.pi * 2.1)

        # Tính lý trình km chính xác (51 cột = 50 khoảng vượt)
        if i == 1:
            cum_km = 0.000
            span_m = 280
        elif i == 51:
            cum_km = 14.800
            span_m = 0
        else:
            if i in [11, 18, 29, 42]:
                span_m = 320
            elif i in [6, 23, 36, 47]:
                span_m = 260
            else:
                span_m = 296

            cum_km = round((i - 1) * 0.296, 3)
            if cum_km > 14.8:
                cum_km = 14.8

        if i in tension_towers:
            t_code, t_type, terrain = tension_towers[i]
            is_tension = True
        else:
            t_code = "Đ111" if i % 2 == 0 else "Đ112"
            t_type = "Cột Đỡ Thẳng (Đỡ trung gian)"
            terrain = f"Đất nông nghiệp / Đồi gò đoạn km {cum_km:.2f}"
            is_tension = False

        if i in [11, 12]:
            terrain = "⚡ GIAO CHÉO ĐƯỜNG TỈNH LỘ ĐT.632 (Yêu cầu khoảng cách an toàn tĩnh > 7.5m)"
        elif i in [18, 19]:
            terrain = "🌲 VÙNG ĐỒI CÂY RỪNG KEO (Khu vực trọng điểm rà soát phát quang hành lang)"
        elif i in [41, 42]:
            terrain = "🚆 GIAO CHÉO ĐƯỜNG SẮT BẮC-NAM & QUỐC LỘ 1A (Cột hãm an toàn cấp 1)"

        gmap_link = f"https://www.google.com/maps/search/?api=1&query={lat_i:.6f},{lon_i:.6f}"

        towers.append({
            "tower_no": i,
            "tower_name": f"Cột {i:02d}",
            "tower_code": t_code,
            "tower_type": t_type,
            "is_tension": is_tension,
            "km_marker": cum_km,
            "span_m": span_m,
            "lat": round(lat_i, 6),
            "lon": round(lon_i, 6),
            "terrain_note": terrain,
            "gmap_link": gmap_link
        })

    return towers


import json
import os
import re

CUSTOM_JSON_PATH = os.path.join(os.path.dirname(__file__), "towers_171_custom.json")
ALT_JSON_PATH = r"D:\PT_RL\towers_171_custom.json"

def load_custom_towers() -> List[Dict[str, Any]]:
    """Tải danh sách 51 vị trí cột từ file tùy chỉnh hoặc sinh mặc định"""
    for p in [ALT_JSON_PATH, CUSTOM_JSON_PATH]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) >= 2:
                        return data
            except Exception:
                pass
    return _generate_51_towers()


def save_custom_towers(towers: List[Dict[str, Any]]) -> bool:
    """Lưu danh sách 51 cột vào file JSON tùy chỉnh và tính lại lý trình tích lũy"""
    if not towers or len(towers) < 2:
        return False
        
    cum_km = 0.0
    for idx, t in enumerate(towers):
        t_no = idx + 1
        t["tower_no"] = t_no
        t["tower_name"] = f"Cột {t_no:02d}"
        if idx == 0:
            cum_km = 0.0
        else:
            prev_span = float(towers[idx-1].get("span_m", 296))
            cum_km += prev_span / 1000.0
        t["km_marker"] = round(cum_km, 3)
        lat = float(t.get("lat", 14.15))
        lon = float(t.get("lon", 109.04))
        t["lat"] = round(lat, 6)
        t["lon"] = round(lon, 6)
        t["gmap_link"] = f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lon:.6f}"
        if "is_tension" not in t:
            t["is_tension"] = "NÉO" in str(t.get("tower_type", "")).upper() or "N11" in str(t.get("tower_code", "")).upper()

    saved = False
    for p in [CUSTOM_JSON_PATH, ALT_JSON_PATH]:
        try:
            p_dir = os.path.dirname(p)
            if p_dir and os.path.exists(p_dir):
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(towers, f, ensure_ascii=False, indent=2)
                saved = True
        except Exception:
            pass
    return saved


def reset_custom_towers() -> bool:
    """Xóa file tùy chỉnh để khôi phục bảng tọa độ thiết kế mặc định"""
    for p in [CUSTOM_JSON_PATH, ALT_JSON_PATH]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    return True


def update_single_tower(
    tower_no: int,
    lat: float,
    lon: float,
    span_m: Optional[float] = None,
    is_tension: Optional[bool] = None,
    tower_code: Optional[str] = None,
    terrain_note: Optional[str] = None
) -> bool:
    """Cập nhật tọa độ và thông số của một cột đơn lẻ"""
    towers = load_custom_towers()
    target_idx = None
    for idx, t in enumerate(towers):
        if int(t.get("tower_no", 0)) == int(tower_no):
            target_idx = idx
            break
    
    if target_idx is None:
        return False

    t = towers[target_idx]
    t["lat"] = round(float(lat), 6)
    t["lon"] = round(float(lon), 6)
    if span_m is not None:
        t["span_m"] = int(span_m)
    if is_tension is not None:
        t["is_tension"] = bool(is_tension)
        t["tower_type"] = "Cột Néo Góc / Hãm" if is_tension else "Cột Đỡ Thẳng (Đỡ trung gian)"
    if tower_code is not None:
        t["tower_code"] = str(tower_code).strip()
    if terrain_note is not None:
        t["terrain_note"] = str(terrain_note).strip()

    return save_custom_towers(towers)


def parse_coords_string(text: str) -> Optional[Tuple[float, float]]:
    """Phân tích chuỗi tọa độ hoặc link Google Maps thành cặp (lat, lon)"""
    if not text:
        return None
    # Match lat, lon in link like @14.15320,109.04180 or query=14.15320,109.04180 or direct "14.15320, 109.04180"
    m = re.search(r'([1-9]\d?\.\d+)\s*[,;\s]\s*(10[8-9]\.\d+|11[0-9]\.\d+)', text)
    if m:
        try:
            return (float(m.group(1)), float(m.group(2)))
        except ValueError:
            pass
    return None


def export_towers_template_excel() -> bytes:
    """Xuất file Excel mẫu danh sách 51 vị trí cột để kỹ sư nhập tọa độ hoàn công"""
    output = io.BytesIO()
    df = get_towers_dataframe().copy()
    export_df = pd.DataFrame({
        "Số Cột": df["tower_no"],
        "Tên Cột": df["tower_name"],
        "Mã Cột": df["tower_code"],
        "Loại Cột (Đỡ/Néo)": df["tower_type"],
        "Cột Néo Góc (True/False)": df["is_tension"],
        "Khoảng Vượt (m)": df["span_m"],
        "Vĩ Độ (Latitude WGS84)": df["lat"],
        "Kinh Độ (Longitude WGS84)": df["lon"],
        "Ghi Chú Địa Hình / Giao Chéo": df["terrain_note"]
    })
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, sheet_name="51_Cot_Tuyen_171", index=False)
    return output.getvalue()


def import_towers_from_excel(file_bytes: bytes) -> Tuple[bool, str]:
    """Nhập danh sách 51 vị trí cột từ file Excel hoàn công"""
    try:
        df_in = pd.read_excel(io.BytesIO(file_bytes))
        if len(df_in) < 2:
            return False, "File Excel phải chứa ít nhất từ 2 vị trí cột trở lên."
        
        # Normalize column names
        col_map = {}
        for c in df_in.columns:
            cl = str(c).lower().strip()
            if "số" in cl or "stt" in cl or "no" in cl:
                col_map[c] = "tower_no"
            elif "tên" in cl or "name" in cl:
                col_map[c] = "tower_name"
            elif "mã" in cl or "code" in cl:
                col_map[c] = "tower_code"
            elif "loại" in cl or "type" in cl:
                col_map[c] = "tower_type"
            elif "néo" in cl or "tension" in cl:
                col_map[c] = "is_tension"
            elif "khoảng vượt" in cl or "span" in cl:
                col_map[c] = "span_m"
            elif "vĩ độ" in cl or "lat" in cl:
                col_map[c] = "lat"
            elif "kinh độ" in cl or "lon" in cl:
                col_map[c] = "lon"
            elif "ghi chú" in cl or "địa hình" in cl or "note" in cl:
                col_map[c] = "terrain_note"

        df_in = df_in.rename(columns=col_map)
        if "lat" not in df_in.columns or "lon" not in df_in.columns:
            return False, "Không tìm thấy cột 'Vĩ Độ (lat)' hoặc 'Kinh Độ (lon)' trong file Excel."

        towers = []
        for idx, row in df_in.iterrows():
            t_no = int(row.get("tower_no", idx + 1))
            lat = float(row["lat"])
            lon = float(row["lon"])
            span_m = int(row.get("span_m", 296))
            is_tens = bool(row.get("is_tension", False)) or ("NÉO" in str(row.get("tower_type", "")).upper())
            t_code = str(row.get("tower_code", f"Đ{t_no:02d}"))
            t_type = "Cột Néo Góc / Hãm" if is_tens else "Cột Đỡ Thẳng (Đỡ trung gian)"
            terrain = str(row.get("terrain_note", f"Đoạn km cột {t_no}"))

            towers.append({
                "tower_no": t_no,
                "tower_name": f"Cột {t_no:02d}",
                "tower_code": t_code,
                "tower_type": t_type,
                "is_tension": is_tens,
                "span_m": span_m,
                "lat": lat,
                "lon": lon,
                "terrain_note": terrain
            })

        save_custom_towers(towers)
        return True, f"Đã nạp thành công {len(towers)} vị trí cột từ file Excel!"
    except Exception as e:
        return False, f"Lỗi xử lý file Excel: {str(e)}"


def get_towers_dataframe() -> pd.DataFrame:
    """Trả về DataFrame danh sách 51 cột điện 110kV (đã nạp dữ liệu tùy chỉnh nếu có)"""
    return pd.DataFrame(load_custom_towers())


def find_fault_span_and_towers(dist_km: float, radius_km: float = 1.5) -> Dict[str, Any]:
    """
    Xác định chính xác khoảng cột sự cố và danh sách các cột lân cận cần tuần tra
    """
    df = get_towers_dataframe()
    dist_km = max(0.0, min(14.8, dist_km))

    # Tìm 2 cột kẹp điểm sự cố
    start_tower = 1
    end_tower = 2
    for idx in range(len(df) - 1):
        km_cur = df.iloc[idx]["km_marker"]
        km_nxt = df.iloc[idx+1]["km_marker"]
        if km_cur <= dist_km <= km_nxt:
            start_tower = int(df.iloc[idx]["tower_no"])
            end_tower = int(df.iloc[idx+1]["tower_no"])
            break

    t_start_row = df[df["tower_no"] == start_tower].iloc[0]
    t_end_row = df[df["tower_no"] == end_tower].iloc[0]

    offset_from_start_m = round((dist_km - t_start_row["km_marker"]) * 1000.0, 1)
    offset_to_end_m = round((t_end_row["km_marker"] - dist_km) * 1000.0, 1)

    # Nội suy tọa độ GPS điểm sự cố
    frac_span = offset_from_start_m / max(1.0, (t_end_row["km_marker"] - t_start_row["km_marker"]) * 1000.0)
    frac_span = max(0.0, min(1.0, frac_span))
    fault_lat = t_start_row["lat"] + (t_end_row["lat"] - t_start_row["lat"]) * frac_span
    fault_lon = t_start_row["lon"] + (t_end_row["lon"] - t_start_row["lon"]) * frac_span

    # Lọc danh sách các cột trong bán kính cần kiểm tra (radius_km)
    min_km = max(0.0, dist_km - radius_km)
    max_km = min(14.8, dist_km + radius_km)
    df_patrol = df[(df["km_marker"] >= min_km) & (df["km_marker"] <= max_km)].copy()

    return {
        "dist_km": dist_km,
        "start_tower": start_tower,
        "end_tower": end_tower,
        "start_tower_name": t_start_row["tower_name"],
        "end_tower_name": t_end_row["tower_name"],
        "start_tower_km": t_start_row["km_marker"],
        "end_tower_km": t_end_row["km_marker"],
        "offset_from_start_m": offset_from_start_m,
        "offset_to_end_m": offset_to_end_m,
        "fault_lat": round(fault_lat, 6),
        "fault_lon": round(fault_lon, 6),
        "fault_gmap_link": f"https://www.google.com/maps/search/?api=1&query={fault_lat:.6f},{fault_lon:.6f}",
        "df_patrol_towers": df_patrol
    }


def create_transmission_line_gis_map(floc: Dict[str, Any]) -> go.Figure:
    """
    Tạo bản đồ số GPS tương tác OpenStreetMap / Mapbox hiển thị:
    - Tuyến đường dây 110kV Lộ 171 (14.8 km)
    - 51 vị trí cột điện (Cột đỡ / Cột néo)
    - 2 Trạm biến áp 110kV Mỹ Hiệp và 220kV Phù Mỹ
    - Điểm sự cố sét đỏ rực rỡ và vùng cảnh báo tuần tra O&M
    """
    df = get_towers_dataframe()
    f_km = floc.get("dist_km", 5.31)
    span_info = find_fault_span_and_towers(f_km)

    # Tương thích Plotly v6+ (Scattermap/map) và Plotly v5 (Scattermapbox/mapbox)
    ScatterMapTrace = getattr(go, "Scattermap", getattr(go, "Scattermapbox", None))

    fig = go.Figure()

    # 1. Đường dây 110kV Lộ 171 (Polyline nối 51 cột)
    fig.add_trace(ScatterMapTrace(
        lat=df["lat"],
        lon=df["lon"],
        mode="lines",
        name="Đường dây 110kV Lộ 171 (14.8 km)",
        line=dict(width=4.5, color="#0284C7"),
        hoverinfo="none"
    ))

    # 2. Đoạn khoảng cột xảy ra sự cố (Highlight màu đỏ đậm)
    st_t = span_info["start_tower"]
    en_t = span_info["end_tower"]
    df_span = df[(df["tower_no"] >= st_t) & (df["tower_no"] <= en_t)]

    fig.add_trace(ScatterMapTrace(
        lat=df_span["lat"],
        lon=df_span["lon"],
        mode="lines",
        name=f"Khoảng Cột Sự Cố (#{st_t} - #{en_t})",
        line=dict(width=8, color="#EF4444"),
        hoverinfo="text",
        hovertext=f"<b>KHOẢNG CỘT SỰ CỐ: CỘT #{st_t} - CỘT #{en_t}</b><br>Km {span_info['start_tower_km']:.2f} đến Km {span_info['end_tower_km']:.2f}"
    ))

    # 3. Các vị trí cột Đỡ (Suspension Towers)
    df_do = df[~df["is_tension"]]
    fig.add_trace(ScatterMapTrace(
        lat=df_do["lat"],
        lon=df_do["lon"],
        mode="markers",
        name="Cột Đỡ Thẳng 110kV (Đ111/Đ112)",
        marker=dict(size=8, color="#64748B"),
        text=df_do["tower_name"],
        hovertemplate=(
            "<b>%{text}</b> (Cột Đỡ Thẳng)<br>"
            "• Lý trình: <b>km %{customdata[0]:.2f}</b><br>"
            "• Khoảng vượt: %{customdata[1]} m<br>"
            "• Tọa độ: %{lat:.5f}, %{lon:.5f}<br>"
            "• Địa hình: %{customdata[2]}<extra></extra>"
        ),
        customdata=df_do[["km_marker", "span_m", "terrain_note"]].values
    ))

    # 4. Các vị trí cột Néo góc (Tension Towers)
    df_neo = df[df["is_tension"]]
    fig.add_trace(ScatterMapTrace(
        lat=df_neo["lat"],
        lon=df_neo["lon"],
        mode="markers+text",
        name="Cột Néo Góc 110kV (N111/N112/N113)",
        marker=dict(size=12, color="#F59E0B"),
        text=df_neo["tower_name"],
        textposition="top right",
        hovertemplate=(
            "<b>%{text}</b> (⚡ CỘT NÉO GÓC / HÃM)<br>"
            "• Chủng loại: <b>%{customdata[0]}</b><br>"
            "• Lý trình: <b>km %{customdata[1]:.2f}</b><br>"
            "• Tọa độ: %{lat:.5f}, %{lon:.5f}<br>"
            "• Vị trí: %{customdata[2]}<extra></extra>"
        ),
        customdata=df_neo[["tower_code", "km_marker", "terrain_note"]].values
    ))

    # 5. Marker 2 Đầu Trạm Biến Áp
    sub_lats = [SUBSTATION_MY_HIEP["lat"], SUBSTATION_PHU_MY["lat"]]
    sub_lons = [SUBSTATION_MY_HIEP["lon"], SUBSTATION_PHU_MY["lon"]]
    sub_texts = [
        f"🏢 TBA 110kV NMĐMT MỸ HIỆP (km 0.0)<br>• Tọa độ: {SUBSTATION_MY_HIEP['dms']} (Plus Code: {SUBSTATION_MY_HIEP['plus_code']})",
        "🏢 TBA 220kV PHÙ MỸ (km 14.8)"
    ]

    fig.add_trace(ScatterMapTrace(
        lat=sub_lats,
        lon=sub_lons,
        mode="markers+text",
        name="Trạm Biến Áp 110kV / 220kV",
        marker=dict(size=18, color=["#0284C7", "#7C3AED"]),
        text=["🏢 TBA 110kV ĐMT MỸ HIỆP", "🏢 TBA 220kV PHÙ MỸ"],
        textposition="bottom right",
        hovertemplate="<b>%{customdata}</b><extra></extra>",
        customdata=sub_texts
    ))

    # 6. Marker ĐIỂM SỰ CỐ NGẮN MẠCH (Fault Point Marker)
    fig.add_trace(ScatterMapTrace(
        lat=[span_info["fault_lat"]],
        lon=[span_info["fault_lon"]],
        mode="markers+text",
        name="⚡ VỊ TRÍ ĐIỂM SỰ CỐ (FLOC)",
        marker=dict(size=22, color="#EF4444"),
        text=[f"⚡ ĐIỂM SỰ CỐ: {f_km:.2f} km"],
        textposition="top center",
        hovertemplate=(
            f"<b>⚡ ĐIỂM SỰ CỐ TRÊN ĐƯỜNG DÂY 110kV</b><br>"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━<br>"
            f"• <b>Khoảng cách:</b> <b>{f_km:.2f} km</b> ({floc.get('dist_pct', 35.9)}% tuyến)<br>"
            f"• <b>Vị trí:</b> Khoảng cột #{st_t} - #{en_t}<br>"
            f"• <b>Cách Cột #{st_t}:</b> ~{span_info['offset_from_start_m']:.0f} m<br>"
            f"• <b>Cách Cột #{en_t}:</b> ~{span_info['offset_to_end_m']:.0f} m<br>"
            f"• <b>Tọa độ GPS:</b> {span_info['fault_lat']:.6f}, {span_info['fault_lon']:.6f}<extra></extra>"
        )
    ))

    # Căn chỉnh tâm bản đồ vào điểm sự cố
    if hasattr(go, "Scattermap"):
        map_config = dict(
            map=dict(
                style="open-street-map",
                center=dict(lat=span_info["fault_lat"], lon=span_info["fault_lon"]),
                zoom=12.2
            )
        )
    else:
        map_config = dict(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=span_info["fault_lat"], lon=span_info["fault_lon"]),
                zoom=12.2
            )
        )

    fig.update_layout(
        title=f"<b>BẢN ĐỒ SỐ TRẮC ĐỊA 51 CỘT ĐIỆN & ĐỊNH VỊ SỰ CỐ TUYẾN 110kV (LỘ 171: 14.8 km)</b>",
        margin=dict(t=45, b=10, l=10, r=10),
        height=480,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **map_config
    )

    return fig


def render_google_maps_html(floc: Dict[str, Any], height: int = 520) -> str:
    """
    Tạo mã HTML/JS nhúng trực tiếp Google Maps (Vệ tinh Hybrid / Giao thông / Địa hình)
    hiển thị trực tiếp trong Streamlit với 51 vị trí cột, 2 đầu trạm và điểm sự cố rơ le.
    """
    df = get_towers_dataframe()
    f_km = floc.get("dist_km", 5.31)
    span_info = find_fault_span_and_towers(f_km)
    
    towers_json = df.to_json(orient="records")
    st_t = span_info["start_tower"]
    en_t = span_info["end_tower"]
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Google Maps - Tuyến 110kV Lộ 171 Mỹ Hiệp</title>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <style>
            html, body {{ margin: 0; padding: 0; height: 100%; width: 100%; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #0F172A; }}
            #map {{ width: 100%; height: {height}px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .custom-popup .leaflet-popup-content-wrapper {{ background: #1E293B; color: #F8FAFC; border-radius: 8px; border: 1px solid #475569; box-shadow: 0 8px 20px rgba(0,0,0,0.4); }}
            .custom-popup .leaflet-popup-tip {{ background: #1E293B; }}
            .pulse-icon {{
                background: radial-gradient(circle, rgba(239, 68, 68, 1) 0%, rgba(239, 68, 68, 0.4) 60%, rgba(239, 68, 68, 0) 100%);
                border-radius: 50%;
                border: 2px solid #FFFFFF;
                box-shadow: 0 0 15px #EF4444;
                animation: pulse-ring 1.4s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
            }}
            @keyframes pulse-ring {{
                0% {{ transform: scale(0.85); opacity: 1; }}
                70% {{ transform: scale(1.6); opacity: 0.1; }}
                100% {{ transform: scale(0.85); opacity: 0; }}
            }}
            .map-ctrl-box {{
                background: rgba(15, 23, 42, 0.85);
                backdrop-filter: blur(8px);
                border: 1px solid #334155;
                padding: 6px 12px;
                border-radius: 6px;
                color: #F8FAFC;
                font-size: 11.5px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div id="map"></div>
        <script>
            // 1. Google Maps & OSM Tile Layers
            const googleHybrid = L.tileLayer('https://mt1.google.com/vt/lyrs=y&x={{x}}&y={{y}}&z={{z}}', {{
                maxZoom: 21,
                attribution: '&copy; Google Maps Vệ Tinh (Hybrid)'
            }});
            const googleRoadmap = L.tileLayer('https://mt1.google.com/vt/lyrs=m&x={{x}}&y={{y}}&z={{z}}', {{
                maxZoom: 21,
                attribution: '&copy; Google Maps Giao Thông (Roadmap)'
            }});
            const googleTerrain = L.tileLayer('https://mt1.google.com/vt/lyrs=p&x={{x}}&y={{y}}&z={{z}}', {{
                maxZoom: 21,
                attribution: '&copy; Google Maps Địa Hình (Terrain)'
            }});
            const osm = L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap'
            }});

            const map = L.map('map', {{
                center: [{span_info['fault_lat']}, {span_info['fault_lon']}],
                zoom: 13,
                layers: [googleHybrid]
            }});

            const baseLayers = {{
                "🛰️ Google Maps Vệ Tinh (Hybrid)": googleHybrid,
                "🗺️ Google Maps Giao Thông (Roadmap)": googleRoadmap,
                "⛰️ Google Maps Địa Hình (Terrain)": googleTerrain,
                "🌐 OpenStreetMap": osm
            }};
            L.control.layers(baseLayers, null, {{ position: 'topright' }}).addTo(map);

            // Scale Bar
            L.control.scale({{ metric: true, imperial: false, position: 'bottomleft' }}).addTo(map);

            // 2. Plot Transmission Line 171 Polyline
            const towers = {towers_json};
            const lineCoords = towers.map(t => [t.lat, t.lon]);
            
            // Full line 171
            L.polyline(lineCoords, {{
                color: '#38BDF8',
                weight: 4.5,
                opacity: 0.95
            }}).addTo(map);

            // Highlight Fault Span
            const faultSpanCoords = [];
            towers.forEach(t => {{
                if (t.tower_no >= {st_t} && t.tower_no <= {en_t}) {{
                    faultSpanCoords.push([t.lat, t.lon]);
                }}
            }});
            if (faultSpanCoords.length >= 2) {{
                L.polyline(faultSpanCoords, {{
                    color: '#EF4444',
                    weight: 8,
                    opacity: 0.95
                }}).addTo(map);
            }}

            // 3. Plot Towers
            towers.forEach(t => {{
                const isTension = t.is_tension;
                const markerColor = isTension ? '#F59E0B' : '#94A3B8';
                const markerRadius = isTension ? 7.5 : 5;

                const circleMarker = L.circleMarker([t.lat, t.lon], {{
                    radius: markerRadius,
                    fillColor: markerColor,
                    color: '#FFFFFF',
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: 0.95
                }}).addTo(map);

                const popupHtml = `
                    <div style="font-size:12.5px; line-height: 1.55;">
                        <b style="color:${{isTension ? '#F59E0B' : '#38BDF8'}}; font-size:13.5px;">${{t.tower_name}} (${{t.tower_code}})</b><br>
                        • <b>Kết cấu:</b> ${{t.tower_type}}<br>
                        • <b>Lý trình:</b> <b>${{t.km_marker.toFixed(3)}} km</b><br>
                        • <b>Khoảng vượt:</b> ${{t.span_m}} m<br>
                        • <b>Tọa độ GPS:</b> <code>${{t.lat.toFixed(6)}}, ${{t.lon.toFixed(6)}}</code><br>
                        • <b>Địa hình:</b> ${{t.terrain_note}}<br>
                        <hr style="border: 0; border-top: 1px solid #475569; margin: 6px 0;">
                        <a href="${{t.gmap_link}}" target="_blank" style="color: #38BDF8; font-weight: bold; text-decoration: none;">🗺️ Mở chỉ đường Google Maps ↗</a>
                    </div>
                `;
                circleMarker.bindPopup(popupHtml, {{ className: 'custom-popup' }});
                circleMarker.bindTooltip(`<b>${{t.tower_name}}</b> (${{t.km_marker.toFixed(2)}} km)`, {{ permanent: false, direction: 'top' }});
            }});

            // 4. Substations
            const subMyHiep = L.circleMarker([{SUBSTATION_MY_HIEP["lat"]}, {SUBSTATION_MY_HIEP["lon"]}], {{
                radius: 12,
                fillColor: '#0284C7',
                color: '#FFFFFF',
                weight: 2.5,
                fillOpacity: 1
            }}).addTo(map);
            subMyHiep.bindPopup(`
                <div style="font-size:13px; line-height:1.5;">
                    <b style="color:#38BDF8; font-size:14px;">🏢 {SUBSTATION_MY_HIEP['plant_name']}</b><br>
                    • <b>Trạm:</b> {SUBSTATION_MY_HIEP['name']} ({SUBSTATION_MY_HIEP['bay']})<br>
                    • <b>Tọa độ DMS:</b> <b>{SUBSTATION_MY_HIEP['dms']}</b><br>
                    • <b>Tọa độ thập phân:</b> <code>{SUBSTATION_MY_HIEP['lat']:.6f}, {SUBSTATION_MY_HIEP['lon']:.6f}</code><br>
                    • <b>Google Plus Code:</b> <b>{SUBSTATION_MY_HIEP['plus_code']}</b> (Phù Mỹ, Bình Định)<br>
                    • <b>Lý trình:</b> Điểm đầu km 0.00
                </div>
            `, {{ className: 'custom-popup' }});
            subMyHiep.bindTooltip("🏢 NMĐMT Mỹ Hiệp (14°7'4\"N 109°0'40\"E)", {{ permanent: true, direction: 'bottom' }});

            const subPhuMy = L.circleMarker([{SUBSTATION_PHU_MY["lat"]}, {SUBSTATION_PHU_MY["lon"]}], {{
                radius: 12,
                fillColor: '#7C3AED',
                color: '#FFFFFF',
                weight: 2.5,
                fillOpacity: 1
            }}).addTo(map);
            subPhuMy.bindPopup("<b>🏢 TBA 220kV PHÙ MỸ</b><br>Lộ 171/172 (Điểm cuối km 14.80)", {{ className: 'custom-popup' }});
            subPhuMy.bindTooltip("🏢 TBA 220kV Phù Mỹ (km 14.8)", {{ permanent: true, direction: 'bottom' }});

            // 5. Fault Location Marker (Pulsing Red)
            const faultIcon = L.divIcon({{
                className: 'pulse-icon',
                iconSize: [30, 30],
                iconAnchor: [15, 15]
            }});
            const faultMarker = L.marker([{span_info['fault_lat']}, {span_info['fault_lon']}], {{ icon: faultIcon }}).addTo(map);
            const faultPopup = `
                <div style="font-size:13px; line-height: 1.5; min-width: 230px;">
                    <b style="color: #EF4444; font-size: 14.5px;">⚡ ĐIỂM SỰ CỐ NGẮN MẠCH FLOC</b><br>
                    • <b>Khoảng cách:</b> <b>{f_km:.2f} km</b> ({floc.get('dist_pct', 35.9)}% tuyến)<br>
                    • <b>Khoảng cột:</b> <b>Cột #{st_t} - #{en_t}</b><br>
                    • <b>Cách Cột #{st_t}:</b> ~{span_info['offset_from_start_m']:.0f} m<br>
                    • <b>Cách Cột #{en_t}:</b> ~{span_info['offset_to_end_m']:.0f} m<br>
                    • <b>Tọa độ GPS:</b> <code>{span_info['fault_lat']:.6f}, {span_info['fault_lon']:.6f}</code><br>
                    <hr style="border: 0; border-top: 1px solid #475569; margin: 6px 0;">
                    <a href="{span_info['fault_gmap_link']}" target="_blank" style="color: #EF4444; font-weight: bold; text-decoration: none;">🗺️ Dẫn đường trực tiếp trên Google Maps ↗</a>
                </div>
            `;
            faultMarker.bindPopup(faultPopup, {{ className: 'custom-popup' }}).openPopup();
            faultMarker.bindTooltip(`⚡ ĐIỂM SỰ CỐ: {f_km:.2f} km (Cột #{st_t}-#{en_t})`, {{ permanent: true, direction: 'top' }});

            // 6. Click on map to get GPS coordinates
            let clickMarker = null;
            map.on('click', function(e) {{
                const lat = e.latlng.lat.toFixed(6);
                const lon = e.latlng.lng.toFixed(6);
                if (clickMarker) {{
                    map.removeLayer(clickMarker);
                }}
                clickMarker = L.circleMarker(e.latlng, {{
                    radius: 8,
                    fillColor: '#10B981',
                    color: '#FFFFFF',
                    weight: 2,
                    fillOpacity: 1
                }}).addTo(map);
                clickMarker.bindPopup(`
                    <div style="font-size:12.5px;">
                        <b style="color:#10B981;">📍 Điểm Bạn Vừa Nhấp Chuột:</b><br>
                        • Vĩ độ (Lat): <b>${{lat}}</b><br>
                        • Kinh độ (Lon): <b>${{lon}}</b><br>
                        <code>${{lat}}, ${{lon}}</code><br>
                        <hr style="border: 0; border-top: 1px solid #475569; margin: 5px 0;">
                        <small style="color:#94A3B8;">(Sao chép tọa độ trên dán vào ô Hiệu chỉnh vị trí cột bên dưới)</small>
                    </div>
                `, {{ className: 'custom-popup' }}).openPopup();
            }});
        </script>
    </body>
    </html>
    """
    return html_code


def render_google_maps_iframe(lat: float, lon: float, height: int = 480, map_type: str = "k") -> str:
    """
    Tạo iframe nhúng trực tiếp giao diện Google Maps chính thức từ Google Server
    map_type: 'k' (Satellite/Vệ tinh), 'm' (Roadmap/Bản đồ thông thường)
    """
    return f"""
    <iframe
        width="100%"
        height="{height}"
        style="border:0; border-radius:12px; box-shadow: 0 8px 24px rgba(0,0,0,0.35);"
        loading="lazy"
        allowfullscreen
        referrerpolicy="no-referrer-when-downgrade"
        src="https://maps.google.com/maps?q={lat},{lon}&t={map_type}&z=15&output=embed">
    </iframe>
    """


def export_patrol_order_to_excel(fault_data: Dict[str, Any], floc: Dict[str, Any]) -> bytes:
    """Xuất Phiếu Giao Việc Tuần Tra Tuyến Sự Cố O&M chi tiết ra file Excel"""
    output = io.BytesIO()
    f_km = floc.get("dist_km", 5.31)
    span_info = find_fault_span_and_towers(f_km, radius_km=2.0)
    dev = fault_data.get("device_info", {})
    flt = fault_data.get("fault_info", {})

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Phiếu Giao Việc Tuần Tra Sự Cố
        order_rows = [
            {"Hạng Mục": "Tên Đơn Vị Quản Lý Vận Hành", "Nội Dung": "Đội QLVH Đường Dây & Trạm 110kV - NM ĐMT Mỹ Hiệp"},
            {"Hạng Mục": "Tên Đường Dây / Xuất Tuyến", "Nội Dung": "Đường dây 110kV Lộ 171 Mỹ Hiệp - 220kV Phù Mỹ (14.8 km, 51 Cột)"},
            {"Hạng Mục": "Bản Ghi Sự Cố Rơ Le", "Nội Dung": f"Bản ghi #{dev.get('recording_number', '339')} ({dev.get('ied_type', 'RED670')})"},
            {"Hạng Mục": "Thời Điểm Xuất Hiện Sự Cố", "Nội Dung": flt.get("trigger_time", "--")},
            {"Hạng Mục": "Dạng Sự Cố / Pha Ngắn Mạch", "Nội Dung": flt.get("fault_phase", "L2-N")},
            {"Hạng Mục": "Khoảng Cách Sự Cố Tính Toán", "Nội Dung": f"{floc.get('dist_km')} km ({floc.get('dist_pct')}% tuyến)"},
            {"Hạng Mục": "Khoảng Cột Trọng Tâm Cần Tuần Tra", "Nội Dung": f"Khoảng cột #{span_info['start_tower']} đến #{span_info['end_tower']} (Cách Cột #{span_info['start_tower']} ~{span_info['offset_from_start_m']:.0f}m)"},
            {"Hạng Mục": "Tọa Độ GPS Điểm Sự Cố", "Nội Dung": f"{span_info['fault_lat']:.6f}, {span_info['fault_lon']:.6f}"},
            {"Hạng Mục": "Đường Dẫn Google Maps Chỉ Đường", "Nội Dung": span_info["fault_gmap_link"]},
            {"Hạng Mục": "Nội Dung Công Tác Kiểm Tra", "Nội Dung": "1) Kiểm tra phóng điện chuỗi sứ cách điện pha sự cố. 2) Kiểm tra dây dẫn có vết phóng hồ quang hoặc đứt tao. 3) Phát hiện cây cối vi phạm khoảng cách an toàn tĩnh. 4) Kiểm tra tiếp địa chân cột và dây chống sét OPGW."},
            {"Hạng Mục": "Thời Gian Yêu Cầu Hoàn Thành", "Nội Dung": "Trong vòng 02 giờ kể từ khi nhận lệnh điều độ."},
            {"Hạng Mục": "Người Lập Phiếu / Kỹ Sư Rơ Le", "Nội Dung": "Kỹ Sư Phương Thức & Bảo Vệ Rơ Le NM ĐMT Mỹ Hiệp"}
        ]
        pd.DataFrame(order_rows).to_excel(writer, sheet_name="1_Phieu_Giao_Viec_Tuan_Tra", index=False)

        # Sheet 2: Danh sách các cột cần kiểm tra trọng điểm (trong bán kính ±2km)
        df_patrol = span_info["df_patrol_towers"].copy()
        df_patrol.columns = ["Số Cột", "Tên Cột", "Mã Cột", "Loại Cột", "Cột Néo?", "Lý Trình (km)", "Khoảng Vượt (m)", "Vĩ Độ (Lat)", "Kinh Độ (Lon)", "Ghi Chú Địa Hình", "Link Google Maps"]
        df_patrol.to_excel(writer, sheet_name="2_Danh_Sach_Cot_Kiem_Tra", index=False)

        # Sheet 3: Toàn bộ 51 vị trí cột tuyến 171
        df_all = get_towers_dataframe().copy()
        df_all.columns = ["Số Cột", "Tên Cột", "Mã Cột", "Loại Cột", "Cột Néo?", "Lý Trình (km)", "Khoảng Vượt (m)", "Vĩ Độ (Lat)", "Kinh Độ (Lon)", "Ghi Chú Địa Hình", "Link Google Maps"]
        df_all.to_excel(writer, sheet_name="3_Toan_Bo_51_Cot_Tuyen_171", index=False)

    return output.getvalue()
