@echo off
echo Testing backend environment...
cd /d %~dp0backend

echo.
echo [TEST] Python version:
python --version

echo.
echo [TEST] Dependency check:
pip show fastapi uvicorn pydantic | findstr /i "Name Version"

echo.
echo [TEST] Import test:
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import requests, dotenv; print('requests/dotenv: OK')"
python -c "import pydantic; print('Pydantic:', pydantic.__version__)"

echo.
echo [TEST] Project structure:
dir /b models ai_host game_engine learning

echo.
echo [TEST] Syntax check:
python -m py_compile main.py ai_host\llm_client.py ai_host\reasoning_engine.py ai_host\host_persona.py game_engine\game_controller.py game_engine\case_generator.py learning\learning_system.py models\game_state.py
if errorlevel 1 (
    echo [FAIL] Syntax errors found!
) else (
    echo [OK] All Python files compile fine
)

echo.
echo [TEST] Done. For full API test (needs backend running):
echo   python test_api.py
pause
