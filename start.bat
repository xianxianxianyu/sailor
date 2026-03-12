@echo off
cd /d "%~dp0"
echo Starting Sailor (Backend + Frontend)...
echo.
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Worker: python -m backend.worker
echo.
echo Press Ctrl+C to stop.
echo.
npm run dev
