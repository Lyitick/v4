# Plan: Telegram Bot -> Telegram Mini App Migration

## Architecture Overview

```
finance_bot/          (existing, keep for notifications)
webapp/
├── backend/          (FastAPI API server)
│   ├── main.py       (FastAPI app + Telegram initData auth)
│   ├── auth.py       (Telegram WebApp auth validation)
│   ├── routers/
│   │   └── wishlist.py   (Phase 1: wishlist REST API)
│   └── database/     (symlink/import from existing Bot/database)
└── frontend/         (React + Vite)
    ├── src/
    │   ├── App.tsx
    │   ├── api/          (API client)
    │   ├── pages/
    │   │   └── WishlistPage.tsx
    │   ├── components/
    │   │   ├── WishCard.tsx
    │   │   ├── AddWishForm.tsx
    │   │   └── CategoryTabs.tsx
    │   └── hooks/
    │       └── useTelegram.ts
    ├── index.html
    ├── vite.config.ts
    └── package.json
```

## Phase 1: Wishlist Module (this PR)

### Step 1: FastAPI Backend Setup
- Create `webapp/backend/main.py` — FastAPI app with CORS
- Create `webapp/backend/auth.py` — validate Telegram `initData` (HMAC-SHA256)
- Reuse existing `Bot/database/crud.py` and `get_db.py` directly via Python imports
- Create `webapp/backend/routers/wishlist.py` with endpoints:
  - `GET /api/wishlist/categories` — list active categories
  - `GET /api/wishlist/wishes?category_id=X` — list wishes (active + purchased)
  - `POST /api/wishlist/wishes` — add wish (name, price, url?, category)
  - `POST /api/wishlist/wishes/{id}/purchase` — mark wish as purchased
  - `DELETE /api/wishlist/wishes/{id}` — delete wish
  - `POST /api/wishlist/wishes/{id}/defer` — defer wish
  - `GET /api/wishlist/purchases` — list purchases

### Step 2: React Frontend Setup
- Initialize React + Vite + TypeScript project in `webapp/frontend/`
- Install `@telegram-apps/sdk` for Telegram Web App integration
- Create `useTelegram` hook for WebApp init + theme + initData
- Create API client that sends `initData` in Authorization header
- Build Wishlist UI:
  - Category tabs at top (horizontal scroll)
  - Wish cards with name, price, url, saved_amount, deferred status
  - Add wish form (modal/sheet)
  - Purchase confirmation
  - Swipe to delete/defer
- Style using Telegram theme variables (CSS vars from WebApp SDK)

### Step 3: Bot Integration
- Add `/start` command handler that opens Mini App via `WebAppInfo` button
- Keep existing bot handlers working in parallel (hybrid mode)
- Keep byt_scheduler for push notifications through bot

### Step 4: Wiring & Config
- Add `WEBAPP_URL` to `.env` for Mini App URL
- Create `webapp/backend/requirements.txt` (fastapi, uvicorn, etc.)
- Create run scripts for development

## Implementation Order (files to create/modify)

1. `webapp/backend/auth.py` — Telegram auth
2. `webapp/backend/main.py` — FastAPI app
3. `webapp/backend/routers/wishlist.py` — wishlist API
4. `webapp/backend/requirements.txt`
5. `webapp/frontend/` — React project init (vite, package.json, tsconfig)
6. `webapp/frontend/src/hooks/useTelegram.ts`
7. `webapp/frontend/src/api/client.ts`
8. `webapp/frontend/src/pages/WishlistPage.tsx`
9. `webapp/frontend/src/components/` — WishCard, AddWishForm, CategoryTabs
10. `webapp/frontend/src/App.tsx` + routing
11. `finance_bot/Bot/handlers/start.py` — add Mini App button
12. Update `.env` example

## Future Phases (not in this PR)
- Phase 2: Income distribution page
- Phase 3: Household payments page
- Phase 4: Savings & settings pages
- Phase 5: Remove bot handlers, full Mini App
