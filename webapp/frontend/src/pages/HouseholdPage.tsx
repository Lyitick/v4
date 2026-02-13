import { useEffect, useState, useCallback } from "react";
import { householdApi } from "../api/client";
import type { PaymentStatus } from "../api/client";

export function HouseholdPage() {
  const [payments, setPayments] = useState<PaymentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tg = window.Telegram?.WebApp;

  const loadStatus = useCallback(() => {
    setLoading(true);
    householdApi
      .getStatus()
      .then(setPayments)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleToggle = async (code: string, currentlyPaid: boolean) => {
    try {
      await householdApi.answer(code, currentlyPaid ? "no" : "yes");
      tg?.HapticFeedback?.impactOccurred("light");
      loadStatus();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const paidCount = payments.filter((p) => p.is_paid).length;
  const totalAmount = payments.reduce((sum, p) => sum + p.amount, 0);
  const paidAmount = payments
    .filter((p) => p.is_paid)
    .reduce((sum, p) => sum + p.amount, 0);

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <h2>Бытовые платежи</h2>

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : payments.length === 0 ? (
        <p className="empty-state">Нет бытовых платежей</p>
      ) : (
        <>
          <div className="household-summary">
            <span>
              Оплачено: {paidCount}/{payments.length}
            </span>
            <span>
              {paidAmount.toLocaleString("ru-RU")} / {totalAmount.toLocaleString("ru-RU")} ₽
            </span>
          </div>

          <div className="household-progress">
            <div
              className="household-progress__bar"
              style={{
                width: `${totalAmount > 0 ? (paidAmount / totalAmount) * 100 : 0}%`,
              }}
            />
          </div>

          <div className="household-list">
            {payments.map((p) => (
              <div
                key={p.code}
                className={`household-item ${p.is_paid ? "paid" : ""}`}
                onClick={() => handleToggle(p.code, p.is_paid)}
              >
                <div className="household-item__check">
                  {p.is_paid ? "✓" : "○"}
                </div>
                <div className="household-item__info">
                  <span className="household-item__text">{p.text}</span>
                  <span className="household-item__amount">
                    {p.amount.toLocaleString("ru-RU")} ₽
                  </span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
