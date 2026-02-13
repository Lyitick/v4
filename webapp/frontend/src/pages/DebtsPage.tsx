import { useEffect, useState } from "react";
import { debtsApi } from "../api/client";
import type { Debt, DebtSummary } from "../api/client";

type TabType = "owed" | "owe" | "settled";

export function DebtsPage() {
  const [debts, setDebts] = useState<Debt[]>([]);
  const [settledDebts, setSettledDebts] = useState<Debt[]>([]);
  const [summary, setSummary] = useState<DebtSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabType>("owed");
  const [showForm, setShowForm] = useState(false);

  const [person, setPerson] = useState("");
  const [amount, setAmount] = useState("");
  const [direction, setDirection] = useState<"owe" | "owed">("owed");
  const [description, setDescription] = useState("");

  const tg = window.Telegram?.WebApp;

  const load = () => {
    setLoading(true);
    Promise.all([
      debtsApi.list(false),
      debtsApi.list(true),
      debtsApi.summary(),
    ])
      .then(([active, settled, sum]) => {
        setDebts(active);
        setSettledDebts(settled);
        setSummary(sum);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async () => {
    if (!person.trim() || !amount) return;
    try {
      await debtsApi.create({
        person: person.trim(),
        amount: parseFloat(amount),
        direction,
        description: description.trim(),
      });
      tg?.HapticFeedback?.impactOccurred("medium");
      setPerson("");
      setAmount("");
      setDescription("");
      setShowForm(false);
      load();
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    }
  };

  const handleSettle = async (id: number) => {
    try {
      await debtsApi.settle(id);
      tg?.HapticFeedback?.impactOccurred("light");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await debtsApi.remove(id);
      tg?.HapticFeedback?.impactOccurred("light");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    const months = [
      "янв", "фев", "мар", "апр", "май", "июн",
      "июл", "авг", "сен", "окт", "ноя", "дек",
    ];
    return `${d.getDate()} ${months[d.getMonth()]}`;
  };

  const filtered =
    tab === "settled"
      ? settledDebts
      : debts.filter((d) => d.direction === tab);

  const owedCount = debts.filter((d) => d.direction === "owed").length;
  const oweCount = debts.filter((d) => d.direction === "owe").length;

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="section-header">
        <h2>Долги</h2>
        <button
          className="btn--add"
          onClick={() => {
            setShowForm(!showForm);
            tg?.HapticFeedback?.selectionChanged();
          }}
        >
          +
        </button>
      </div>

      {/* Summary cards */}
      {summary && (summary.owed_to_me > 0 || summary.i_owe > 0) && (
        <div className="debt-summary">
          <div className="debt-summary__card debt-summary__card--positive">
            <span className="debt-summary__label">Мне должны</span>
            <span className="debt-summary__amount">
              {summary.owed_to_me.toLocaleString("ru-RU")} &#8381;
            </span>
          </div>
          <div className="debt-summary__card debt-summary__card--negative">
            <span className="debt-summary__label">Я должен</span>
            <span className="debt-summary__amount">
              {summary.i_owe.toLocaleString("ru-RU")} &#8381;
            </span>
          </div>
          <div
            className={`debt-summary__card ${
              summary.net_balance >= 0
                ? "debt-summary__card--positive"
                : "debt-summary__card--negative"
            }`}
          >
            <span className="debt-summary__label">Баланс</span>
            <span className="debt-summary__amount">
              {summary.net_balance >= 0 ? "+" : ""}
              {summary.net_balance.toLocaleString("ru-RU")} &#8381;
            </span>
          </div>
        </div>
      )}

      {/* Tab bar */}
      <div className="debt-tabs">
        <button
          className={`debt-tab ${tab === "owed" ? "active" : ""}`}
          onClick={() => setTab("owed")}
        >
          Мне должны {owedCount > 0 && `(${owedCount})`}
        </button>
        <button
          className={`debt-tab ${tab === "owe" ? "active" : ""}`}
          onClick={() => setTab("owe")}
        >
          Я должен {oweCount > 0 && `(${oweCount})`}
        </button>
        <button
          className={`debt-tab ${tab === "settled" ? "active" : ""}`}
          onClick={() => setTab("settled")}
        >
          Погашенные
        </button>
      </div>

      {showForm && (
        <div className="expense-form">
          <input
            className="input"
            placeholder="Кто"
            value={person}
            onChange={(e) => setPerson(e.target.value)}
            autoFocus
          />
          <input
            className="input"
            type="number"
            placeholder="Сумма"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            min="1"
          />
          <div className="debt-direction-toggle">
            <button
              className={`debt-direction-btn ${direction === "owed" ? "active" : ""}`}
              onClick={() => setDirection("owed")}
            >
              Мне должны
            </button>
            <button
              className={`debt-direction-btn ${direction === "owe" ? "active" : ""}`}
              onClick={() => setDirection("owe")}
            >
              Я должен
            </button>
          </div>
          <input
            className="input"
            placeholder="Описание (необязательно)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <button className="btn btn--primary btn--full" onClick={handleAdd}>
            Добавить
          </button>
        </div>
      )}

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : filtered.length === 0 ? (
        <p className="empty-state">
          {tab === "settled"
            ? "Нет погашенных долгов."
            : tab === "owed"
            ? "Никто не должен вам. Отлично!"
            : "Вы никому не должны. Отлично!"}
        </p>
      ) : (
        <div className="recurring-list">
          {filtered.map((debt) => (
            <div key={debt.id} className="recurring-card">
              <div className="recurring-card__info">
                <span className="recurring-card__title">
                  {debt.person}
                  {debt.description && (
                    <span className="expense-note"> — {debt.description}</span>
                  )}
                </span>
                <span className="recurring-card__meta">
                  {formatDate(debt.created_at)}
                  {debt.is_settled && debt.settled_at && (
                    <> &rarr; {formatDate(debt.settled_at)}</>
                  )}
                </span>
              </div>
              <div className="recurring-card__right">
                <span
                  className="recurring-card__amount"
                  style={{
                    color: debt.direction === "owed" ? "#43a047" : "#e53935",
                  }}
                >
                  {debt.direction === "owed" ? "+" : "-"}
                  {debt.amount.toLocaleString("ru-RU")} &#8381;
                </span>
                {!debt.is_settled && (
                  <button
                    className="btn btn--primary btn--sm"
                    onClick={() => handleSettle(debt.id)}
                    title="Погасить"
                  >
                    &#10003;
                  </button>
                )}
                <button
                  className="btn btn--danger btn--sm"
                  onClick={() => handleDelete(debt.id)}
                >
                  &#10005;
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
