import { useEffect, useState } from "react";
import { savingsApi } from "../api/client";
import type { Saving } from "../api/client";

export function SavingsPage() {
  const [savings, setSavings] = useState<Saving[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    savingsApi
      .getAll()
      .then(setSavings)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const totalCurrent = savings.reduce((sum, s) => sum + s.current, 0);

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <h2>Накопления</h2>

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : savings.length === 0 ? (
        <p className="empty-state">Пока нет накоплений</p>
      ) : (
        <>
          <div className="savings-total">
            Всего: {totalCurrent.toLocaleString("ru-RU")} ₽
          </div>

          <div className="savings-list">
            {savings.map((s) => {
              const progress =
                s.goal > 0 ? Math.min((s.current / s.goal) * 100, 100) : 0;
              return (
                <div key={s.category} className="saving-card">
                  <div className="saving-card__header">
                    <span className="saving-card__category">{s.category}</span>
                    <span className="saving-card__amount">
                      {s.current.toLocaleString("ru-RU")} ₽
                    </span>
                  </div>

                  {s.goal > 0 && (
                    <>
                      <div className="saving-card__goal">
                        Цель: {s.goal.toLocaleString("ru-RU")} ₽
                        {s.purpose && ` — ${s.purpose}`}
                      </div>
                      <div className="saving-card__progress">
                        <div
                          className="saving-card__progress-bar"
                          style={{ width: `${progress}%` }}
                        />
                      </div>
                      <div className="saving-card__percent">{progress.toFixed(0)}%</div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
