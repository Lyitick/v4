"""Google Sheets synchronization utility.

Uses a service account to write financial data to a user's Google Sheet.
Requires:
  - gspread + google-auth packages
  - GOOGLE_SHEETS_CREDENTIALS env var pointing to service account JSON file
  - User must share the spreadsheet with the service account email
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

LOGGER = logging.getLogger(__name__)


def _get_client():
    """Create an authorized gspread client from service account credentials."""
    import gspread
    from google.oauth2.service_account import Credentials

    from Bot.config.settings import get_settings

    creds_path = get_settings().google_sheets_credentials
    if not creds_path:
        raise RuntimeError("GOOGLE_SHEETS_CREDENTIALS не настроен")

    creds_file = Path(creds_path)
    if not creds_file.exists():
        raise RuntimeError(f"Файл credentials не найден: {creds_path}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(str(creds_file), scopes=scopes)
    return gspread.authorize(creds)


def extract_spreadsheet_id(url_or_id: str) -> str:
    """Extract spreadsheet ID from a URL or return as-is if already an ID."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url_or_id)
    if match:
        return match.group(1)
    # Assume it's already an ID
    return url_or_id.strip()


def get_service_account_email() -> str | None:
    """Return the service account email for sharing instructions."""
    import json

    from Bot.config.settings import get_settings

    creds_path = get_settings().google_sheets_credentials
    if not creds_path:
        return None
    try:
        data = json.loads(Path(creds_path).read_text())
        return data.get("client_email")
    except Exception:
        return None


def sync_to_sheets(user_id: int, spreadsheet_id: str) -> dict:
    """Sync all financial data to the given Google Spreadsheet.

    Creates/updates worksheets:
      - Накопления (Savings)
      - Расходы (Expenses for current month)
      - Отчёт (Monthly report)
      - Повторяющиеся (Recurring)
      - Бытовые платежи (Household)
      - Долги (Debts)

    Returns: {"ok": True, "sheets_updated": int} or raises on error.
    """
    from Bot.database.get_db import get_db

    gc = _get_client()
    sh = gc.open_by_key(spreadsheet_id)
    db = get_db()

    now = datetime.utcnow()
    year, month = now.year, now.month
    month_prefix = f"{year:04d}-{month:02d}"
    sheets_updated = 0

    def _get_or_create_worksheet(title: str, rows: int = 100, cols: int = 10):
        try:
            ws = sh.worksheet(title)
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title=title, rows=rows, cols=cols)
        return ws

    # ── 1. Savings ────────────────────────────────────────
    savings = db.get_all_savings_list(user_id)
    ws = _get_or_create_worksheet("Накопления")
    data = [["Категория", "Текущие", "Цель", "Назначение", "Прогресс %"]]
    for s in savings:
        current = float(s.get("current", 0))
        goal = float(s.get("goal", 0))
        pct = round(current / goal * 100, 1) if goal > 0 else 0
        data.append([s["category"], current, goal, s.get("purpose", ""), pct])
    if len(data) > 1:
        ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    # ── 2. Expenses ───────────────────────────────────────
    expenses = db.list_expenses(user_id, year, month)
    ws = _get_or_create_worksheet("Расходы")
    data = [["Дата", "Категория", "Сумма", "Заметка"]]
    for e in expenses:
        data.append([e.get("created_at", ""), e.get("category", ""), e.get("amount", 0), e.get("note", "")])
    if len(data) > 1:
        ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    # ── 3. Monthly Report ─────────────────────────────────
    report = db.get_monthly_report_data(user_id, year, month)
    ws = _get_or_create_worksheet("Отчёт")
    data = [
        ["Показатель", "Сумма"],
        ["Месяц", report["month"]],
        ["Общий доход", report["total_income"]],
        ["Общий расход", report["total_expense"]],
        ["Баланс", round(report["total_income"] - report["total_expense"], 2)],
        ["Бытовые оплачено", report["household_paid"]],
        ["Бытовые всего", report["household_total"]],
        [],
        ["--- Доходы по категориям ---", ""],
    ]
    for item in report["income_by_category"]:
        data.append([item["category"], item["amount"]])
    data.append([])
    data.append(["--- Расходы по категориям ---", ""])
    for item in report["expense_by_category"]:
        data.append([item["category"], item["amount"]])
    ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    # ── 4. Recurring ──────────────────────────────────────
    recurring = db.list_recurring_payments(user_id)
    ws = _get_or_create_worksheet("Повторяющиеся")
    data = [["Название", "Сумма", "Частота", "День месяца", "Следующая дата"]]
    for r in recurring:
        data.append([r["title"], r["amount"], r["frequency"], r["day_of_month"], r.get("next_due_date", "")])
    if len(data) > 1:
        ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    # ── 5. Household ──────────────────────────────────────
    items = db.list_active_household_items(user_id)
    ws = _get_or_create_worksheet("Бытовые платежи")
    data = [["Платёж", "Сумма", "Оплачено"]]
    cursor = db.connection.cursor()
    for item in items:
        try:
            cursor.execute(
                f'SELECT is_paid FROM "{db.tables.household_payments}" WHERE user_id = ? AND month = ? AND question_code = ?',
                (user_id, month_prefix, item["code"]),
            )
            row = cursor.fetchone()
            is_paid = bool(row and int(row["is_paid"])) if row else False
        except Exception:
            is_paid = False
        data.append([item["text"], item["amount"], "Да" if is_paid else "Нет"])
    if len(data) > 1:
        ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    # ── 6. Debts ──────────────────────────────────────────
    active_debts = db.list_debts(user_id, settled=False)
    settled_debts = db.list_debts(user_id, settled=True)
    ws = _get_or_create_worksheet("Долги")
    data = [["Человек", "Сумма", "Направление", "Описание", "Статус", "Дата"]]
    for d in active_debts:
        direction_text = "Мне должны" if d["direction"] == "owed" else "Я должен"
        data.append([d["person"], d["amount"], direction_text, d.get("description", ""), "Активный", d["created_at"]])
    for d in settled_debts:
        direction_text = "Мне должны" if d["direction"] == "owed" else "Я должен"
        data.append([d["person"], d["amount"], direction_text, d.get("description", ""), "Погашен", d["created_at"]])
    if len(data) > 1:
        ws.update(data, value_input_option="RAW")
    sheets_updated += 1

    return {"ok": True, "sheets_updated": sheets_updated}
