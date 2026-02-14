#!/usr/bin/env bash
# ============================================================
#  Единый скрипт запуска проекта Finance Bot + Mini App
#  Запускает: Cloudflare Tunnel → FastAPI backend → Vite frontend → Telegram Bot
#  Автоматически подставляет WEBAPP_URL из туннеля в .env
# ============================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$PROJECT_ROOT/finance_bot/.env"
BOT_DIR="$PROJECT_ROOT/finance_bot"
BACKEND_DIR="$PROJECT_ROOT/webapp/backend"
FRONTEND_DIR="$PROJECT_ROOT/webapp/frontend"

# ── Цвета для вывода ─────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()   { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*"; }
info()  { echo -e "${CYAN}[→]${NC} $*"; }

# ── PID-ы запущенных процессов ───────────────────────────────
TUNNEL_PID=""
BACKEND_PID=""
FRONTEND_PID=""
BOT_PID=""

cleanup() {
    echo ""
    warn "Остановка всех сервисов..."
    for pid_var in BOT_PID FRONTEND_PID BACKEND_PID TUNNEL_PID; do
        pid="${!pid_var}"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    # Подождём завершения
    for pid_var in BOT_PID FRONTEND_PID BACKEND_PID TUNNEL_PID; do
        pid="${!pid_var}"
        if [ -n "$pid" ]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
    log "Все сервисы остановлены."
    exit 0
}

trap cleanup INT TERM

# ============================================================
#  1. Проверка зависимостей
# ============================================================
echo ""
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo -e "${CYAN}   Finance Bot + Mini App — Автозапуск            ${NC}"
echo -e "${CYAN}══════════════════════════════════════════════════${NC}"
echo ""

# Проверка Python
if ! command -v python3 &>/dev/null; then
    err "python3 не найден. Установите Python 3.10+."
    exit 1
fi
log "Python: $(python3 --version)"

# Проверка Node.js
if ! command -v node &>/dev/null; then
    err "node не найден. Установите Node.js 18+."
    exit 1
fi
log "Node.js: $(node --version)"

# Проверка npm
if ! command -v npm &>/dev/null; then
    err "npm не найден. Установите npm."
    exit 1
fi
log "npm: $(npm --version)"

# Проверка .env файла
if [ ! -f "$ENV_FILE" ]; then
    err ".env файл не найден: $ENV_FILE"
    err "Создайте файл с BOT_TOKEN=<ваш_токен>"
    exit 1
fi

# Проверка BOT_TOKEN
BOT_TOKEN=$(grep -E "^BOT_TOKEN=" "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"" | tr -d '[:space:]')
if [ -z "$BOT_TOKEN" ]; then
    err "BOT_TOKEN не найден в $ENV_FILE"
    exit 1
fi
log "BOT_TOKEN: ${BOT_TOKEN:0:4}…${BOT_TOKEN: -4}"

# ============================================================
#  2. Установка зависимостей
# ============================================================
info "Проверка Python-зависимостей (bot)..."
pip install -q -r "$BOT_DIR/requirements.txt" 2>/dev/null && log "Bot зависимости OK" || warn "Некоторые bot-зависимости не установились"

info "Проверка Python-зависимостей (backend)..."
pip install -q -r "$BACKEND_DIR/requirements.txt" 2>/dev/null && log "Backend зависимости OK" || warn "Некоторые backend-зависимости не установились"

info "Проверка Node.js-зависимостей (frontend)..."
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    info "Установка npm пакетов..."
    (cd "$FRONTEND_DIR" && npm install --silent) && log "Frontend зависимости установлены" || warn "npm install завершился с ошибками"
else
    log "Frontend зависимости OK (node_modules существует)"
fi

# ============================================================
#  3. Запуск Cloudflare Tunnel (получение публичного URL)
# ============================================================
TUNNEL_LOG="$PROJECT_ROOT/.tunnel.log"
WEBAPP_URL=""

if command -v cloudflared &>/dev/null; then
    info "Запуск Cloudflare Tunnel (порт 3000)..."
    cloudflared tunnel --url http://localhost:3000 > "$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!

    # Ждём появления URL в логах (до 15 секунд)
    for i in $(seq 1 30); do
        WEBAPP_URL=$(grep -oP 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
        if [ -n "$WEBAPP_URL" ]; then
            break
        fi
        sleep 0.5
    done

    if [ -n "$WEBAPP_URL" ]; then
        log "Tunnel URL: $WEBAPP_URL"
    else
        warn "Не удалось получить URL туннеля. Используется WEBAPP_URL из .env"
        kill "$TUNNEL_PID" 2>/dev/null || true
        TUNNEL_PID=""
    fi
else
    warn "cloudflared не установлен — туннель не запущен."
    warn "Mini App будет доступен только локально (localhost:3000)."
    warn "Установите: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/"
fi

# ============================================================
#  4. Обновление WEBAPP_URL в .env
# ============================================================
if [ -n "$WEBAPP_URL" ]; then
    if grep -q "^WEBAPP_URL=" "$ENV_FILE"; then
        # Заменяем существующее значение
        sed -i "s|^WEBAPP_URL=.*|WEBAPP_URL=$WEBAPP_URL|" "$ENV_FILE"
    else
        # Добавляем новую строку
        echo "WEBAPP_URL=$WEBAPP_URL" >> "$ENV_FILE"
    fi
    log "WEBAPP_URL обновлён в .env → $WEBAPP_URL"
else
    WEBAPP_URL=$(grep -E "^WEBAPP_URL=" "$ENV_FILE" | cut -d'=' -f2- | tr -d "'\"" | tr -d '[:space:]')
    if [ -n "$WEBAPP_URL" ]; then
        warn "Используется текущий WEBAPP_URL из .env: $WEBAPP_URL"
    else
        warn "WEBAPP_URL не задан — кнопка Mini App в боте не будет работать"
    fi
fi

# ============================================================
#  5. Запуск FastAPI backend (порт 8000)
# ============================================================
echo ""
info "Запуск FastAPI backend на :8000 ..."
PYTHONPATH="$PROJECT_ROOT:$BOT_DIR" \
    python3 -m uvicorn webapp.backend.main:app \
    --reload --host 0.0.0.0 --port 8000 \
    --log-level info \
    > "$PROJECT_ROOT/.backend.log" 2>&1 &
BACKEND_PID=$!
sleep 1

if kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Backend запущен (PID: $BACKEND_PID)"
else
    err "Backend не запустился! Смотрите лог: $PROJECT_ROOT/.backend.log"
    cleanup
fi

# ============================================================
#  6. Запуск Vite frontend (порт 3000)
# ============================================================
info "Запуск Vite frontend на :3000 ..."
(cd "$FRONTEND_DIR" && npm run dev) > "$PROJECT_ROOT/.frontend.log" 2>&1 &
FRONTEND_PID=$!
sleep 2

if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Frontend запущен (PID: $FRONTEND_PID)"
else
    err "Frontend не запустился! Смотрите лог: $PROJECT_ROOT/.frontend.log"
    cleanup
fi

# ============================================================
#  7. Запуск Telegram Bot
# ============================================================
info "Запуск Telegram Bot..."
(cd "$BOT_DIR" && PYTHONPATH="$PROJECT_ROOT:$BOT_DIR" python3 Bot/main.py) \
    > "$PROJECT_ROOT/.bot.log" 2>&1 &
BOT_PID=$!
sleep 2

if kill -0 "$BOT_PID" 2>/dev/null; then
    log "Telegram Bot запущен (PID: $BOT_PID)"
else
    err "Bot не запустился! Смотрите лог: $PROJECT_ROOT/.bot.log"
    cleanup
fi

# ============================================================
#  Готово — вывод статуса
# ============================================================
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   Все сервисы запущены!                          ${NC}"
echo -e "${GREEN}══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Backend API:${NC}    http://localhost:8000/api/health"
echo -e "  ${CYAN}Frontend:${NC}       http://localhost:3000"
if [ -n "$WEBAPP_URL" ]; then
echo -e "  ${CYAN}Tunnel (Web):${NC}   $WEBAPP_URL"
fi
echo -e "  ${CYAN}Telegram Bot:${NC}   активен (polling)"
echo ""
echo -e "  ${YELLOW}Логи:${NC}"
echo -e "    Backend:   tail -f $PROJECT_ROOT/.backend.log"
echo -e "    Frontend:  tail -f $PROJECT_ROOT/.frontend.log"
echo -e "    Bot:       tail -f $PROJECT_ROOT/.bot.log"
if [ -n "$TUNNEL_PID" ]; then
echo -e "    Tunnel:    tail -f $TUNNEL_LOG"
fi
echo ""
echo -e "  Нажмите ${RED}Ctrl+C${NC} для остановки всех сервисов."
echo ""

# Ожидаем завершения любого процесса
wait
