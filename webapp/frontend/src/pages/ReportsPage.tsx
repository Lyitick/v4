import { useEffect, useState } from "react";
import { reportsApi, exportApi } from "../api/client";
import type { MonthlyReport } from "../api/client";

const MONTH_NAMES = [
  "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

export function ReportsPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [reportDay, setReportDay] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const tg = window.Telegram?.WebApp;

  const load = () => {
    setLoading(true);
    Promise.all([
      reportsApi.monthly(year, month),
      reportsApi.getReportDay(),
    ])
      .then(([rep, dayRes]) => {
        setReport(rep);
        setReportDay(dayRes.day);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [year, month]);

  const handlePrevMonth = () => {
    tg?.HapticFeedback?.selectionChanged();
    if (month === 1) { setMonth(12); setYear(year - 1); }
    else setMonth(month - 1);
  };

  const handleNextMonth = () => {
    tg?.HapticFeedback?.selectionChanged();
    if (month === 12) { setMonth(1); setYear(year + 1); }
    else setMonth(month + 1);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportApi.downloadExcel(year, month);
      tg?.HapticFeedback?.notificationOccurred("success");
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setExporting(false);
    }
  };

  const handleSetReportDay = async () => {
    const input = prompt("День месяца для отчёта (1-28):", String(reportDay));
    if (!input) return;
    const d = parseInt(input);
    if (isNaN(d) || d < 1 || d > 28) return;
    try {
      await reportsApi.setReportDay(d);
      setReportDay(d);
      tg?.HapticFeedback?.impactOccurred("light");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const maxAmount = report
    ? Math.max(
        ...report.income_by_category.map((c) => c.amount),
        ...report.expense_by_category.map((c) => c.amount),
        1,
      )
    : 1;

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <div className="report-nav">
        <button className="btn btn--secondary" onClick={handlePrevMonth}>
          &larr;
        </button>
        <span className="report-nav__title">
          {MONTH_NAMES[month]} {year}
        </span>
        <button className="btn btn--secondary" onClick={handleNextMonth}>
          &rarr;
        </button>
      </div>

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : report ? (
        <>
          <div className="report-summary">
            <div className="report-summary__item report-summary--income">
              <span className="report-summary__label">Доход</span>
              <span className="report-summary__value">
                {report.total_income.toLocaleString("ru-RU")} ₽
              </span>
            </div>
            <div className="report-summary__item report-summary--expense">
              <span className="report-summary__label">Расход</span>
              <span className="report-summary__value">
                {report.total_expense.toLocaleString("ru-RU")} ₽
              </span>
            </div>
            <div className="report-summary__item report-summary--balance">
              <span className="report-summary__label">Баланс</span>
              <span className="report-summary__value">
                {report.balance >= 0 ? "+" : ""}
                {report.balance.toLocaleString("ru-RU")} ₽
              </span>
            </div>
          </div>

          {report.income_by_category.length > 0 && (
            <div className="report-section">
              <h3>Доходы</h3>
              {report.income_by_category.map((c) => (
                <div key={c.category} className="report-bar">
                  <div className="report-bar__label">
                    <span>{c.category}</span>
                    <span>{c.amount.toLocaleString("ru-RU")} ₽</span>
                  </div>
                  <div className="report-bar__track">
                    <div
                      className="report-bar__fill report-bar__fill--income"
                      style={{ width: `${(c.amount / maxAmount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {report.expense_by_category.length > 0 && (
            <div className="report-section">
              <h3>Расходы</h3>
              {report.expense_by_category.map((c) => (
                <div key={c.category} className="report-bar">
                  <div className="report-bar__label">
                    <span>{c.category}</span>
                    <span>{c.amount.toLocaleString("ru-RU")} ₽</span>
                  </div>
                  <div className="report-bar__track">
                    <div
                      className="report-bar__fill report-bar__fill--expense"
                      style={{ width: `${(c.amount / maxAmount) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {report.household_total > 0 && (
            <div className="report-section">
              <h3>Бытовые платежи</h3>
              <div className="household-summary">
                <span>Оплачено</span>
                <span>
                  {report.household_paid.toLocaleString("ru-RU")} /{" "}
                  {report.household_total.toLocaleString("ru-RU")} ₽
                </span>
              </div>
              <div className="household-progress">
                <div
                  className="household-progress__bar"
                  style={{
                    width: `${(report.household_paid / report.household_total) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}

          <div className="report-actions">
            <button
              className="btn btn--primary btn--full"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting ? "Экспорт..." : "Скачать Excel"}
            </button>
          </div>

          <div
            className="settings-item settings-item--toggle"
            onClick={handleSetReportDay}
          >
            <span className="settings-item__label">День отчёта</span>
            <span className="settings-item__value">{reportDay}-го числа</span>
          </div>
        </>
      ) : (
        <p className="empty-state">Нет данных за этот месяц</p>
      )}
    </div>
  );
}
