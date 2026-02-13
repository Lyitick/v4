import type { Category } from "../api/client";

interface Props {
  categories: Category[];
  activeCategory: string | null;
  onSelect: (title: string) => void;
}

export function CategoryTabs({ categories, activeCategory, onSelect }: Props) {
  return (
    <div className="category-tabs">
      {categories.map((cat) => (
        <button
          key={cat.id}
          className={`category-tab ${activeCategory === cat.title ? "active" : ""}`}
          onClick={() => onSelect(cat.title)}
        >
          {cat.title}
        </button>
      ))}
    </div>
  );
}
