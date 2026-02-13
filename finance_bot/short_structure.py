import os
import sys
from pathlib import Path
from typing import Set

# Папки, которые не хотим видеть в выводе
IGNORE_DIRS: Set[str] = {
    ".git",
    ".idea",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
}


def print_tree(root: Path, max_depth: int, depth: int = 0) -> None:
    """Рекурсивно печатает дерево файлов до max_depth."""
    if depth > max_depth:
        return

    try:
        items = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return

    for item in items:
        # Пропускаем служебные папки
        if item.is_dir() and item.name in IGNORE_DIRS:
            continue

        indent = "    " * depth
        prefix = "📁" if item.is_dir() else "📄"
        print(f"{indent}{prefix} {item.name}{'/' if item.is_dir() else ''}")

        if item.is_dir():
            print_tree(item, max_depth, depth + 1)


def parse_max_depth() -> int:
    """Читает глубину из аргументов командной строки, по умолчанию 3."""
    default_depth = 3
    if len(sys.argv) < 2:
        return default_depth
    try:
        value = int(sys.argv[1])
        return max(0, value)
    except ValueError:
        return default_depth


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent
    max_depth = parse_max_depth()

    print(f"Структура проекта: {project_root}")
    print(f"Максимальная глубина: {max_depth}\n")
    print_tree(project_root, max_depth)

#python short_structure.py 4(цифра меняет глубину)
