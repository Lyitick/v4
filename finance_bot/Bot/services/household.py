"""Business logic for household payments flow."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class HouseholdFlowState:
    """Container for household flow state."""

    month: str
    questions: list[dict]
    current_step_index: int
    current_question_code: str | None
    answers: dict[str, str]
    processed_steps: set[str]


def build_household_questions(items: Iterable[dict]) -> list[dict]:
    return [
        {
            "code": str(item.get("code", "")),
            "text": str(item.get("text", "")),
            "amount": item.get("amount"),
        }
        for item in items
        if item.get("code") is not None
    ]


def build_answers_from_status(status_map: dict[str, int]) -> dict[str, str]:
    return {
        str(code): "yes"
        for code, value in status_map.items()
        if int(value) == 1
    }


def filter_unpaid_questions(
    questions: Iterable[dict], unpaid_codes: Iterable[str]
) -> list[dict]:
    unpaid_set = {str(code) for code in unpaid_codes}
    return [question for question in questions if question.get("code") in unpaid_set]


def get_current_question(questions: list[dict], index: int) -> dict | None:
    if index < 0 or index >= len(questions):
        return None
    return questions[index]


def get_next_index(index: int, questions: list[dict]) -> int:
    return min(index + 1, len(questions))


def get_previous_index(index: int) -> int:
    return max(index - 1, 0)


def should_ignore_answer(
    answers: dict[str, str],
    processed_steps: set[str],
    question_code: str,
    action: str,
) -> bool:
    return question_code in processed_steps and answers.get(question_code) == action


def normalize_processed_steps(value: Iterable[str] | None) -> set[str]:
    if not value:
        return set()
    return {str(item) for item in value}


def update_flow_state(
    month: str,
    questions: list[dict],
    current_step_index: int,
    answers: dict[str, str] | None,
    processed_steps: Iterable[str] | None,
) -> HouseholdFlowState:
    current_question = get_current_question(questions, current_step_index)
    return HouseholdFlowState(
        month=month,
        questions=questions,
        current_step_index=current_step_index,
        current_question_code=str(current_question.get("code"))
        if current_question
        else None,
        answers=dict(answers or {}),
        processed_steps=normalize_processed_steps(processed_steps),
    )
