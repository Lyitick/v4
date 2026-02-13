import { useState } from "react";
import { incomeApi } from "../api/client";
import type { AllocationItem } from "../api/client";

export function IncomePage() {
  const [amount, setAmount] = useState("");
  const [allocations, setAllocations] = useState<AllocationItem[]>([]);
  const [totalPercent, setTotalPercent] = useState(0);
  const [calculated, setCalculated] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tg = window.Telegram?.WebApp;

  const handleCalculate = async () => {
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed <= 0) return;

    setLoading(true);
    setError(null);
    try {
      const result = await incomeApi.calculate(parsed);
      setAllocations(result.allocations);
      setTotalPercent(result.total_percent);
      setCalculated(true);
      setConfirmed(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    const parsed = parseFloat(amount);
    if (isNaN(parsed) || parsed <= 0) return;

    setLoading(true);
    try {
      await incomeApi.confirm(parsed);
      setConfirmed(true);
      tg?.HapticFeedback?.notificationOccurred("success");
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setAmount("");
    setAllocations([]);
    setCalculated(false);
    setConfirmed(false);
  };

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <h2>Рассчитать доход</h2>

      {!confirmed ? (
        <>
          <div className="income-input-group">
            <input
              className="input income-input"
              type="number"
              placeholder="Сумма дохода (₽)"
              value={amount}
              onChange={(e) => {
                setAmount(e.target.value);
                setCalculated(false);
              }}
              min="1"
            />
            <button
              className="btn btn--primary"
              onClick={handleCalculate}
              disabled={loading || !amount}
            >
              {loading ? "..." : "Рассчитать"}
            </button>
          </div>

          {calculated && allocations.length > 0 && (
            <div className="allocations">
              <div className="allocations__header">
                <span>Распределение</span>
                <span className={totalPercent === 100 ? "percent-ok" : "percent-warn"}>
                  {totalPercent}%
                </span>
              </div>

              {allocations.map((a) => (
                <div key={a.code} className="allocation-row">
                  <div className="allocation-row__info">
                    <span className="allocation-row__title">{a.title}</span>
                    <span className="allocation-row__percent">{a.percent}%</span>
                  </div>
                  <span className="allocation-row__amount">
                    {a.amount.toLocaleString("ru-RU")} ₽
                  </span>
                </div>
              ))}

              <button
                className="btn btn--primary btn--full"
                onClick={handleConfirm}
                disabled={loading}
              >
                Подтвердить
              </button>
            </div>
          )}

          {calculated && allocations.length === 0 && (
            <p className="empty-state">
              Нет категорий дохода. Настройте их в разделе «Настройки».
            </p>
          )}
        </>
      ) : (
        <div className="success-block">
          <div className="success-icon">&#10003;</div>
          <p>Доход {parseFloat(amount).toLocaleString("ru-RU")} ₽ распределён!</p>
          <div className="allocations">
            {allocations.map((a) => (
              <div key={a.code} className="allocation-row">
                <span className="allocation-row__title">{a.title}</span>
                <span className="allocation-row__amount">
                  +{a.amount.toLocaleString("ru-RU")} ₽
                </span>
              </div>
            ))}
          </div>
          <button className="btn btn--secondary btn--full" onClick={handleReset}>
            Новый расчёт
          </button>
        </div>
      )}
    </div>
  );
}
