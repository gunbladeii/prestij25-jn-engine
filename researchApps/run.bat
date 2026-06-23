@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting Research Paper Summarizer on http://localhost:8500
echo.
uvicorn main:app --host 0.0.0.0 --port 8500 --reload
