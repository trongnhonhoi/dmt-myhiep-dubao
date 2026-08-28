"""
Tạo các file dữ liệu mẫu 1-phút (.txt, .xlsx và .csv) để người dùng thử nghiệm import
Bao gồm file TXT chuẩn trạm SCADA ĐMT Mỹ Hiệp (Station 02, Station 06)
"""

import os
from solar_engine import generate_synthetic_1min_data, generate_scada_txt_sample_content

def generate_sample_files():
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    os.makedirs(sample_dir, exist_ok=True)
    
    # 1. File TXT SCADA chuẩn trạm thời tiết Mỹ Hiệp (Station 02, Station 06)
    scada_txt_content = generate_scada_txt_sample_content()
    scada_path = os.path.join(sample_dir, "Du_Lieu_Tram_SCADA_MyHiep_1Phut.txt")
    with open(scada_path, "w", encoding="utf-8") as f:
        f.write(scada_txt_content)
    print(f"Created: {scada_path}")
    
    # 2. File Excel ngày nắng đẹp
    df_sunny = generate_synthetic_1min_data(
        start_date="2026-08-26",
        num_days=1,
        weather_type="Nắng đẹp (Clear Sky)"
    )
    sunny_path = os.path.join(sample_dir, "Du_Lieu_Mau_1Phut_Ngay_Nang_Dep.xlsx")
    df_sunny.to_excel(sunny_path, index=False)
    print(f"Created: {sunny_path}")
    
    # 3. File CSV ngày có mây thay đổi
    df_cloudy = generate_synthetic_1min_data(
        start_date="2026-08-27",
        num_days=1,
        weather_type="Có mây thay đổi (Partly Cloudy)"
    )
    cloudy_path = os.path.join(sample_dir, "Du_Lieu_Mau_1Phut_Ngay_May_Thay_Doi.csv")
    df_cloudy.to_csv(cloudy_path, index=False, encoding='utf-8-sig')
    print(f"Created: {cloudy_path}")

if __name__ == "__main__":
    generate_sample_files()
