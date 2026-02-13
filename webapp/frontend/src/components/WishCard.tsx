import type { Wish } from "../api/client";

interface Props {
  wish: Wish;
  onPurchase: (id: number) => void;
  onDelete: (id: number) => void;
  onRestore?: (id: number) => void;
}

export function WishCard({ wish, onPurchase, onDelete, onRestore }: Props) {
  const isDeferred = wish.deferred_until && new Date(wish.deferred_until) > new Date();
  const isDeleted = !!wish.deleted_at;

  let deleteTimeRemaining: string | null = null;
  if (isDeleted && wish.deleted_at) {
    const deletedDate = new Date(wish.deleted_at);
    const expiresAt = new Date(deletedDate.getTime() + 24 * 60 * 60 * 1000);
    const now = new Date();
    const diff = expiresAt.getTime() - now.getTime();
    if (diff > 0) {
      const hoursLeft = Math.floor(diff / (1000 * 60 * 60));
      const minutesLeft = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      deleteTimeRemaining = `${hoursLeft}ч ${minutesLeft}м`;
    } else {
      deleteTimeRemaining = "скоро";
    }
  }

  return (
    <div className={`wish-card ${wish.is_purchased ? "purchased" : ""} ${isDeferred ? "deferred" : ""} ${isDeleted ? "deleted" : ""}`}>
      <div className="wish-card__header">
        <span className="wish-card__name">{wish.name}</span>
        <span className="wish-card__price">{wish.price.toLocaleString("ru-RU")} &#8381;</span>
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

      {wish.saved_amount > 0 && !wish.is_purchased && !isDeleted && (
        <div className="wish-card__saved">
          Накоплено: {wish.saved_amount.toLocaleString("ru-RU")} &#8381;
          <div className="wish-card__progress">
            <div
              className="wish-card__progress-bar"
              style={{ width: `${Math.min((wish.saved_amount / wish.price) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {isDeferred && !isDeleted && (
        <div className="wish-card__deferred">
          Отложено до {new Date(wish.deferred_until!).toLocaleDateString("ru-RU")}
        </div>
      )}

      {wish.is_purchased && wish.purchased_at && !isDeleted && (
        <div className="wish-card__purchased-at">
          Куплено {new Date(wish.purchased_at).toLocaleDateString("ru-RU")}
        </div>
      )}

      {isDeleted && (
        <div className="wish-card__deleted-info">
          Удалено. Восстановить можно ещё {deleteTimeRemaining}
        </div>
      )}

      {isDeleted && onRestore && (
        <div className="wish-card__actions">
          <button className="btn btn--secondary" onClick={() => onRestore(wish.id)}>
            Восстановить
          </button>
        </div>
      )}

      {!wish.is_purchased && !isDeleted && (
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
