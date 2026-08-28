import os
import subprocess

desktop = os.path.join(os.environ.get('USERPROFILE', r'C:\Users\Dell'), 'Desktop')
target_exe = r'C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep\dist\DMT_MyHiep_DuBao\DMT_MyHiep_DuBao.exe'
work_dir = r'C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep\dist\DMT_MyHiep_DuBao'
link_path = os.path.join(desktop, 'DMT_MyHiep_DuBao.lnk')

vbs = f'''Set ws = CreateObject("WScript.Shell")
Set sc = ws.CreateShortcut("{link_path}")
sc.TargetPath = "{target_exe}"
sc.WorkingDirectory = "{work_dir}"
sc.Description = "Nha May Dien Mat Troi My Hiep - He Thong Du Bao San Luong"
sc.Save
'''

tmp_vbs = os.path.join(work_dir, '_mklink.vbs')
with open(tmp_vbs, 'w', encoding='utf-8') as f:
    f.write(vbs)

subprocess.run(['cscript', '//nologo', tmp_vbs], check=True)
if os.path.exists(tmp_vbs):
    os.remove(tmp_vbs)

print("VERIFIED: Desktop shortcut exists ->", os.path.exists(link_path))
