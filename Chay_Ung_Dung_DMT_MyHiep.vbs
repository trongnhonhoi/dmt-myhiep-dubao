Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Dell\.gemini\antigravity\scratch\solar_forecasting_myhiep"
WshShell.Run """C:\Users\Dell\AppData\Local\Python\pythoncore-3.14-64\python.exe"" desktop_app.py", 0, False
