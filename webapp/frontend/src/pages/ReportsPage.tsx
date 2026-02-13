import { useEffect, useState } from "react";
import { reportsApi, exportApi } from "../api/client";
import type { MonthlyReport } from "../api/client";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  BarElement,
} from "chart.js";
import { Doughnut, Bar } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement);

const MONTH_NAMES = [
  "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
];

const CHART_COLORS = [
  "#3390ec", "#43a047", "#e53935", "#ff9800", "#9c27b0",
  "#00bcd4", "#795548", "#607d8b", "#e91e63", "#cddc39",
];

export function ReportsPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [prevReport, setPrevReport] = useState<MonthlyReport | null>(null);
  const [reportDay, setReportDay] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  const tg = window.Telegram?.WebApp;

  const getPrevYearMonth = () => {
    return month === 1 ? { y: year - 1, m: 12 } : { y: year, m: month - 1 };
  };

  const load = () => {
    setLoading(true);
    const prev = getPrevYearMonth();
    Promise.all([
      reportsApi.monthly(year, month),
      reportsApi.monthly(prev.y, prev.m),
      reportsApi.getReportDay(),
    ])
      .then(([rep, prevRep, dayRes]) => {
        setReport(rep);
        setPrevReport(prevRep);
        setReportDay(dayRes.day);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  const getDelta = (current: number, previous: number) => {
    if (previous === 0) return current > 0 ? 100 : 0;
    return Math.round(((current - previous) / previous) * 100);
  };

  const DeltaBadge = ({ current, previous, invertColor }: { current: number; previous: number; invertColor?: boolean }) => {
    const delta = getDelta(current, previous);
    if (delta === 0 && previous === 0 && current === 0) return null;
    const isUp = delta > 0;
    const color = invertColor
      ? (isUp ? "#e53935" : "#43a047")  // For expenses: up=bad(red), down=good(green)
      : (isUp ? "#43a047" : "#e53935"); // For income: up=good(green), down=bad(red)
    return (
      <span className="delta-badge" style={{ color }}>
        {isUp ? "\u2191" : "\u2193"}{Math.abs(delta)}%
      </span>
    );
  };

  const findPrevCategoryAmount = (category: string, items: { category: string; amount: number }[]) => {
    return items.find((i) => i.category === category)?.amount ?? 0;
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

  const tgText = getComputedStyle(document.documentElement)
    .getPropertyValue("--tg-theme-text-color").trim() || "#000000";
  const tgHint = getComputedStyle(document.documentElement)
    .getPropertyValue("--tg-theme-hint-color").trim() || "#999999";

  const doughnutOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "60%",
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: {
          color: tgText,
          padding: 12,
          font: { size: 12 },
        },
      },
    },
  };

  const buildDoughnutData = (items: { category: string; amount: number }[]) => ({
    labels: items.map((i) => i.category),
    datasets: [
      {
        data: items.map((i) => i.amount),
        backgroundColor: items.map((_, idx) => CHART_COLORS[idx % CHART_COLORS.length]),
        borderWidth: 0,
      },
    ],
  });

  const barData = report
    ? {
        labels: ["Доход", "Расход"],
        datasets: [
          {
            data: [report.total_income, report.total_expense],
            backgroundColor: ["#43a047", "#e53935"],
            borderRadius: 6,
          },
        ],
      }
    : null;

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
    },
    scales: {
      x: {
        ticks: { color: tgText },
        grid: { display: false },
      },
      y: {
        ticks: { color: tgHint },
        grid: { color: tgHint + "20" },
      },
    },
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
                {report.total_income.toLocaleString("ru-RU")} &#8381;
              </span>
              {prevReport && (
                <DeltaBadge current={report.total_income} previous={prevReport.total_income} />
              )}
            </div>
            <div className="report-summary__item report-summary--expense">
              <span className="report-summary__label">Расход</span>
              <span className="report-summary__value">
                {report.total_expense.toLocaleString("ru-RU")} &#8381;
              </span>
              {prevReport && (
                <DeltaBadge current={report.total_expense} previous={prevReport.total_expense} invertColor />
              )}
            </div>
            <div className="report-summary__item report-summary--balance">
              <span className="report-summary__label">Баланс</span>
              <span className="report-summary__value">
                {report.balance >= 0 ? "+" : ""}
                {report.balance.toLocaleString("ru-RU")} &#8381;
              </span>
              {prevReport && (
                <DeltaBadge current={report.balance} previous={prevReport.balance} />
              )}
            </div>
          </div>

          {/* Income vs Expense bar chart */}
          {(report.total_income > 0 || report.total_expense > 0) && barData && (
            <div className="chart-container chart-container--bar">
              <Bar data={barData} options={barOptions} />
            </div>
          )}

          {/* Income donut chart */}
          {report.income_by_category.length > 0 && (
            <div className="report-section">
              <h3>Доходы</h3>
              <div className="chart-container chart-container--donut">
                <Doughnut
                  data={buildDoughnutData(report.income_by_category)}
                  options={doughnutOptions}
                />
              </div>
              {report.income_by_category.map((c) => {
                const prevAmt = prevReport ? findPrevCategoryAmount(c.category, prevReport.income_by_category) : 0;
                return (
                  <div key={c.category} className="report-bar">
                    <div className="report-bar__label">
                      <span>{c.category}</span>
                      <span>
                        {c.amount.toLocaleString("ru-RU")} &#8381;
                        {prevReport && <DeltaBadge current={c.amount} previous={prevAmt} />}
                      </span>
                    </div>
                    <div className="report-bar__track">
                      <div
                        className="report-bar__fill report-bar__fill--income"
                        style={{ width: `${(c.amount / maxAmount) * 100}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Expense donut chart */}
          {report.expense_by_category.length > 0 && (
            <div className="report-section">
              <h3>Расходы</h3>
              <div className="chart-container chart-container--donut">
                <Doughnut
                  data={buildDoughnutData(report.expense_by_category)}
                  options={doughnutOptions}
                />
              </div>
              {report.expense_by_category.map((c) => {
                const prevAmt = prevReport ? findPrevCategoryAmount(c.category, prevReport.expense_by_category) : 0;
                return (
                  <div key={c.category} className="report-bar">
                    <div className="report-bar__label">
                      <span>{c.category}</span>
                      <span>
                        {c.amount.toLocaleString("ru-RU")} &#8381;
                        {prevReport && <DeltaBadge current={c.amount} previous={prevAmt} invertColor />}
                      </span>
                    </div>
                    <div className="report-bar__track">
                      <div
                        className="report-bar__fill report-bar__fill--expense"
                        style={{ width: `${(c.amount / maxAmount) * 100}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {report.household_total > 0 && (
            <div className="report-section">
              <h3>Бытовые платежи</h3>
              <div className="household-summary">
                <span>Оплачено</span>
                <span>
                  {report.household_paid.toLocaleString("ru-RU")} /{" "}
                  {report.household_total.toLocaleString("ru-RU")} &#8381;
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
