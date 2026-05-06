# FlowScope Demo Trading - Setup Script
# PowerShell script untuk setup dan menjalankan sistem demo trading

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FlowScope Demo Trading Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if virtual environment exists
Write-Host "[1/5] Checking virtual environment..." -ForegroundColor Yellow
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "✓ Virtual environment found" -ForegroundColor Green
} else {
    Write-Host "✗ Virtual environment not found. Creating..." -ForegroundColor Red
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
}

# 2. Activate virtual environment
Write-Host ""
Write-Host "[2/5] Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"
Write-Host "✓ Virtual environment activated" -ForegroundColor Green

# 3. Install dependencies
Write-Host ""
Write-Host "[3/5] Installing Python dependencies..." -ForegroundColor Yellow
pip install python-binance --quiet
if (Test-Path ".\backend\services\binance_demo\requirements.txt") {
    pip install -r .\backend\services\binance_demo\requirements.txt --quiet
}
Write-Host "✓ Dependencies installed" -ForegroundColor Green

# 4. Check .env file
Write-Host ""
Write-Host "[4/5] Checking environment configuration..." -ForegroundColor Yellow
if (Test-Path ".\.env") {
    Write-Host "✓ .env file found" -ForegroundColor Green
    Write-Host ""
    Write-Host "⚠ IMPORTANT: Make sure you have configured:" -ForegroundColor Yellow
    Write-Host "   FLOWSCOPE_BINANCE_TESTNET_API_KEY=your_key_here" -ForegroundColor White
    Write-Host "   FLOWSCOPE_BINANCE_TESTNET_SECRET_KEY=your_secret_here" -ForegroundColor White
    Write-Host ""
    Write-Host "Get your testnet keys from: https://testnet.binancefuture.com" -ForegroundColor Cyan
} else {
    Write-Host "✗ .env file not found. Creating from example..." -ForegroundColor Red
    if (Test-Path ".\.env.example") {
        Copy-Item ".\.env.example" ".\.env"
        Write-Host "✓ .env created. Please edit with your Binance Testnet credentials" -ForegroundColor Green
    }
}

# 5. Database check
Write-Host ""
Write-Host "[5/5] Checking database connection..." -ForegroundColor Yellow
Write-Host "Make sure PostgreSQL is running and flowscope_db exists" -ForegroundColor White

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Edit .env file with your Binance Testnet API credentials" -ForegroundColor White
Write-Host "   Get keys from: https://testnet.binancefuture.com" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Run the backend server:" -ForegroundColor White
Write-Host "   python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Open frontend dashboard in browser:" -ForegroundColor White
Write-Host "   frontend/demo/index.html" -ForegroundColor Cyan
Write-Host "   Or run: python -m http.server 3000 -d frontend/demo" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. Access dashboard at: http://localhost:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "For detailed instructions, see: DEMO_TRADING_GUIDE.md" -ForegroundColor Cyan
Write-Host ""
