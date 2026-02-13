import { useEffect } from "react";
import { WishlistPage } from "./pages/WishlistPage";
import "./styles.css";

function App() {
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
    }
  }, []);

  return (
    <div className="app">
      <WishlistPage />
    </div>
  );
}

export default App;
