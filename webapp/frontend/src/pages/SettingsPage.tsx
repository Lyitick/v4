import { useEffect, useState, useCallback } from "react";
import { settingsApi } from "../api/client";
import type {
  UserSettings,
  IncomeCategorySetting,
  WishlistCategorySetting,
  BytReminderCategory,
  BytReminderTime,
  HouseholdItemSetting,
} from "../api/client";

export function SettingsPage() {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openSection, setOpenSection] = useState<string | null>(null);

  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    settingsApi
      .get()
      .then(setSettings)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const reloadSettings = useCallback(() => {
    settingsApi.get().then(setSettings).catch(() => {});
  }, []);

  const toggleSection = (section: string) => {
    setOpenSection((prev) => (prev === section ? null : section));
    tg?.HapticFeedback?.selectionChanged();
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
        <div className="settings-sections">
          <IncomeSection
            open={openSection === "income"}
            onToggle={() => toggleSection("income")}
            onError={setError}
          />
          <WishlistSection
            open={openSection === "wishlist"}
            onToggle={() => toggleSection("wishlist")}
            settings={settings}
            onError={setError}
          />
          <BytSection
            open={openSection === "byt"}
            onToggle={() => toggleSection("byt")}
            settings={settings}
            onSettingsChange={reloadSettings}
            onError={setError}
          />
          <HouseholdSection
            open={openSection === "household"}
            onToggle={() => toggleSection("household")}
            settings={settings}
            onError={setError}
          />
          <TimezoneSection
            settings={settings}
            onSettingsChange={setSettings}
            onError={setError}
          />
        </div>
      ) : null}
    </div>
  );
}

/* ── Income Section ─────────────────────────────────── */

function IncomeSection({
  open,
  onToggle,
  onError,
}: {
  open: boolean;
  onToggle: () => void;
  onError: (msg: string) => void;
}) {
  const [categories, setCategories] = useState<IncomeCategorySetting[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  const load = useCallback(() => {
    settingsApi
      .getIncomeCategories()
      .then((cats) => {
        setCategories(cats);
        setLoaded(true);
      })
      .catch((e) => onError(e.message));
  }, [onError]);

  useEffect(() => {
    if (open && !loaded) load();
  }, [open, loaded, load]);

  const handleAdd = async () => {
    if (!newTitle.trim()) return;
    try {
      await settingsApi.addIncomeCategory(newTitle.trim());
      setNewTitle("");
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleRemove = async (id: number) => {
    try {
      await settingsApi.removeIncomeCategory(id);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handlePercentChange = async (id: number, percent: number) => {
    try {
      await settingsApi.updateIncomeCategoryPercent(id, percent);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const totalPercent = categories.reduce((sum, c) => sum + c.percent, 0);

  return (
    <div className={`settings-section ${open ? "settings-section--open" : ""}`}>
      <div className="settings-section__header" onClick={onToggle}>
        <span>Доход</span>
      </div>
      {open && (
        <div className="settings-section__content">
          {categories.map((cat) => (
            <div key={cat.id} className="settings-list-item">
              <span className="settings-list-item__title">{cat.title}</span>
              <div className="settings-list-item__actions">
                <input
                  type="number"
                  className="settings-inline-input"
                  value={cat.percent}
                  min={0}
                  max={100}
                  onChange={(e) => {
                    const val = parseInt(e.target.value) || 0;
                    setCategories((prev) =>
                      prev.map((c) => (c.id === cat.id ? { ...c, percent: val } : c))
                    );
                  }}
                  onBlur={(e) => {
                    const val = parseInt(e.target.value) || 0;
                    handlePercentChange(cat.id, Math.min(100, Math.max(0, val)));
                  }}
                />
                <span className="settings-list-item__unit">%</span>
                <button className="btn btn--icon btn--danger-text" onClick={() => handleRemove(cat.id)}>
                  &times;
                </button>
              </div>
            </div>
          ))}
          <div className="settings-total">
            Итого: <strong className={totalPercent === 100 ? "text-ok" : "text-warn"}>{totalPercent}%</strong>
          </div>
          <div className="settings-add-row">
            <input
              className="input"
              placeholder="Название категории"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button className="btn btn--primary btn--sm" onClick={handleAdd}>+</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Wishlist Section ───────────────────────────────── */

function WishlistSection({
  open,
  onToggle,
  settings,
  onError,
}: {
  open: boolean;
  onToggle: () => void;
  settings: UserSettings;
  onError: (msg: string) => void;
}) {
  const [categories, setCategories] = useState<WishlistCategorySetting[]>([]);
  const [incomeCategories, setIncomeCategories] = useState<IncomeCategorySetting[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [newTitle, setNewTitle] = useState("");

  const load = useCallback(() => {
    Promise.all([
      settingsApi.getWishlistCategories(),
      settingsApi.getIncomeCategories(),
    ])
      .then(([wlCats, incCats]) => {
        setCategories(wlCats);
        setIncomeCategories(incCats);
        setLoaded(true);
      })
      .catch((e) => onError(e.message));
  }, [onError]);

  useEffect(() => {
    if (open && !loaded) load();
  }, [open, loaded, load]);

  const handleAdd = async () => {
    if (!newTitle.trim()) return;
    try {
      await settingsApi.addWishlistCategory(newTitle.trim());
      setNewTitle("");
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleRemove = async (id: number) => {
    try {
      await settingsApi.removeWishlistCategory(id);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleModeChange = async (id: number, mode: string) => {
    try {
      await settingsApi.updatePurchasedMode(id, mode);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleDaysChange = async (id: number, days: number) => {
    try {
      await settingsApi.updatePurchasedDays(id, days);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleDebitCategoryChange = async (categoryId: string | null) => {
    try {
      await settingsApi.setWishlistDebitCategory(categoryId);
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleBytCategoryChange = async (categoryId: number | null) => {
    try {
      await settingsApi.setBytWishlistCategory(categoryId);
    } catch (e: any) {
      onError(e.message);
    }
  };

  return (
    <div className={`settings-section ${open ? "settings-section--open" : ""}`}>
      <div className="settings-section__header" onClick={onToggle}>
        <span>Вишлист</span>
      </div>
      {open && (
        <div className="settings-section__content">
          <div className="settings-subtitle">Категории</div>
          {categories.map((cat) => (
            <div key={cat.id} className="settings-list-item">
              <span className="settings-list-item__title">{cat.title}</span>
              <div className="settings-list-item__actions">
                <select
                  className="settings-inline-select"
                  value={cat.purchased_mode || "days"}
                  onChange={(e) => handleModeChange(cat.id, e.target.value)}
                >
                  <option value="always">Всегда</option>
                  <option value="days">Дни</option>
                </select>
                {cat.purchased_mode !== "always" && (
                  <input
                    type="number"
                    className="settings-inline-input"
                    value={cat.purchased_days || 30}
                    min={1}
                    max={365}
                    onChange={(e) => {
                      const val = parseInt(e.target.value) || 30;
                      setCategories((prev) =>
                        prev.map((c) =>
                          c.id === cat.id ? { ...c, purchased_days: val } : c
                        )
                      );
                    }}
                    onBlur={(e) => {
                      const val = parseInt(e.target.value) || 30;
                      handleDaysChange(cat.id, Math.min(365, Math.max(1, val)));
                    }}
                  />
                )}
                <button className="btn btn--icon btn--danger-text" onClick={() => handleRemove(cat.id)}>
                  &times;
                </button>
              </div>
            </div>
          ))}
          <div className="settings-add-row">
            <input
              className="input"
              placeholder="Новая категория"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button className="btn btn--primary btn--sm" onClick={handleAdd}>+</button>
          </div>

          <div className="settings-subtitle">Категория списания</div>
          <select
            className="settings-select"
            value={settings.wishlist_debit_category_id || ""}
            onChange={(e) =>
              handleDebitCategoryChange(e.target.value || null)
            }
          >
            <option value="">Не выбрана</option>
            {incomeCategories.map((c) => (
              <option key={c.id} value={c.title}>
                {c.title}
              </option>
            ))}
          </select>

          <div className="settings-subtitle">БЫТ категория</div>
          <select
            className="settings-select"
            value={settings.byt_wishlist_category_id ?? ""}
            onChange={(e) =>
              handleBytCategoryChange(e.target.value ? parseInt(e.target.value) : null)
            }
          >
            <option value="">Не выбрана</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

/* ── BYT Reminders Section ──────────────────────────── */

function BytSection({
  open,
  onToggle,
  settings,
  onSettingsChange,
  onError,
}: {
  open: boolean;
  onToggle: () => void;
  settings: UserSettings;
  onSettingsChange: () => void;
  onError: (msg: string) => void;
}) {
  const [categories, setCategories] = useState<BytReminderCategory[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [expandedCat, setExpandedCat] = useState<number | null>(null);
  const [catTimes, setCatTimes] = useState<BytReminderTime[]>([]);
  const [newTime, setNewTime] = useState("");
  const [editDays, setEditDays] = useState(settings.byt_defer_max_days);

  const load = useCallback(() => {
    settingsApi
      .getBytReminderCategories()
      .then((cats) => {
        setCategories(cats);
        setLoaded(true);
      })
      .catch((e) => onError(e.message));
  }, [onError]);

  useEffect(() => {
    if (open && !loaded) load();
  }, [open, loaded, load]);

  const loadTimes = useCallback(
    (catId: number) => {
      settingsApi
        .getBytReminderTimes(catId)
        .then(setCatTimes)
        .catch((e) => onError(e.message));
    },
    [onError]
  );

  useEffect(() => {
    if (expandedCat !== null) loadTimes(expandedCat);
  }, [expandedCat, loadTimes]);

  const handleToggleReminders = async () => {
    try {
      await settingsApi.toggleBytReminders();
      onSettingsChange();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleToggleDefer = async () => {
    try {
      await settingsApi.toggleBytDefer();
      onSettingsChange();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleMaxDaysBlur = async () => {
    const days = Math.min(365, Math.max(1, editDays));
    try {
      await settingsApi.updateMaxDeferDays(days);
      setEditDays(days);
      onSettingsChange();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleToggleCategory = async (catId: number) => {
    try {
      await settingsApi.toggleBytReminderCategory(catId);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleAddTime = async () => {
    if (!newTime || expandedCat === null) return;
    try {
      await settingsApi.addBytReminderTime(expandedCat, newTime);
      setNewTime("");
      loadTimes(expandedCat);
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleRemoveTime = async (time: string) => {
    if (expandedCat === null) return;
    try {
      await settingsApi.removeBytReminderTime(expandedCat, time);
      loadTimes(expandedCat);
    } catch (e: any) {
      onError(e.message);
    }
  };

  return (
    <div className={`settings-section ${open ? "settings-section--open" : ""}`}>
      <div className="settings-section__header" onClick={onToggle}>
        <span>Напоминания</span>
      </div>
      {open && (
        <div className="settings-section__content">
          <div
            className="settings-item settings-item--toggle"
            onClick={handleToggleReminders}
          >
            <span className="settings-item__label">Напоминания</span>
            <span className={`settings-toggle ${settings.byt_reminders_enabled ? "on" : "off"}`}>
              {settings.byt_reminders_enabled ? "ВКЛ" : "ВЫКЛ"}
            </span>
          </div>

          <div
            className="settings-item settings-item--toggle"
            onClick={handleToggleDefer}
          >
            <span className="settings-item__label">Отложить</span>
            <span className={`settings-toggle ${settings.byt_defer_enabled ? "on" : "off"}`}>
              {settings.byt_defer_enabled ? "ВКЛ" : "ВЫКЛ"}
            </span>
          </div>

          <div className="settings-item">
            <span className="settings-item__label">Макс. дней отложить</span>
            <input
              type="number"
              className="settings-inline-input"
              value={editDays}
              min={1}
              max={365}
              onChange={(e) => setEditDays(parseInt(e.target.value) || 1)}
              onBlur={handleMaxDaysBlur}
            />
          </div>

          <div className="settings-subtitle">Категории</div>
          {categories.map((cat) => (
            <div key={cat.id}>
              <div className="settings-list-item">
                <span
                  className="settings-list-item__title settings-list-item__clickable"
                  onClick={() =>
                    setExpandedCat((prev) => (prev === cat.id ? null : cat.id))
                  }
                >
                  {cat.title}
                </span>
                <div className="settings-list-item__actions">
                  <button
                    className={`btn btn--sm ${cat.enabled ? "btn--primary" : "btn--secondary"}`}
                    onClick={() => handleToggleCategory(cat.id)}
                  >
                    {cat.enabled ? "ВКЛ" : "ВЫКЛ"}
                  </button>
                </div>
              </div>
              {expandedCat === cat.id && (
                <div className="settings-times">
                  <div className="settings-tags">
                    {catTimes.map((t) => (
                      <span key={t.time_hhmm} className="settings-tag">
                        {t.time_hhmm}
                        <button
                          className="settings-tag__remove"
                          onClick={() => handleRemoveTime(t.time_hhmm)}
                        >
                          &times;
                        </button>
                      </span>
                    ))}
                  </div>
                  <div className="settings-add-row">
                    <input
                      type="time"
                      className="input"
                      value={newTime}
                      onChange={(e) => setNewTime(e.target.value)}
                    />
                    <button className="btn btn--primary btn--sm" onClick={handleAddTime}>
                      +
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Household Payments Section ─────────────────────── */

function HouseholdSection({
  open,
  onToggle,
  settings,
  onError,
}: {
  open: boolean;
  onToggle: () => void;
  settings: UserSettings;
  onError: (msg: string) => void;
}) {
  const [items, setItems] = useState<HouseholdItemSetting[]>([]);
  const [incomeCategories, setIncomeCategories] = useState<IncomeCategorySetting[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [newText, setNewText] = useState("");
  const [newAmount, setNewAmount] = useState("");

  const load = useCallback(() => {
    Promise.all([
      settingsApi.getHouseholdItems(),
      settingsApi.getIncomeCategories(),
    ])
      .then(([hItems, incCats]) => {
        setItems(hItems);
        setIncomeCategories(incCats);
        setLoaded(true);
      })
      .catch((e) => onError(e.message));
  }, [onError]);

  useEffect(() => {
    if (open && !loaded) load();
  }, [open, loaded, load]);

  const handleAdd = async () => {
    if (!newText.trim() || !newAmount) return;
    try {
      await settingsApi.addHouseholdItem(newText.trim(), parseInt(newAmount));
      setNewText("");
      setNewAmount("");
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleRemove = async (code: string) => {
    try {
      await settingsApi.removeHouseholdItem(code);
      load();
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleDebitCategory = async (category: string | null) => {
    try {
      await settingsApi.setHouseholdDebitCategory(category);
    } catch (e: any) {
      onError(e.message);
    }
  };

  const handleReset = async () => {
    try {
      await settingsApi.resetHouseholdPayments();
    } catch (e: any) {
      onError(e.message);
    }
  };

  return (
    <div className={`settings-section ${open ? "settings-section--open" : ""}`}>
      <div className="settings-section__header" onClick={onToggle}>
        <span>Бытовые платежи</span>
      </div>
      {open && (
        <div className="settings-section__content">
          {items.map((item) => (
            <div key={item.code} className="settings-list-item">
              <span className="settings-list-item__title">{item.text}</span>
              <span className="settings-list-item__value">
                {item.amount.toLocaleString("ru-RU")} &#8381;
              </span>
              <button
                className="btn btn--icon btn--danger-text"
                onClick={() => handleRemove(item.code)}
              >
                &times;
              </button>
            </div>
          ))}

          <div className="settings-add-row">
            <input
              className="input"
              placeholder="Название"
              value={newText}
              onChange={(e) => setNewText(e.target.value)}
            />
            <input
              className="input input--short"
              placeholder="Сумма"
              type="number"
              value={newAmount}
              onChange={(e) => setNewAmount(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            />
            <button className="btn btn--primary btn--sm" onClick={handleAdd}>+</button>
          </div>

          <div className="settings-subtitle">Категория списания</div>
          <select
            className="settings-select"
            value={settings.household_debit_category || ""}
            onChange={(e) => handleDebitCategory(e.target.value || null)}
          >
            <option value="">Не выбрана</option>
            {incomeCategories.map((c) => (
              <option key={c.id} value={c.title}>
                {c.title}
              </option>
            ))}
          </select>

          <button className="btn btn--danger btn--sm settings-reset-btn" onClick={handleReset}>
            Обнулить платежи
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Timezone Section ───────────────────────────────── */

function TimezoneSection({
  settings,
  onSettingsChange,
  onError,
}: {
  settings: UserSettings;
  onSettingsChange: (s: UserSettings) => void;
  onError: (msg: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [tz, setTz] = useState(settings.timezone);

  const handleSave = async () => {
    if (!tz.trim()) return;
    try {
      await settingsApi.updateTimezone(tz.trim());
      onSettingsChange({ ...settings, timezone: tz.trim() });
      setEditing(false);
    } catch (e: any) {
      onError(e.message);
    }
  };

  return (
    <div className="settings-section settings-section--open">
      <div className="settings-section__header">
        <span>Таймзона</span>
      </div>
      <div className="settings-section__content">
        {editing ? (
          <div className="settings-add-row">
            <input
              className="input"
              value={tz}
              onChange={(e) => setTz(e.target.value)}
              placeholder="Europe/Moscow"
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
            <button className="btn btn--primary btn--sm" onClick={handleSave}>
              OK
            </button>
            <button
              className="btn btn--secondary btn--sm"
              onClick={() => {
                setTz(settings.timezone);
                setEditing(false);
              }}
            >
              &times;
            </button>
          </div>
        ) : (
          <div className="settings-item" onClick={() => setEditing(true)}>
            <span className="settings-item__label">Часовой пояс</span>
            <span className="settings-item__value settings-item__editable">
              {settings.timezone}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
