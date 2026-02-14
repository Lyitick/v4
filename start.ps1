# ============================================================
#  Единый скрипт запуска проекта Finance Bot + Mini App
#  Запускает: Cloudflare Tunnel → FastAPI backend → Vite frontend → Telegram Bot
#  Автоматически подставляет WEBAPP_URL из туннеля в .env
# ============================================================

$ErrorActionPreference = "Stop"
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$ENV_FILE = Join-Path $PROJECT_ROOT "finance_bot\.env"
$BOT_DIR = Join-Path $PROJECT_ROOT "finance_bot"
$BACKEND_DIR = Join-Path $PROJECT_ROOT "webapp\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "webapp\frontend"

# ── Логирование ──────────────────────────────────────────────
function Log-OK($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Log-Warn($msg) { Write-Host "[!]  $msg" -ForegroundColor Yellow }
function Log-Err($msg)  { Write-Host "[X]  $msg" -ForegroundColor Red }
function Log-Info($msg) { Write-Host "[->] $msg" -ForegroundColor Cyan }

# ── Список процессов для очистки ─────────────────────────────
$script:Jobs = @()

function Stop-All {
    Write-Host ""
    Log-Warn "Остановка всех сервисов..."
    foreach ($job in $script:Jobs) {
        try {
            if ($job -and !$job.HasExited) {
                Stop-Process -Id $job.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {}
    }
    Log-OK "Все сервисы остановлены."
}

# ============================================================
#  1. Проверка зависимостей
# ============================================================
Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   Finance Bot + Mini App — Автозапуск (Windows)   " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    $py = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $py) {
    Log-Err "python не найден. Установите Python 3.10+."
    exit 1
}
$PYTHON = $py.Source
Log-OK "Python: $(&$PYTHON --version 2>&1)"

# Node.js
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Log-Err "node не найден. Установите Node.js 18+."
    exit 1
}
Log-OK "Node.js: $(node --version)"

# npm
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Log-Err "npm не найден. Установите npm."
    exit 1
}
Log-OK "npm: $(npm --version)"

# .env файл
if (-not (Test-Path $ENV_FILE)) {
    Log-Err ".env файл не найден: $ENV_FILE"
    Log-Err "Создайте файл с BOT_TOKEN=<ваш_токен>"
    exit 1
}

# BOT_TOKEN
$envContent = Get-Content $ENV_FILE -Raw
$botTokenMatch = [regex]::Match($envContent, '(?m)^BOT_TOKEN=(.+)$')
if (-not $botTokenMatch.Success) {
    Log-Err "BOT_TOKEN не найден в $ENV_FILE"
    exit 1
}
$BOT_TOKEN = $botTokenMatch.Groups[1].Value.Trim().Trim('"').Trim("'")
$tokenPreview = $BOT_TOKEN.Substring(0, 4) + "..." + $BOT_TOKEN.Substring($BOT_TOKEN.Length - 4)
Log-OK "BOT_TOKEN: $tokenPreview"

# ============================================================
#  2. Установка зависимостей
# ============================================================
Log-Info "Проверка Python-зависимостей (bot)..."
& $PYTHON -m pip install -q -r "$BOT_DIR\requirements.txt" 2>$null
Log-OK "Bot зависимости OK"

Log-Info "Проверка Python-зависимостей (backend)..."
& $PYTHON -m pip install -q -r "$BACKEND_DIR\requirements.txt" 2>$null
Log-OK "Backend зависимости OK"

Log-Info "Проверка Node.js-зависимостей (frontend)..."
if (-not (Test-Path "$FRONTEND_DIR\node_modules")) {
    Log-Info "Установка npm пакетов..."
    Push-Location $FRONTEND_DIR
    npm install --silent 2>$null
    Pop-Location
    Log-OK "Frontend зависимости установлены"
} else {
    Log-OK "Frontend зависимости OK (node_modules существует)"
}

# ============================================================
#  3. Запуск Cloudflare Tunnel (получение публичного URL)
# ============================================================
$WEBAPP_URL = ""
$tunnelLog = Join-Path $PROJECT_ROOT ".tunnel.log"

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cf) {
    Log-Info "Запуск Cloudflare Tunnel (порт 3000)..."

    $tunnelProc = Start-Process -FilePath "cloudflared" `
        -ArgumentList "tunnel","--url","http://localhost:3000" `
        -RedirectStandardError $tunnelLog `
        -WindowStyle Hidden `
        -PassThru
    $script:Jobs += $tunnelProc

    # Ждём URL (до 15 секунд)
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        if (Test-Path $tunnelLog) {
            $logText = Get-Content $tunnelLog -Raw -ErrorAction SilentlyContinue
            $urlMatch = [regex]::Match($logText, 'https://[a-z0-9-]+\.trycloudflare\.com')
            if ($urlMatch.Success) {
                $WEBAPP_URL = $urlMatch.Value
                break
            }
        }
    }

    if ($WEBAPP_URL) {
        Log-OK "Tunnel URL: $WEBAPP_URL"
    } else {
        Log-Warn "Не удалось получить URL туннеля. Используется WEBAPP_URL из .env"
        try { Stop-Process -Id $tunnelProc.Id -Force -ErrorAction SilentlyContinue } catch {}
    }
} else {
    Log-Warn "cloudflared не установлен — туннель не запущен."
    Log-Warn "Mini App будет доступен только локально (localhost:3000)."
    Log-Warn "Установите: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/"
}

# ============================================================
#  4. Обновление WEBAPP_URL в .env
# ============================================================
if ($WEBAPP_URL) {
    $lines = Get-Content $ENV_FILE
    $found = $false
    $newLines = $lines | ForEach-Object {
        if ($_ -match '^WEBAPP_URL=') {
            $found = $true
            "WEBAPP_URL=$WEBAPP_URL"
        } else {
            $_
        }
    }
    if (-not $found) {
        $newLines += "WEBAPP_URL=$WEBAPP_URL"
    }
    $newLines | Set-Content $ENV_FILE -Encoding UTF8
    Log-OK "WEBAPP_URL обновлён в .env -> $WEBAPP_URL"
} else {
    $urlMatch = [regex]::Match($envContent, '(?m)^WEBAPP_URL=(.+)$')
    if ($urlMatch.Success) {
        $WEBAPP_URL = $urlMatch.Groups[1].Value.Trim()
        Log-Warn "Используется текущий WEBAPP_URL из .env: $WEBAPP_URL"
    } else {
        Log-Warn "WEBAPP_URL не задан — кнопка Mini App в боте не будет работать"
    }
}

# ============================================================
#  5. Запуск FastAPI backend (порт 8000)
# ============================================================
Write-Host ""
Log-Info "Запуск FastAPI backend на :8000 ..."

$backendLog = Join-Path $PROJECT_ROOT ".backend.log"
$env:PYTHONPATH = "$PROJECT_ROOT;$BOT_DIR"
$backendProc = Start-Process -FilePath $PYTHON `
    -ArgumentList "-m","uvicorn","webapp.backend.main:app","--reload","--host","0.0.0.0","--port","8000","--log-level","info" `
    -WorkingDirectory $PROJECT_ROOT `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError (Join-Path $PROJECT_ROOT ".backend.err.log") `
    -WindowStyle Hidden `
    -PassThru
$script:Jobs += $backendProc

Start-Sleep -Seconds 2
if (-not $backendProc.HasExited) {
    Log-OK "Backend запущен (PID: $($backendProc.Id))"
} else {
    Log-Err "Backend не запустился! Смотрите лог: $backendLog"
    Stop-All
    exit 1
}

# ============================================================
#  6. Запуск Vite frontend (порт 3000)
# ============================================================
Log-Info "Запуск Vite frontend на :3000 ..."

$frontendLog = Join-Path $PROJECT_ROOT ".frontend.log"
$frontendProc = Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c","cd /d `"$FRONTEND_DIR`" && npm run dev" `
    -RedirectStandardOutput $frontendLog `
    -RedirectStandardError (Join-Path $PROJECT_ROOT ".frontend.err.log") `
    -WindowStyle Hidden `
    -PassThru
$script:Jobs += $frontendProc

Start-Sleep -Seconds 3
if (-not $frontendProc.HasExited) {
    Log-OK "Frontend запущен (PID: $($frontendProc.Id))"
} else {
    Log-Err "Frontend не запустился! Смотрите лог: $frontendLog"
    Stop-All
    exit 1
}

# ============================================================
#  7. Запуск Telegram Bot
# ============================================================
Log-Info "Запуск Telegram Bot..."

$botLog = Join-Path $PROJECT_ROOT ".bot.log"
$env:PYTHONPATH = "$PROJECT_ROOT;$BOT_DIR"
$botProc = Start-Process -FilePath $PYTHON `
    -ArgumentList "Bot\main.py" `
    -WorkingDirectory $BOT_DIR `
    -RedirectStandardOutput $botLog `
    -RedirectStandardError (Join-Path $PROJECT_ROOT ".bot.err.log") `
    -WindowStyle Hidden `
    -PassThru
$script:Jobs += $botProc

Start-Sleep -Seconds 2
if (-not $botProc.HasExited) {
    Log-OK "Telegram Bot запущен (PID: $($botProc.Id))"
} else {
    Log-Err "Bot не запустился! Смотрите лог: $botLog"
    Stop-All
    exit 1
}

# ============================================================
#  Готово — вывод статуса
# ============================================================
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host "   Все сервисы запущены!                           " -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend API:   http://localhost:8000/api/health" -ForegroundColor Cyan
Write-Host "  Frontend:      http://localhost:3000" -ForegroundColor Cyan
if ($WEBAPP_URL) {
    Write-Host "  Tunnel (Web):  $WEBAPP_URL" -ForegroundColor Cyan
}
Write-Host "  Telegram Bot:  активен (polling)" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Логи:" -ForegroundColor Yellow
Write-Host "    Backend:   Get-Content $backendLog -Wait"
Write-Host "    Frontend:  Get-Content $frontendLog -Wait"
Write-Host "    Bot:       Get-Content $botLog -Wait"
Write-Host ""
Write-Host "  Нажмите Ctrl+C для остановки всех сервисов." -ForegroundColor Red
Write-Host ""

# Ожидание — проверяем каждые 2 секунды, жив ли хоть один процесс
try {
    while ($true) {
        $alive = $false
        foreach ($job in $script:Jobs) {
            if ($job -and -not $job.HasExited) {
                $alive = $true
                break
            }
        }
        if (-not $alive) {
            Log-Warn "Все процессы завершились."
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-All
}
