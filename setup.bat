@echo off
REM Setup script for Agent QA Mentor (Windows)

echo 🚀 Setting up Agent QA Mentor...

REM Create virtual environment
echo 📦 Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo ✅ Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️  Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo 📥 Installing dependencies...
pip install -r requirements.txt

REM Create .env from example if it doesn't exist
if not exist .env (
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env
    echo ⚠️  Please edit .env and add your GEMINI_API_KEY
) else (
    echo ✅ .env file already exists
)

echo.
echo ✅ Setup complete!
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate.bat
echo.
echo Don't forget to add your GEMINI_API_KEY to .env file!
pause

