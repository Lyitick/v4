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

// ── Expense Types ────────────────────────────────────

export interface Expense {
  id: number;
  amount: number;
  category: string;
  note: string;
  created_at: string;
}

export interface ExpenseCategory {
  id: number;
  code: string;
  title: string;
  budget_limit: number;
}

export interface BudgetStatus {
  category_id: number;
  category: string;
  budget_limit: number;
  spent: number;
  remaining: number;
  percent_used: number;
}

// ── Wishlist Types ────────────────────────────────────

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

// ── Income Types ──────────────────────────────────────

export interface IncomeCategory {
  id: number;
  code: string;
  title: string;
  percent: number;
  position: number;
}

export interface AllocationItem {
  code: string;
  title: string;
  percent: number;
  amount: number;
}

export interface CalculateResult {
  amount: number;
  allocations: AllocationItem[];
  total_percent: number;
}

// ── Household Types ───────────────────────────────────

export interface HouseholdItem {
  code: string;
  text: string;
  amount: number;
  position: number;
}

export interface PaymentStatus {
  code: string;
  text: string;
  amount: number;
  is_paid: boolean;
}

// ── Debt Types ────────────────────────────────────────

export interface Debt {
  id: number;
  person: string;
  amount: number;
  direction: "owe" | "owed";
  description: string;
  is_settled: boolean;
  settled_at?: string;
  created_at: string;
}

export interface DebtSummary {
  owed_to_me: number;
  i_owe: number;
  net_balance: number;
}

// ── Savings Types ─────────────────────────────────────

export interface Saving {
  category: string;
  current: number;
  goal: number;
  purpose: string;
}

// ── Settings Types ────────────────────────────────────

export interface UserSettings {
  timezone: string;
  purchased_keep_days: number;
  byt_reminders_enabled: boolean;
  byt_defer_enabled: boolean;
  byt_defer_max_days: number;
  household_debit_category?: string;
  wishlist_debit_category_id?: string;
}

// ── Expenses API ─────────────────────────────────────

export const expensesApi = {
  getCategories: () => request<ExpenseCategory[]>("/expenses/categories"),

  list: (year?: number, month?: number) => {
    const params = new URLSearchParams();
    if (year) params.set("year", String(year));
    if (month) params.set("month", String(month));
    const qs = params.toString();
    return request<Expense[]>(`/expenses/${qs ? `?${qs}` : ""}`);
  },

  create: (data: { amount: number; category: string; note?: string }) =>
    request<Expense>("/expenses/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (id: number) =>
    request<{ ok: boolean }>(`/expenses/${id}`, {
      method: "DELETE",
    }),

  setBudgetLimit: (categoryId: number, limit: number) =>
    request<{ ok: boolean }>("/expenses/budget-limit", {
      method: "POST",
      body: JSON.stringify({ category_id: categoryId, limit }),
    }),

  getBudgetStatus: (year?: number, month?: number) => {
    const params = new URLSearchParams();
    if (year) params.set("year", String(year));
    if (month) params.set("month", String(month));
    const qs = params.toString();
    return request<BudgetStatus[]>(`/expenses/budget-status${qs ? `?${qs}` : ""}`);
  },
};

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

// ── Income API ────────────────────────────────────────

export const incomeApi = {
  getCategories: () => request<IncomeCategory[]>("/income/categories"),

  calculate: (amount: number) =>
    request<CalculateResult>("/income/calculate", {
      method: "POST",
      body: JSON.stringify({ amount }),
    }),

  confirm: (amount: number) =>
    request<{ ok: boolean; applied: AllocationItem[] }>("/income/confirm", {
      method: "POST",
      body: JSON.stringify({ amount }),
    }),
};

// ── Household API ─────────────────────────────────────

export const householdApi = {
  getItems: () => request<HouseholdItem[]>("/household/items"),

  getStatus: (month?: string) => {
    const params = month ? `?month=${encodeURIComponent(month)}` : "";
    return request<PaymentStatus[]>(`/household/status${params}`);
  },

  answer: (questionCode: string, answer: "yes" | "no", month?: string) => {
    const params = month ? `?month=${encodeURIComponent(month)}` : "";
    return request<{ ok: boolean; changed: boolean }>(`/household/answer${params}`, {
      method: "POST",
      body: JSON.stringify({ question_code: questionCode, answer }),
    });
  },

  reset: (month?: string) => {
    const params = month ? `?month=${encodeURIComponent(month)}` : "";
    return request<{ ok: boolean }>(`/household/reset${params}`, {
      method: "POST",
    });
  },
};

// ── Savings API ───────────────────────────────────────

export const savingsApi = {
  getAll: () => request<Saving[]>("/savings/"),

  setGoal: (category: string, goal: number, purpose: string) =>
    request<{ ok: boolean }>("/savings/goal", {
      method: "POST",
      body: JSON.stringify({ category, goal, purpose }),
    }),

  resetGoals: () =>
    request<{ ok: boolean }>("/savings/reset-goals", {
      method: "POST",
    }),
};

// ── Debts API ────────────────────────────────────────

export const debtsApi = {
  list: (settled = false) =>
    request<Debt[]>(`/debts/?settled=${settled}`),

  create: (data: { person: string; amount: number; direction: "owe" | "owed"; description?: string }) =>
    request<Debt>("/debts/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  settle: (debtId: number) =>
    request<{ ok: boolean }>(`/debts/${debtId}/settle`, {
      method: "POST",
    }),

  remove: (debtId: number) =>
    request<{ ok: boolean }>(`/debts/${debtId}`, {
      method: "DELETE",
    }),

  summary: () => request<DebtSummary>("/debts/summary"),
};

// ── Recurring Types ──────────────────────────────────

export interface RecurringPayment {
  id: number;
  title: string;
  amount: number;
  category?: string;
  frequency: string;
  day_of_month: number;
  next_due_date?: string;
}

// ── Report Types ────────────────────────────────────

export interface CategoryAmount {
  category: string;
  amount: number;
}

export interface MonthlyReport {
  month: string;
  total_income: number;
  total_expense: number;
  balance: number;
  income_by_category: CategoryAmount[];
  expense_by_category: CategoryAmount[];
  household_paid: number;
  household_total: number;
}

// ── Settings API ──────────────────────────────────────

export const settingsApi = {
  get: () => request<UserSettings>("/settings/"),

  updateTimezone: (timezone: string) =>
    request<{ ok: boolean }>("/settings/timezone", {
      method: "POST",
      body: JSON.stringify({ timezone }),
    }),

  updateKeepDays: (days: number) =>
    request<{ ok: boolean }>("/settings/keep-days", {
      method: "POST",
      body: JSON.stringify({ days }),
    }),

  toggleBytReminders: () =>
    request<{ ok: boolean; enabled: boolean }>("/settings/byt-reminders/toggle", {
      method: "POST",
    }),
};

// ── Recurring API ────────────────────────────────────

export const recurringApi = {
  list: () => request<RecurringPayment[]>("/recurring/"),

  create: (data: { title: string; amount: number; category?: string; frequency?: string; day_of_month: number }) =>
    request<RecurringPayment>("/recurring/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  remove: (id: number) =>
    request<{ ok: boolean }>(`/recurring/${id}`, {
      method: "DELETE",
    }),
};

// ── Reports API ──────────────────────────────────────

export const reportsApi = {
  monthly: (year?: number, month?: number) => {
    const params = new URLSearchParams();
    if (year) params.set("year", String(year));
    if (month) params.set("month", String(month));
    const qs = params.toString();
    return request<MonthlyReport>(`/reports/monthly${qs ? `?${qs}` : ""}`);
  },

  getReportDay: () => request<{ day: number }>("/reports/report-day"),

  setReportDay: (day: number) =>
    request<{ ok: boolean; day: number }>("/reports/report-day", {
      method: "POST",
      body: JSON.stringify({ day }),
    }),
};

// ── Export API ────────────────────────────────────────

export const exportApi = {
  downloadExcel: async (year?: number, month?: number) => {
    const params = new URLSearchParams();
    if (year) params.set("year", String(year));
    if (month) params.set("month", String(month));
    const qs = params.toString();
    const initData = getInitData();
    const res = await fetch(`${API_BASE}/export/excel${qs ? `?${qs}` : ""}`, {
      headers: { Authorization: `tma ${initData}` },
    });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `finance_report.xlsx`;
    a.click();
    URL.revokeObjectURL(url);
  },
};
