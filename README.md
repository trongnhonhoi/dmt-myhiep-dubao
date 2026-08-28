# Hệ Thống Dự Báo Sản Lượng Nhà Máy Điện Mặt Trời Mỹ Hiệp

Hệ thống dự báo sản lượng điện quang điện chu kỳ 15 phút phục vụ vận hành và thị trường điện (EVN / A0 / A3).

## Thông Tin Nhà Máy
- **Tên nhà máy:** Nhà Máy Điện Mặt Trời Mỹ Hiệp
- **Công suất:** 50.00 MWp DC / 40.075 MW AC
- **Tấm pin:** Sharp NU-440 (NU-JD440 Monocrystalline)
- **Địa chỉ:** Thôn Vạn Phước, Xã Phù Mỹ Nam, Tỉnh Gia Lai
- **Điện thoại:** 0256 3856 667
- **Đơn vị điều độ:** A0 & A3

## Tính Năng Chính
1. Dự báo sản lượng 96 chu kỳ ngày (Chu kỳ 15 phút).
2. Dự báo cuốn chiếu 18 chu kỳ (4.5 giờ tới).
3. Đánh giá sai số đối soát theo quy chuẩn EVN (NMAE, MAE, RMSE).
4. Dự báo đa chu kỳ (2 ngày, 7 ngày, 30 ngày, cuối tháng, tháng tiếp theo).
5. Bản thuyết minh khí tượng & sản lượng tự động.
6. Cập nhật và nạp dữ liệu P & W tùy biến từ file SCADA / Excel ngoài.
7. Xuất báo cáo Excel / CSV chuẩn EVN / A0 / A3.

## Hướng Dẫn Chạy
```bash
pip install -r requirements.txt
streamlit run app.py
```
