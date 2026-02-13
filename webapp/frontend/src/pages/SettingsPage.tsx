import { useEffect, useState } from "react";
import { settingsApi } from "../api/client";
import type { UserSettings } from "../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    settingsApi
      .get()
      .then(setSettings)
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
      ) : null}
    </div>
  );
}
