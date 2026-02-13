import { useEffect, useState, useCallback } from "react";
import { wishlistApi } from "../api/client";
import type { Category, Wish } from "../api/client";
import { CategoryTabs } from "../components/CategoryTabs";
import { WishCard } from "../components/WishCard";
import { AddWishForm } from "../components/AddWishForm";

export function WishlistPage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [wishes, setWishes] = useState<Wish[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tg = window.Telegram?.WebApp;

  // Load categories on mount
  useEffect(() => {
    wishlistApi
      .getCategories()
      .then((cats) => {
        setCategories(cats);
        if (cats.length > 0) {
          setActiveCategory(cats[0].title);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  // Load wishes when category changes
  const loadWishes = useCallback(() => {
    if (!activeCategory) return;
    setLoading(true);
    wishlistApi
      .getWishes(activeCategory)
      .then(setWishes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [activeCategory]);

  useEffect(() => {
    loadWishes();
  }, [loadWishes]);

  const handlePurchase = async (wishId: number) => {
    try {
      const result = await wishlistApi.purchaseWish(wishId);
      if (result.ok) {
        tg?.HapticFeedback?.notificationOccurred("success");
        loadWishes();
      } else {
        tg?.HapticFeedback?.notificationOccurred("error");
        setError(result.message || "Ошибка");
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (wishId: number) => {
    try {
      await wishlistApi.deleteWish(wishId);
      tg?.HapticFeedback?.impactOccurred("medium");
      loadWishes();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleAddWish = async (data: {
    name: string;
    price: number;
    url?: string;
    category: string;
  }) => {
    try {
      await wishlistApi.createWish(data);
      tg?.HapticFeedback?.notificationOccurred("success");
      setShowAddForm(false);
      loadWishes();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const activeWishes = wishes.filter((w) => !w.is_purchased);
  const purchasedWishes = wishes.filter((w) => w.is_purchased);

  return (
    <div className="page">
      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error}
        </div>
      )}

      <CategoryTabs
        categories={categories}
        activeCategory={activeCategory}
        onSelect={(title) => {
          setActiveCategory(title);
          tg?.HapticFeedback?.selectionChanged();
        }}
      />

      {loading ? (
        <div className="loader">Загрузка...</div>
      ) : (
        <>
          <div className="wishes-section">
            <div className="section-header">
              <h2>Желания</h2>
              <button
                className="btn btn--add"
                onClick={() => setShowAddForm(true)}
              >
                +
              </button>
            </div>

            {activeWishes.length === 0 ? (
              <p className="empty-state">Нет желаний в этой категории</p>
            ) : (
              activeWishes.map((wish) => (
                <WishCard
                  key={wish.id}
                  wish={wish}
                  onPurchase={handlePurchase}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>

          {purchasedWishes.length > 0 && (
            <div className="wishes-section wishes-section--purchased">
              <h2>Куплено</h2>
              {purchasedWishes.map((wish) => (
                <WishCard
                  key={wish.id}
                  wish={wish}
                  onPurchase={handlePurchase}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </>
      )}

      {showAddForm && activeCategory && (
        <AddWishForm
          category={activeCategory}
          onSubmit={handleAddWish}
          onCancel={() => setShowAddForm(false)}
        />
      )}
    </div>
  );
}
