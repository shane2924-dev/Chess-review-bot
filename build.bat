@echo off
cd /d "%~dp0"
python -m pip install pyinstaller fastapi uvicorn python-chess
python -m PyInstaller --noconfirm --onedir --name ChessReviewBot --add-data "index.html;." --collect-submodules uvicorn --collect-submodules anyio server.py
echo.
echo Done. Your app is in dist\ChessReviewBot
echo Copy your Stockfish folder into dist\ChessReviewBot, then zip that folder to share it.
pause
