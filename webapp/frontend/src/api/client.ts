/**
 * API client for the Mini App backend.
 * Sends Telegram initData in Authorization header.
 */

const API_BASE = import.meta.env.VITE_API_URL || "/api";

function getInitData(): string {
  return window.Telegram?.WebApp?.initData ?? "";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const initData = getInitData();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `tma ${initData}`,
      ...options.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── Types ──────────────────────────────────────────────

export interface Category {
  id: number;
  title: string;
  position: number;
  purchased_mode?: string;
  purchased_days?: number;
}

export interface Wish {
  id: number;
  name: string;
  price: number;
  url?: string;
  category: string;
  is_purchased: boolean;
  saved_amount: number;
  purchased_at?: string;
  deferred_until?: string;
}

export interface Purchase {
  id: number;
  wish_name: string;
  price: number;
  category: string;
  purchased_at?: string;
}

// ── Wishlist API ───────────────────────────────────────

export const wishlistApi = {
  getCategories: () => request<Category[]>("/wishlist/categories"),

  getWishes: (category?: string) => {
    const params = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<Wish[]>(`/wishlist/wishes${params}`);
  },

  createWish: (data: { name: string; price: number; url?: string; category: string }) =>
    request<Wish>("/wishlist/wishes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  purchaseWish: (wishId: number) =>
    request<{ ok: boolean; message?: string; status?: string }>(
      `/wishlist/wishes/${wishId}/purchase`,
      { method: "POST" }
    ),

  deferWish: (wishId: number, deferredUntil: string) =>
    request<{ ok: boolean }>(
      `/wishlist/wishes/${wishId}/defer`,
      {
        method: "POST",
        body: JSON.stringify({ deferred_until: deferredUntil }),
      }
    ),

  deleteWish: (wishId: number) =>
    request<{ ok: boolean }>(`/wishlist/wishes/${wishId}`, {
      method: "DELETE",
    }),

  getPurchases: () => request<Purchase[]>("/wishlist/purchases"),
};
