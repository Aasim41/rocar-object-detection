@echo off
echo ============================================
echo   Autonomous Cart - System Launcher
echo ============================================
echo.
echo Starting FastAPI Backend on port 8000...
start "FastAPI Backend" cmd /k "cd /d %~dp0 && uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
echo.
echo Waiting 3 seconds for backend to initialize...
timeout /t 3 /nobreak >nul
echo.
echo Starting Streamlit Dashboard on port 8501...
start "Streamlit Dashboard" cmd /k "cd /d %~dp0 && streamlit run dashboard.py --server.port 8501"
echo.
echo ============================================
echo   Both services are starting!
echo   Backend:   http://localhost:8000
echo   Dashboard: http://localhost:8501
echo ============================================
echo.
pause
