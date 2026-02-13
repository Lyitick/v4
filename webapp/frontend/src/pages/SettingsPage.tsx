import { useEffect, useState } from "react";
import { settingsApi, gsheetsApi, exportApi } from "../api/client";
import type { UserSettings, SheetsStatus } from "../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [sheetsStatus, setSheetsStatus] = useState<SheetsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sheetsUrl, setSheetsUrl] = useState("");
  const [syncing, setSyncing] = useState(false);

  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    Promise.all([settingsApi.get(), gsheetsApi.status()])
      .then(([s, gs]) => {
        setSettings(s);
        setSheetsStatus(gs);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleToggleReminders = async () => {
    try {
      const result = await settingsApi.toggleBytReminders();
      setSettings((prev) =>
        prev ? { ...prev, byt_reminders_enabled: result.enabled } : prev
      );
      tg?.HapticFeedback?.impactOccurred("light");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleConnectSheets = async () => {
    if (!sheetsUrl.trim()) return;
    try {
      await gsheetsApi.connect(sheetsUrl.trim());
      const status = await gsheetsApi.status();
      setSheetsStatus(status);
      setSheetsUrl("");
      tg?.HapticFeedback?.impactOccurred("medium");
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    }
  };

  const handleDisconnectSheets = async () => {
    try {
      await gsheetsApi.disconnect();
      setSheetsStatus({ connected: false });
      tg?.HapticFeedback?.impactOccurred("light");
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSyncSheets = async () => {
    setSyncing(true);
    try {
      const result = await gsheetsApi.sync();
      if (result.ok) {
        tg?.HapticFeedback?.notificationOccurred("success");
      } else {
        setError(result.error || "Ошибка синхронизации");
        tg?.HapticFeedback?.notificationOccurred("error");
      }
    } catch (err: any) {
      setError(err.message);
      tg?.HapticFeedback?.notificationOccurred("error");
    } finally {
      setSyncing(false);
    }
  };

  const handleExportExcel = async () => {
    try {
      await exportApi.downloadExcel();
      tg?.HapticFeedback?.impactOccurred("medium");
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <h2>Настройки</h2>

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : settings ? (
        <>
          <div className="settings-list">
            <div className="settings-item">
              <span className="settings-item__label">Часовой пояс</span>
              <span className="settings-item__value">{settings.timezone}</span>
            </div>

            <div className="settings-item">
              <span className="settings-item__label">Хранить покупки (дней)</span>
              <span className="settings-item__value">
                {settings.purchased_keep_days}
              </span>
            </div>

            <div
              className="settings-item settings-item--toggle"
              onClick={handleToggleReminders}
            >
              <span className="settings-item__label">Напоминания (БЫТ)</span>
              <span
                className={`settings-toggle ${settings.byt_reminders_enabled ? "on" : "off"}`}
              >
                {settings.byt_reminders_enabled ? "ВКЛ" : "ВЫКЛ"}
              </span>
            </div>

            <div className="settings-item">
              <span className="settings-item__label">Отложить макс. дней</span>
              <span className="settings-item__value">
                {settings.byt_defer_max_days}
              </span>
            </div>
          </div>

          {/* Google Sheets section */}
          <h3 className="settings-section-title">Google Sheets</h3>
          <div className="settings-list">
            {sheetsStatus?.connected ? (
              <>
                <div className="settings-item">
                  <span className="settings-item__label">Статус</span>
                  <span className="settings-item__value gsheets-connected">
                    Подключено
                  </span>
                </div>
                <div className="gsheets-actions">
                  <button
                    className="btn btn--primary btn--full"
                    onClick={handleSyncSheets}
                    disabled={syncing}
                  >
                    {syncing ? "Синхронизация..." : "Синхронизировать"}
                  </button>
                  <button
                    className="btn btn--secondary btn--full"
                    onClick={handleDisconnectSheets}
                  >
                    Отключить
                  </button>
                </div>
              </>
            ) : (
              <>
                {sheetsStatus?.service_account_email && (
                  <div className="gsheets-hint">
                    Предоставьте доступ к таблице для:
                    <br />
                    <code className="gsheets-email">
                      {sheetsStatus.service_account_email}
                    </code>
                  </div>
                )}
                <div className="gsheets-connect">
                  <input
                    className="input"
                    placeholder="Ссылка на Google Таблицу"
                    value={sheetsUrl}
                    onChange={(e) => setSheetsUrl(e.target.value)}
                  />
                  <button
                    className="btn btn--primary btn--full"
                    onClick={handleConnectSheets}
                    disabled={!sheetsUrl.trim()}
                  >
                    Подключить
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Export section */}
          <h3 className="settings-section-title">Экспорт</h3>
          <div className="settings-list">
            <button
              className="btn btn--secondary btn--full"
              onClick={handleExportExcel}
            >
              Скачать Excel
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
