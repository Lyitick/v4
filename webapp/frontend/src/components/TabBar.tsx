interface Tab {
  id: string;
  label: string;
  icon: string;
}

const tabs: Tab[] = [
  { id: "income", label: "Доход", icon: "💰" },
  { id: "expenses", label: "Расходы", icon: "💸" },
  { id: "wishlist", label: "Вишлист", icon: "📋" },
  { id: "household", label: "Платежи", icon: "🏠" },
  { id: "savings", label: "Копилка", icon: "🎯" },
  { id: "debts", label: "Долги", icon: "🤝" },
  { id: "recurring", label: "Авто", icon: "🔄" },
  { id: "reports", label: "Отчёт", icon: "📊" },
  { id: "settings", label: "Ещё", icon: "⚙️" },
];

interface Props {
  activeTab: string;
  onTabChange: (id: string) => void;
}

export function TabBar({ activeTab, onTabChange }: Props) {
  const handleTab = (id: string) => {
    if (id !== activeTab) {
      window.Telegram?.WebApp?.HapticFeedback?.selectionChanged();
    }
    onTabChange(id);
  };

  return (
    <nav className="tab-bar">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`tab-bar__item ${activeTab === tab.id ? "active" : ""}`}
          onClick={() => handleTab(tab.id)}
        >
          <span className="tab-bar__icon">{tab.icon}</span>
          <span className="tab-bar__label">{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}
