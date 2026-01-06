# Audit Report (finance_bot v4)

## Found issues
- UI cleanup tracked multiple message lists and could retain welcome in tracked ids.
- Welcome message id was not persisted and could be duplicated after state loss.
- Direct Telegram edit/delete calls could fail on network errors or invalid reply keyboards.
- Income category titles contained bank/service suffixes and older rows were not sanitized.
- Database access used direct `FinanceDatabase()` construction across handlers.

## Fixes applied
- Unified UI tracking to `ui_tracked_message_ids` and excluded welcome from tracked ids after cleanup.
- Added persistent welcome id storage in `ui_pins` table and reused it on startup.
- Implemented safe Telegram operations with retries and guarded edits against reply keyboards.
- Added income title sanitizer and migration to update existing stored titles.
- Introduced `get_db()` for a shared database instance and updated handlers.

## Backlog / Follow-up
- Expand safe Telegram wrapper adoption in remaining handlers and services.
- Add safe reply markup editing helper if required by additional flows.
