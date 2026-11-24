@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" backend\launch.py %*
) else (
  set "PYTHONPATH=%~dp0..\..\work\python"
  if exist "%ProgramFiles%\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe" (
    "%ProgramFiles%\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt\dependencies\python\python.exe" backend\launch.py %*
  ) else (
    echo Run the setup in README.md on this machine, then launch again.
    pause
    exit /b 1
  )
)
if errorlevel 1 pause
