"""Savings utility helpers."""
from typing import Any, Dict, List, Tuple


def _fallback_humanize_category(category: str) -> str:
    name = str(category)
    if name.startswith("savings_"):
        name = name[len("savings_") :]
    name = name.replace("_", " ").strip()
    return name or str(category)


def format_savings_summary(
    savings: Dict[str, Dict[str, Any]],
    categories_map: Dict[str, str] | None = None,
) -> str:
    """Format savings summary for user message."""

    if not savings:
        return "Пока нет накоплений."

    lines: List[str] = []
    for category, data in savings.items():
        display_name = None
        if categories_map is not None:
            display_name = categories_map.get(str(category))
        if not display_name:
            display_name = _fallback_humanize_category(str(category))
        current = data.get("current", 0)
        goal = data.get("goal", 0)
        purpose = data.get("purpose", "")
        line = f"{display_name}: {current:.2f}"
        if goal and goal > 0:
            progress = min(current / goal * 100, 100)
            extra = f" (цель {goal:.2f} для '{purpose}', прогресс {progress:.1f}%)"
            line = f"{line}{extra}"
        lines.append(line)
    return "\n".join(lines)


def find_reached_goal(
    savings: Dict[str, Dict[str, Any]]
) -> Tuple[str, Dict[str, Any]] | Tuple[None, None]:
    """Find first saving goal that has been reached."""

    for category, data in savings.items():
        current = data.get("current", 0)
        goal = data.get("goal", 0)
        if goal and current >= goal:
            return category, data
    return None, None
