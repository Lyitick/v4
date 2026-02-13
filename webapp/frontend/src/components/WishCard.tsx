import type { Wish } from "../api/client";

interface Props {
  wish: Wish;
  onPurchase: (id: number) => void;
  onDelete: (id: number) => void;
}

export function WishCard({ wish, onPurchase, onDelete }: Props) {
  const isDeferred = wish.deferred_until && new Date(wish.deferred_until) > new Date();

  return (
    <div className={`wish-card ${wish.is_purchased ? "purchased" : ""} ${isDeferred ? "deferred" : ""}`}>
      <div className="wish-card__header">
        <span className="wish-card__name">{wish.name}</span>
        <span className="wish-card__price">{wish.price.toLocaleString("ru-RU")} ₽</span>
      </div>

      {wish.url && (
        <a
          className="wish-card__link"
          href={wish.url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Ссылка
        </a>
      )}

      {wish.saved_amount > 0 && !wish.is_purchased && (
        <div className="wish-card__saved">
          Накоплено: {wish.saved_amount.toLocaleString("ru-RU")} ₽
          <div className="wish-card__progress">
            <div
              className="wish-card__progress-bar"
              style={{ width: `${Math.min((wish.saved_amount / wish.price) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {isDeferred && (
        <div className="wish-card__deferred">
          Отложено до {new Date(wish.deferred_until!).toLocaleDateString("ru-RU")}
        </div>
      )}

      {wish.is_purchased && wish.purchased_at && (
        <div className="wish-card__purchased-at">
          Куплено {new Date(wish.purchased_at).toLocaleDateString("ru-RU")}
        </div>
      )}

      {!wish.is_purchased && (
        <div className="wish-card__actions">
          <button className="btn btn--primary" onClick={() => onPurchase(wish.id)}>
            Купить
          </button>
          <button className="btn btn--danger" onClick={() => onDelete(wish.id)}>
            Удалить
          </button>
        </div>
      )}
    </div>
  );
}
