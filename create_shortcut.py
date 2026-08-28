import os
import subprocess

desktop_dir = os.path.join(os.environ.get('USERPROFILE', r'C:\Users\Dell'), 'Desktop')
project_dir = r'C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep'
target_vbs = os.path.join(project_dir, 'Chay_Ung_Dung_DMT_MyHiep.vbs')
icon_file = os.path.join(project_dir, 'dist', 'DMT_MyHiep_DuBao', 'DMT_MyHiep_DuBao.exe')
shortcut_path = os.path.join(desktop_dir, 'DMT_MyHiep_DuBao.lnk')

vbs_code = f'''Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "wscript.exe"
oLink.Arguments = """{target_vbs}"""
oLink.WorkingDirectory = "{project_dir}"
oLink.Description = "Nha May Dien Mat Troi My Hiep - He Thong Du Bao San Luong (50MWp / 40.075MW)"
If oWS.ExpandEnvironmentStrings("{icon_file}") <> "" Then
    oLink.IconLocation = "{icon_file},0"
End If
oLink.Save
'''

tmp_vbs = os.path.join(project_dir, '_make_link.vbs')
with open(tmp_vbs, 'w', encoding='utf-8') as f:
    f.write(vbs_code)

try:
    subprocess.run(['cscript', '//nologo', tmp_vbs], check=True)
    print("SUCCESS: Desktop Shortcut created pointing to silent launcher with app icon!")
finally:
    if os.path.exists(tmp_vbs):
        os.remove(tmp_vbs)
