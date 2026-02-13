import { useState } from "react";

interface Props {
  category: string;
  onSubmit: (data: { name: string; price: number; url?: string; category: string }) => void;
  onCancel: () => void;
}

export function AddWishForm({ category, onSubmit, onCancel }: Props) {
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [url, setUrl] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const parsedPrice = parseFloat(price);
    if (!name.trim() || isNaN(parsedPrice) || parsedPrice <= 0) return;

    onSubmit({
      name: name.trim(),
      price: parsedPrice,
      url: url.trim() || undefined,
      category,
    });
  };

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <form className="add-wish-form" onClick={(e) => e.stopPropagation()} onSubmit={handleSubmit}>
        <h3>Новое желание</h3>
        <p className="add-wish-form__category">Категория: {category}</p>

        <input
          className="input"
          placeholder="Название"
          value={name}
          onChange={(e) => setName(e.target.value)}
          autoFocus
          required
        />

        <input
          className="input"
          placeholder="Цена (₽)"
          type="number"
          min="1"
          step="any"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
        />

        <input
          className="input"
          placeholder="Ссылка (необязательно)"
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />

        <div className="add-wish-form__actions">
          <button type="submit" className="btn btn--primary" disabled={!name.trim() || !price}>
            Добавить
          </button>
          <button type="button" className="btn btn--secondary" onClick={onCancel}>
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
}
