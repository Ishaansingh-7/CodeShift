@echo off
setlocal
cd /d "%~dp0"

if not exist backend\.venv\Scripts\python.exe (
  echo Creating backend\.venv ...
  python -m venv backend\.venv || goto :fail
)
echo Checking backend packages ...
backend\.venv\Scripts\python -m pip install -q --disable-pip-version-check -r backend\requirements.txt || goto :fail

echo Checking frontend packages ...
pushd frontend
call npm install --no-audit --no-fund --loglevel=error || (popd & goto :fail)
popd

echo Stopping old servers on ports 5173 and 8000 ...
powershell -NoProfile -Command "$ps = Get-CimInstance Win32_Process; foreach ($c in Get-NetTCPConnection -State Listen -LocalPort 5173,8000 -EA 0) { $p = $ps | ? ProcessId -eq $c.OwningProcess; while ($q = $ps | ? { $_.ProcessId -eq $p.ParentProcessId -and $_.CommandLine -match 'uvicorn|vite|npm' }) { $p = $q }; if ($p) { taskkill /f /t /pid $p.ProcessId 2>&1 | Out-Null } }; for ($i = 0; $i -lt 25 -and (Get-NetTCPConnection -State Listen -LocalPort 5173,8000 -EA 0); $i++) { Start-Sleep -m 200 }"

start "CodeShift API" /d backend cmd /k ".venv\Scripts\python -m uvicorn app.main:app --reload --port 8000"
start "CodeShift Web" /d frontend cmd /k "npm run dev -- --open"
exit /b 0

:fail
echo Setup failed.
pause
exit /b 1
