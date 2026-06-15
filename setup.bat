@echo off
:: ============================================================
:: AV SHIELD — FABLE 5 AGENT PLATFORM
:: setup.bat — One-Click Windows Setup Script
:: Double-click this file to deploy the entire platform
:: ============================================================

title AV Shield — Fable 5 Platform Setup
color 0A
cls

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║     AV SHIELD — FABLE 5 PLATFORM SETUP              ║
echo ║     Automated Deployment Script                      ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  This script will:
echo  1. Check and install Python
echo  2. Create your project folder
echo  3. Set up your credentials
echo  4. Install all dependencies
echo  5. Set up GitHub
echo  6. Test the platform
echo  7. Deploy to DigitalOcean
echo.
pause

:: ============================================================
:: STEP 1 — CHECK PYTHON
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 1 — Checking Python                           ║
echo ╚══════════════════════════════════════════════════════╝
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo  ⚠️  Python not found. Opening download page...
    echo.
    echo  IMPORTANT: When installer opens:
    echo  ✅ CHECK "Add Python to PATH" at the bottom
    echo  Then click Install Now
    echo.
    start https://www.python.org/downloads/
    echo  Press any key AFTER Python is installed and you restarted this script...
    pause
    exit
) else (
    for /f "tokens=*" %%i in ('python --version') do set PYVER=%%i
    echo  ✅ %PYVER% found
)

:: Check pip
pip --version > nul 2>&1
if %errorlevel% neq 0 (
    echo  Installing pip...
    python -m ensurepip --upgrade
)
echo  ✅ pip ready
echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 2 — CHECK GIT
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 2 — Checking Git                              ║
echo ╚══════════════════════════════════════════════════════╝
echo.

git --version > nul 2>&1
if %errorlevel% neq 0 (
    echo  ⚠️  Git not found. Opening download page...
    start https://git-scm.com/download/win
    echo.
    echo  Install Git then press any key to continue...
    pause
) else (
    for /f "tokens=*" %%i in ('git --version') do set GITVER=%%i
    echo  ✅ %GITVER% found
)
echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 3 — CREATE PROJECT FOLDER
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 3 — Creating Project Folder                   ║
echo ╚══════════════════════════════════════════════════════╝
echo.

set PROJECT_DIR=%USERPROFILE%\Documents\av-shield-agents
echo  Creating: %PROJECT_DIR%
echo.

if not exist "%PROJECT_DIR%" (
    mkdir "%PROJECT_DIR%"
    echo  ✅ Folder created
) else (
    echo  ✅ Folder already exists
)

:: Copy all agent files to project folder
echo  Copying agent files...
copy /Y "%~dp0*.py" "%PROJECT_DIR%\" > nul 2>&1
copy /Y "%~dp0requirements.txt" "%PROJECT_DIR%\" > nul 2>&1
copy /Y "%~dp0Procfile" "%PROJECT_DIR%\" > nul 2>&1
copy /Y "%~dp0.gitignore" "%PROJECT_DIR%\" > nul 2>&1
echo  ✅ All 15 files copied to project folder
echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 4 — CREATE .ENV FILE
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 4 — Setting Up Your Credentials               ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  I'll ask for your API keys now.
echo  These are stored ONLY on your PC in the .env file.
echo  They are NEVER uploaded to GitHub.
echo.

set ENV_FILE=%PROJECT_DIR%\.env

:: Check if .env already exists
if exist "%ENV_FILE%" (
    echo  ⚠️  .env file already exists.
    set /p OVERWRITE= Overwrite it? (y/n): 
    if /i "%OVERWRITE%" neq "y" goto SKIP_ENV
)

echo.
echo  Enter your API keys below.
echo  Press Enter to skip any you don't have yet.
echo  (You can edit %ENV_FILE% later)
echo.

set /p ANTHROPIC_KEY= Anthropic API Key (sk-ant-...): 
set /p GHL_KEY= GHL Private Integration Token: 
set /p GHL_LOC= GHL Location ID: 
set /p TWILIO_SID= Twilio Account SID (AC...): 
set /p TWILIO_TOKEN= Twilio Auth Token: 
set /p TWILIO_PHONE= Twilio Phone Number (+1661...): 
set /p MAPS_KEY= Google Maps API Key: 
set /p ELEVENLABS_KEY= ElevenLabs API Key: 
set /p ELEVENLABS_VOICE= ElevenLabs Voice ID (Sasha's voice): 
set /p DO_TOKEN= DigitalOcean API Token: 
set /p SHAD_PHONE= Your Cell Number for Alerts (+1661...): 

:: Write .env file
echo # AV Shield — Fable 5 Platform Credentials > "%ENV_FILE%"
echo # Generated: %date% %time% >> "%ENV_FILE%"
echo # NEVER share or upload this file >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # Anthropic >> "%ENV_FILE%"
echo ANTHROPIC_API_KEY=%ANTHROPIC_KEY% >> "%ENV_FILE%"
echo ANTHROPIC_MODEL=claude-sonnet-4-6 >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # GoHighLevel >> "%ENV_FILE%"
echo GHL_API_KEY=%GHL_KEY% >> "%ENV_FILE%"
echo GHL_LOCATION_ID=%GHL_LOC% >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # Twilio >> "%ENV_FILE%"
echo TWILIO_ACCOUNT_SID=%TWILIO_SID% >> "%ENV_FILE%"
echo TWILIO_AUTH_TOKEN=%TWILIO_TOKEN% >> "%ENV_FILE%"
echo TWILIO_PHONE_NUMBER=%TWILIO_PHONE% >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # Google >> "%ENV_FILE%"
echo GOOGLE_MAPS_API_KEY=%MAPS_KEY% >> "%ENV_FILE%"
echo GOOGLE_SERVICE_ACCOUNT_PATH=%PROJECT_DIR%\google_service_account.json >> "%ENV_FILE%"
echo GMAIL_CREDS_PATH=%PROJECT_DIR%\gmail_credentials.json >> "%ENV_FILE%"
echo GMAIL_TOKEN_PATH=%PROJECT_DIR%\gmail_token.json >> "%ENV_FILE%"
echo GOOGLE_WORKSPACE_DOMAIN=avsurveillance.com >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # ElevenLabs >> "%ENV_FILE%"
echo ELEVENLABS_API_KEY=%ELEVENLABS_KEY% >> "%ENV_FILE%"
echo ELEVENLABS_VOICE_ID=%ELEVENLABS_VOICE% >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # DigitalOcean >> "%ENV_FILE%"
echo DO_API_TOKEN=%DO_TOKEN% >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # Email >> "%ENV_FILE%"
echo SENDER_EMAIL=info@avsurveillance.com >> "%ENV_FILE%"
echo SALES_SENDER_EMAIL=sales@avsurveillance.com >> "%ENV_FILE%"
echo. >> "%ENV_FILE%"
echo # Alerts >> "%ENV_FILE%"
echo ESCALATION_PHONE=%SHAD_PHONE% >> "%ENV_FILE%"
echo VOICE_PORT=5000 >> "%ENV_FILE%"

echo.
echo  ✅ .env file created at %ENV_FILE%
echo.

:SKIP_ENV
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 5 — INSTALL DEPENDENCIES
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 5 — Installing Dependencies                   ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  Installing all required Python packages...
echo  This may take 2-3 minutes...
echo.

cd /d "%PROJECT_DIR%"
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo  ❌ Some packages failed to install.
    echo  Check your internet connection and try again.
    pause
    exit
)

echo.
echo  ✅ All dependencies installed
echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 6 — RUN TESTS
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 6 — Testing Platform                          ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  Running full platform test suite...
echo.

cd /d "%PROJECT_DIR%"
python test_platform.py

if %errorlevel% neq 0 (
    echo.
    echo  ⚠️  Some tests failed — check warnings above.
    echo  You can still continue — warnings are usually
    echo  just missing API keys which you add to .env later.
    echo.
    set /p CONTINUE= Continue to GitHub setup anyway? (y/n): 
    if /i "%CONTINUE%" neq "y" goto END
)

echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 7 — GITHUB SETUP
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 7 — GitHub Setup                              ║
echo ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%PROJECT_DIR%"

:: Check if already a git repo
if exist ".git" (
    echo  ✅ Git repo already initialized
) else (
    echo  Initializing Git repo...
    git init
    git add .
    git commit -m "AV Shield Fable 5 Platform — Initial Deploy"
    echo  ✅ Git repo initialized
)

echo.
echo  Now let's connect to GitHub.
echo.
echo  1. Go to github.com
echo  2. Click + New repository
echo  3. Name it: av-shield-agents
echo  4. Set to PRIVATE
echo  5. Click Create repository
echo  6. Copy the repo URL (https://github.com/YOUR-USERNAME/av-shield-agents.git)
echo.
set /p GITHUB_URL= Paste your GitHub repo URL here: 

if "%GITHUB_URL%"=="" (
    echo  ⚠️  No URL entered — skipping GitHub push
    goto SKIP_GITHUB
)

git remote remove origin > nul 2>&1
git remote add origin %GITHUB_URL%
git branch -M main
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo  ❌ GitHub push failed.
    echo  Make sure you created the repo and the URL is correct.
) else (
    echo.
    echo  ✅ Code pushed to GitHub successfully!
)

:SKIP_GITHUB
echo.
timeout /t 2 /nobreak > nul

:: ============================================================
:: STEP 8 — DIGITALOCEAN INSTRUCTIONS
:: ============================================================
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║  STEP 8 — DigitalOcean Deployment                   ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  Almost there! Final step — connect DO to GitHub.
echo.
echo  1. Go to cloud.digitalocean.com
echo  2. Click Apps → Create App
echo  3. Choose GitHub as source
echo  4. Select av-shield-agents repo
echo  5. Select main branch
echo  6. Auto-deploy: ON
echo  7. Add environment variables from your .env file
echo  8. Click Deploy
echo.
echo  Opening DigitalOcean now...
start https://cloud.digitalocean.com/apps/new
echo.
echo  Once deployed your platform is LIVE and running 24/7!
echo.

:: ============================================================
:: DONE
:: ============================================================
:END
cls
echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║     🔥 AV SHIELD SETUP COMPLETE 🔥                  ║
echo ╚══════════════════════════════════════════════════════╝
echo.
echo  Your files are at:
echo  %PROJECT_DIR%
echo.
echo  Your credentials are at:
echo  %PROJECT_DIR%\.env
echo.
echo  NEXT STEPS:
echo  1. Add any missing API keys to your .env file
echo  2. Complete DigitalOcean deployment
echo  3. Set up Twilio webhook to point to your DO URL
echo  4. Run: python do_agent.py status
echo.
echo  The platform is built. Time to go live. 💪
echo.
pause
