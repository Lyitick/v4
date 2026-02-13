"""Google Sheets sync REST API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from Bot.database.get_db import get_db

from webapp.backend.dependencies import get_current_user

router = APIRouter()
LOGGER = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────

class ConnectSheetsRequest(BaseModel):
    spreadsheet_url: str = Field(..., min_length=1)


class SheetsStatusOut(BaseModel):
    connected: bool
    spreadsheet_id: str | None = None
    service_account_email: str | None = None


# ── Endpoints ─────────────────────────────────────────

@router.get("/status", response_model=SheetsStatusOut)
async def get_sheets_status(user: dict = Depends(get_current_user)):
    """Check if Google Sheets is connected."""
    from webapp.backend.utils.google_sheets import get_service_account_email

    db = get_db()
    sheets_id = db.get_google_sheets_id(user["id"])
    return SheetsStatusOut(
        connected=sheets_id is not None,
        spreadsheet_id=sheets_id,
        service_account_email=get_service_account_email(),
    )


@router.post("/connect")
async def connect_sheets(
    body: ConnectSheetsRequest,
    user: dict = Depends(get_current_user),
):
    """Connect a Google Spreadsheet by URL or ID."""
    from webapp.backend.utils.google_sheets import extract_spreadsheet_id

    spreadsheet_id = extract_spreadsheet_id(body.spreadsheet_url)
    db = get_db()
    db.set_google_sheets_id(user["id"], spreadsheet_id)
    return {"ok": True, "spreadsheet_id": spreadsheet_id}


@router.post("/disconnect")
async def disconnect_sheets(user: dict = Depends(get_current_user)):
    """Disconnect Google Sheets."""
    db = get_db()
    db.set_google_sheets_id(user["id"], None)
    return {"ok": True}


@router.post("/sync")
async def sync_sheets(user: dict = Depends(get_current_user)):
    """Sync current data to the connected Google Spreadsheet."""
    db = get_db()
    sheets_id = db.get_google_sheets_id(user["id"])
    if not sheets_id:
        return {"ok": False, "error": "Google Sheets не подключён"}

    try:
        from webapp.backend.utils.google_sheets import sync_to_sheets

        result = sync_to_sheets(user["id"], sheets_id)
        return result
    except Exception as exc:
        LOGGER.exception("Google Sheets sync failed for user %s", user["id"])
        return {"ok": False, "error": str(exc)}
