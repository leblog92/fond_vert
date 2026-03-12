# Kill all Python processes
taskkill /F /IM python.exe
taskkill /F /IM pythonw.exe

# Kill specific script
taskkill /F /IM python.exe /FI "WINDOWTITLE eq script_name.py"