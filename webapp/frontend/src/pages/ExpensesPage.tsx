import { useEffect, useState } from "react";
import { expensesApi } from "../api/client";
import type { Expense, ExpenseCategory, BudgetStatus } from "../api/client";

export function ExpensesPage() {
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [categories, setCategories] = useState<ExpenseCategory[]>([]);
  const [budgetStatus, setBudgetStatus] = useState<BudgetStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("");
  const [note, setNote] = useState("");

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const tg = window.Telegram?.WebApp;

  const load = () => {
    setLoading(true);
    Promise.all([
      expensesApi.list(year, month),
      expensesApi.getCategories(),
      expensesApi.getBudgetStatus(year, month),
    ])
      .then(([exp, cats, budget]) => {
        setExpenses(exp);
        setCategories(cats);
        setBudgetStatus(budget);
        if (cats.length > 0 && !category) {
          setCategory(cats[0].title);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [year, month]);

  const handleAdd = async () => {
    if (!amount || !category) return;
    try {
      await expensesApi.create({
        amount: parseFloat(amount),
        category,
        note: note.trim(),
      });
      tg?.HapticFeedback?.impactOccurred("medium");
      setAmount("");
      setNote("");
      setShowForm(false);
      load();
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await expensesApi.remove(id);
      tg?.HapticFeedback?.impactOccurred("light");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSetLimit = async (cat: ExpenseCategory) => {
    const input = prompt(
      `Лимит для "${cat.title}" (0 = без лимита):`,
      String(cat.budget_limit || "")
    );
    if (input === null) return;
    const val = parseFloat(input);
    if (isNaN(val) || val < 0) return;
    try {
      await expensesApi.setBudgetLimit(cat.id, val);
      tg?.HapticFeedback?.impactOccurred("light");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const prevMonth = () => {
    if (month === 1) { setYear(year - 1); setMonth(12); }
    else setMonth(month - 1);
  };
  const nextMonth = () => {
    if (month === 12) { setYear(year + 1); setMonth(1); }
    else setMonth(month + 1);
  };

  const monthNames = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
  ];

  const totalExpenses = expenses.reduce((s, e) => s + e.amount, 0);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return `${d.getDate()} ${monthNames[d.getMonth()]?.slice(0, 3).toLowerCase()}`;
  };

  const getBudgetColor = (percentUsed: number) => {
    if (percentUsed >= 100) return "#e53935";
    if (percentUsed >= 80) return "#ff9800";
    return "#43a047";
  };

  // Group expenses by category for summary
  const byCategory = expenses.reduce<Record<string, number>>((acc, e) => {
    acc[e.category] = (acc[e.category] || 0) + e.amount;
    return acc;
  }, {});

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="section-header">
        <h2>Расходы</h2>
        <button
          className="btn--add"
          onClick={() => { setShowForm(!showForm); tg?.HapticFeedback?.selectionChanged(); }}
        >
          +
        </button>
      </div>

      {/* Month navigation */}
      <div className="report-nav">
        <button className="btn btn--secondary" onClick={prevMonth}>&larr;</button>
        <span className="report-nav__title">
          {monthNames[month - 1]} {year}
        </span>
        <button className="btn btn--secondary" onClick={nextMonth}>&rarr;</button>
      </div>

      {showForm && (
        <div className="expense-form">
          <input
            className="input"
            type="number"
            placeholder="Сумма"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            min="1"
            autoFocus
          />
          <div className="category-tabs">
            {categories.map((c) => (
              <button
                key={c.id}
                className={`category-tab ${category === c.title ? "active" : ""}`}
                onClick={() => setCategory(c.title)}
              >
                {c.title}
              </button>
            ))}
          </div>
          <input
            className="input"
            placeholder="Заметка (необязательно)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
          <button className="btn btn--primary btn--full" onClick={handleAdd}>
            Добавить расход
          </button>
        </div>
      )}

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : (
        <>
          {/* Budget limits section */}
          {budgetStatus.length > 0 && (
            <div className="budget-limits">
              {budgetStatus.map((b) => (
                <div key={b.category_id} className="budget-limit-card">
                  <div className="budget-limit-card__header">
                    <span className="budget-limit-card__title">{b.category}</span>
                    <span
                      className="budget-limit-card__values"
                      style={{ color: getBudgetColor(b.percent_used) }}
                    >
                      {b.spent.toLocaleString("ru-RU")} / {b.budget_limit.toLocaleString("ru-RU")} &#8381;
                    </span>
                  </div>
                  <div className="budget-limit-card__bar">
                    <div
                      className="budget-limit-card__fill"
                      style={{
                        width: `${Math.min(b.percent_used, 100)}%`,
                        background: getBudgetColor(b.percent_used),
                      }}
                    />
                  </div>
                  <span className="budget-limit-card__percent" style={{ color: getBudgetColor(b.percent_used) }}>
                    {b.percent_used}%
                    {b.percent_used >= 100 && " — лимит превышен!"}
                    {b.percent_used >= 80 && b.percent_used < 100 && " — почти на пределе"}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Set limits hint */}
          {budgetStatus.length === 0 && categories.length > 0 && expenses.length > 0 && (
            <div className="budget-limits-hint">
              Установите лимиты на категории, нажав на них ниже
            </div>
          )}

          {expenses.length === 0 ? (
            <p className="empty-state">
              Нет расходов за этот месяц. Нажмите + чтобы добавить.
            </p>
          ) : (
            <>
              {/* Total */}
              <div className="household-summary">
                <span>{expenses.length} записей</span>
                <span>{totalExpenses.toLocaleString("ru-RU")} &#8381;</span>
              </div>

              {/* Category summary with limit setting */}
              {Object.keys(byCategory).length > 0 && (
                <div className="expense-categories-summary">
                  {Object.entries(byCategory)
                    .sort(([, a], [, b]) => b - a)
                    .map(([cat, amt]) => {
                      const catObj = categories.find((c) => c.title === cat);
                      return (
                        <div
                          key={cat}
                          className="expense-cat-row expense-cat-row--clickable"
                          onClick={() => catObj && handleSetLimit(catObj)}
                        >
                          <span className="expense-cat-row__title">
                            {cat}
                            {catObj && catObj.budget_limit > 0 && (
                              <span className="expense-cat-row__limit">
                                {" "}(лимит: {catObj.budget_limit.toLocaleString("ru-RU")})
                              </span>
                            )}
                          </span>
                          <span className="expense-cat-row__amount">
                            {amt.toLocaleString("ru-RU")} &#8381;
                          </span>
                        </div>
                      );
                    })}
                </div>
              )}

              {/* Expenses list */}
              <div className="recurring-list">
                {expenses.map((item) => (
                  <div key={item.id} className="recurring-card">
                    <div className="recurring-card__info">
                      <span className="recurring-card__title">
                        {item.category}
                        {item.note && (
                          <span className="expense-note"> — {item.note}</span>
                        )}
                      </span>
                      <span className="recurring-card__meta">
                        {formatDate(item.created_at)}
                      </span>
                    </div>
                    <div className="recurring-card__right">
                      <span className="recurring-card__amount">
                        {item.amount.toLocaleString("ru-RU")} &#8381;
                      </span>
                      <button
                        className="btn btn--danger btn--sm"
                        onClick={() => handleDelete(item.id)}
                      >
                        &#10005;
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
