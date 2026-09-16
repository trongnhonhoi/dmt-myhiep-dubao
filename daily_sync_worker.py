r"""
DAEMON / BACKGROUND WORKER: TỰ ĐỘNG CẬP NHẬT DỮ LIỆU SCADA & DỰ BÁO LÚC 08:00 SÁNG HÀNG NGÀY
NHÀ MÁY ĐIỆN MẶT TRỜI MỸ HIỆP (50MWp / 40.075MW) - PHÙ MỸ, BÌNH ĐỊNH

Tự động thực hiện độc lập (kể cả khi phần mềm giao diện Streamlit tắt):
1. Quét và đồng bộ toàn bộ dữ liệu SCADA từ máy chủ: D:\DATA SERVER PV 01
2. Cập nhật dữ liệu chẩn đoán chuỗi Inverter (D:\STRING_INV) và Log biến tần (D:\LOG)
3. Cập nhật dữ liệu đo đếm công tơ điện lực (D:\METER) và sự cố rơ le (D:\PT_RL)
4. Thu thập dự báo thời tiết khí tượng NWP (Open-Meteo) và chạy mô hình Hybrid AI 96 chu kỳ
5. Ghi nhật ký vận hành (logs/daily_sync.log) và cập nhật trạng thái tự động (auto_harvest_status.json)
"""

import os
import sys
import json
import time
import logging
import argparse
import subprocess
from datetime import datetime, date, timedelta

# Đảm bảo stdout/stderr hỗ trợ UTF-8 trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Đảm bảo đường dẫn import thư mục dự án
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# Thiết lập thư mục logs
LOG_DIR = os.path.join(PROJECT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "daily_sync.log")
STATUS_FILE = os.path.join(PROJECT_DIR, "auto_harvest_status.json")

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

TASK_NAME = "DMT_MyHiep_AutoSync_8AM"


def perform_full_synchronization() -> dict:
    """Thực thi toàn bộ quy trình đồng bộ dữ liệu lúc 08:00 sáng"""
    start_time = datetime.now()
    logging.info("=" * 65)
    logging.info(f"[AUTO-SYNC] BAT DAU DONG BO DU LIEU TU DONG [08:00 SANG] - {start_time.strftime('%d/%m/%Y %H:%M:%S')}")
    logging.info("=" * 65)

    sync_report = {
        "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "RUNNING",
        "scada_server": {},
        "weather_nwp": {},
        "string_diagnostics": {},
        "meters": {},
        "relay_faults": {},
        "forecast_96_cycles": {},
        "errors": []
    }

    try:
        # 1. Đồng bộ Máy Chủ SCADA (D:\DATA SERVER PV 01)
        import data_harvester as dh
        harvester = dh.DataHarvester()
        server_ok = harvester.check_server_connection()
        if server_ok:
            available_dates = harvester.scan_available_dates(force_rescan=True)
            latest_date = harvester.get_latest_date_entry()
            latest_str = latest_date['date_str'] if latest_date else "--"
            logging.info(f"[*] SCADA Server ({dh.DEFAULT_SERVER_PATH}): Da quet {len(available_dates)} ngay. Moi nhat: {latest_str}")
            sync_report["scada_server"] = {
                "connected": True,
                "path": dh.DEFAULT_SERVER_PATH,
                "total_dates": len(available_dates),
                "latest_date": latest_str
            }
        else:
            logging.warning(f"[!] Khong tim thay duong dan Server SCADA {dh.DEFAULT_SERVER_PATH}, su dung che do du phong.")
            sync_report["scada_server"] = {"connected": False, "note": "Fallback mock mode active"}

        # 2. Thu thập dự báo thời tiết khí tượng NWP (Phù Mỹ, Bình Định)
        import weather_forecast_engine as wfe
        try:
            nwp_data = wfe.fetch_phu_my_weather_forecast(days=7)
            if nwp_data:
                df_15, df_d, kpis = wfe.convert_nwp_to_15min_dispatch(nwp_data)
                hybrid_15, hybrid_d, hybrid_kpis = wfe.generate_unified_hybrid_forecast(start_date=date.today())
                today_energy = round(float(hybrid_kpis[0].get('total_energy_mwh', 0)), 2) if hybrid_kpis else 0.0
                logging.info(f"[*] Du bao NWP & Hybrid AI: Da cap nhat 7 ngay thoi tiet ({len(df_15)} chu ky 15 phut). San luong du kien: {today_energy} MWh")
                sync_report["weather_nwp"] = {
                    "success": True,
                    "forecast_days": 7,
                    "intervals_15min": len(df_15),
                    "today_expected_energy_mwh": today_energy
                }
        except Exception as e_w:
            logging.error(f"[!] Loi cap nhat thoi tiet NWP: {e_w}")
            sync_report["errors"].append(f"Weather NWP Error: {e_w}")

        # 3. Đồng bộ & Chẩn đoán 229 Inverter / 4.058 Chuỗi String DC (D:\STRING_INV)
        import string_diagnostic_engine as sde
        try:
            str_mgr = sde.StringDataManager(sde.DEFAULT_STRING_PATH)
            df_strings = str_mgr.load_string_data()
            wo_df = str_mgr.get_om_work_orders(df_strings)
            logging.info(f"[*] Chan doan String DC: {len(df_strings)} Inverter / 4.058 chuoi, {len(wo_df)} phieu O&M can xu ly")
            sync_report["string_diagnostics"] = {
                "total_inverters": len(df_strings),
                "work_orders_count": len(wo_df),
                "total_pdc_kw": round(df_strings['Total_Pdc_kW'].sum(), 1),
                "total_loss_kw": round(df_strings['Est_Loss_kW'].sum(), 1)
            }
        except Exception as e_s:
            logging.error(f"[!] Loi chan doan String DC: {e_s}")
            sync_report["errors"].append(f"String Engine Error: {e_s}")

        # 4. Đồng bộ 4 Công tơ đo đếm điện lực (D:\METER) & Đối soát lịch sử
        import meter_summary_engine as mse
        import historical_data_manager as hdm
        try:
            meter_mgr = mse.MeterDataManager(mse.DEFAULT_METER_PATH)
            df_meters = meter_mgr.load_all_meters()
            hist_df = hdm.get_historical_meter_data()
            logging.info(f"[*] Cong to do dem: {len(df_meters)} cong to, {len(hist_df)} ban ghi lich su 2020-2026")
            sync_report["meters"] = {
                "meters_count": len(df_meters),
                "history_records": len(hist_df)
            }
        except Exception as e_m:
            logging.error(f"[!] Loi do dem cong to: {e_m}")
            sync_report["errors"].append(f"Meter Engine Error: {e_m}")

        # 5. Đồng bộ Rơ le Bảo vệ Ngăn 171 & Ngăn 131 MBA T1 (D:\PT_RL)
        import relay_fault_analyzer as rfa
        try:
            relay_mgr = rfa.RelayFaultAnalyzer(rfa.DEFAULT_RELAY_PATH)
            files = relay_mgr.scan_relay_files()
            logging.info(f"[*] Ro le Bao ve (D:\\PT_RL): Da quet {len(files)} tep su co (Bay 171 & 131)")
            sync_report["relay_faults"] = {
                "scanned_files": len(files)
            }
        except Exception as e_r:
            logging.error(f"[!] Loi ro le bao ve: {e_r}")
            sync_report["errors"].append(f"Relay Analyzer Error: {e_r}")

        # Hoàn tất
        sync_report["status"] = "SUCCESS" if not sync_report["errors"] else "PARTIAL_SUCCESS"
        duration_sec = (datetime.now() - start_time).total_seconds()
        sync_report["duration_seconds"] = round(duration_sec, 2)
        logging.info(f"[+] HOAN TAT DONG BO 08:00 SANG TRONG {duration_sec:.2f} GIAY. TRANG THAI: {sync_report['status']}")

    except Exception as e_main:
        logging.critical(f"[!] LOI TRONG QUA TRINH DONG BO: {e_main}", exc_info=True)
        sync_report["status"] = "FAILED"
        sync_report["errors"].append(str(e_main))

    # Ghi file trạng thái
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(sync_report, f, ensure_ascii=False, indent=2)

    return sync_report


def setup_windows_task_scheduler() -> bool:
    """Tạo tác vụ tự động hàng ngày 08:00 AM trong Windows Task Scheduler"""
    python_exe = sys.executable
    script_path = os.path.abspath(__file__)
    cmd = (
        f'schtasks /create /tn "{TASK_NAME}" '
        f'/tr "\"{python_exe}\" \"{script_path}\" --run-now" '
        f'/sc daily /st 08:00 /f'
    )
    logging.info(f"Dang dang ky tac vu Windows Task Scheduler: {TASK_NAME} luc 08:00 hang ngay...")
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            logging.info(f"[+] DA DANG KY THANH CONG TAC VU: {TASK_NAME} (08:00 AM Moi Ngay)!")
            print(f"[*] DA THIET LAP THANH CONG: Windows Task Scheduler '{TASK_NAME}' se tu dong chay luc 08:00 Sang moi ngay ke ca khi phan mem tat!")
            return True
        else:
            logging.error(f"[-] Khong the tao tac vu: {res.stderr}")
            print(f"[-] Loi dang ky: {res.stderr}")
            return False
    except Exception as e:
        logging.error(f"[-] Ngoai le khi tao Task Scheduler: {e}")
        return False


def get_sync_status() -> dict:
    """Đọc trạng thái đồng bộ gần nhất"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "status": "NOT_RUN_YET",
        "timestamp": "--",
        "note": "Chua co luot dong bo nao duoc ghi nhan."
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DMT My Hiep Daily 08:00 AM Auto Sync Engine")
    parser.add_argument("--run-now", action="store_true", help="Chay dong bo du lieu ngay lap tuc")
    parser.add_argument("--setup-scheduler", action="store_true", help="Cai dat lich chay tu dong 8:00 sang trong Windows")
    parser.add_argument("--status", action="store_true", help="Xem trang thai dong bo gan nhat")

    args = parser.parse_args()

    if args.setup_scheduler:
        setup_windows_task_scheduler()
    elif args.status:
        st_data = get_sync_status()
        print(json.dumps(st_data, indent=2, ensure_ascii=False))
    else:
        # Mặc định: thực thi đồng bộ
        perform_full_synchronization()
