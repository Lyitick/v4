import { useEffect, useState } from "react";
import { recurringApi } from "../api/client";
import type { RecurringPayment } from "../api/client";

export function RecurringPage() {
  const [items, setItems] = useState<RecurringPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [day, setDay] = useState("1");

  const tg = window.Telegram?.WebApp;

  const load = () => {
    setLoading(true);
    recurringApi
      .list()
      .then(setItems)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  const handleAdd = async () => {
    if (!title.trim() || !amount) return;
    try {
      await recurringApi.create({
        title: title.trim(),
        amount: parseFloat(amount),
        day_of_month: parseInt(day) || 1,
      });
      tg?.HapticFeedback?.impactOccurred("medium");
      setTitle("");
      setAmount("");
      setDay("1");
      setShowForm(false);
      load();
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await recurringApi.remove(id);
      tg?.HapticFeedback?.impactOccurred("light");
      load();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const totalMonthly = items.reduce((s, i) => s + i.amount, 0);

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="section-header">
        <h2>Повторяющиеся</h2>
        <button className="btn--add" onClick={() => { setShowForm(!showForm); tg?.HapticFeedback?.selectionChanged(); }}>
          +
        </button>
      </div>

      {showForm && (
        <div className="recurring-form">
          <input
            className="input"
            placeholder="Название (аренда, подписка...)"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
          <div className="recurring-form__row">
            <input
              className="input"
              type="number"
              placeholder="Сумма"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              min="1"
            />
            <input
              className="input recurring-form__day"
              type="number"
              placeholder="День"
              value={day}
              onChange={(e) => setDay(e.target.value)}
              min="1"
              max="28"
            />
          </div>
          <button className="btn btn--primary btn--full" onClick={handleAdd}>
            Добавить
          </button>
        </div>
      )}

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : items.length === 0 ? (
        <p className="empty-state">
          Нет повторяющихся платежей. Добавьте зарплату, аренду, подписки.
        </p>
      ) : (
        <>
          <div className="household-summary">
            <span>{items.length} платежей</span>
            <span>{totalMonthly.toLocaleString("ru-RU")} ₽/мес</span>
          </div>

          <div className="recurring-list">
            {items.map((item) => (
              <div key={item.id} className="recurring-card">
                <div className="recurring-card__info">
                  <span className="recurring-card__title">{item.title}</span>
                  <span className="recurring-card__meta">
                    каждый {item.day_of_month}-го числа
                  </span>
                </div>
                <div className="recurring-card__right">
                  <span className="recurring-card__amount">
                    {item.amount.toLocaleString("ru-RU")} ₽
                  </span>
                  <button
                    className="btn btn--danger btn--sm"
                    onClick={() => handleDelete(item.id)}
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
