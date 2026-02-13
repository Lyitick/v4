import { useEffect, useState } from "react";
import { IncomePage } from "./pages/IncomePage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { WishlistPage } from "./pages/WishlistPage";
import { HouseholdPage } from "./pages/HouseholdPage";
import { SavingsPage } from "./pages/SavingsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { DebtsPage } from "./pages/DebtsPage";
import { RecurringPage } from "./pages/RecurringPage";
import { ReportsPage } from "./pages/ReportsPage";
import { TabBar } from "./components/TabBar";
import "./styles.css";

function App() {
  const [activeTab, setActiveTab] = useState("income");

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
    }
  }, []);

  const renderPage = () => {
    switch (activeTab) {
      case "income":
        return <IncomePage />;
      case "expenses":
        return <ExpensesPage />;
      case "wishlist":
        return <WishlistPage />;
      case "household":
        return <HouseholdPage />;
      case "savings":
        return <SavingsPage />;
      case "debts":
        return <DebtsPage />;
      case "recurring":
        return <RecurringPage />;
      case "reports":
        return <ReportsPage />;
      case "settings":
        return <SettingsPage />;
      default:
        return <IncomePage />;
    }
  };

  return (
    <div className="app">
      <div className="app__content">{renderPage()}</div>
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  );
}

export default App;
