"""Tests for household services."""

from Bot.services.household import (
    build_household_questions,
    get_current_question,
    get_next_index,
    get_previous_index,
    should_ignore_answer,
    update_flow_state,
)


def test_flow_state_and_navigation() -> None:
    questions = build_household_questions(
        [
            {"code": "q1", "text": "Первый?", "amount": 100},
            {"code": "q2", "text": "Второй?", "amount": 200},
        ]
    )
    flow = update_flow_state(
        month="2025-01",
        questions=questions,
        current_step_index=0,
        answers={},
        processed_steps=[],
    )
    assert flow.current_question_code == "q1"
    assert get_current_question(questions, 1)["code"] == "q2"
    assert get_next_index(0, questions) == 1
    assert get_next_index(1, questions) == 2
    assert get_previous_index(0) == 0
    assert get_previous_index(1) == 0


def test_idempotency_check() -> None:
    answers = {"q1": "yes"}
    processed_steps = {"q1"}
    assert should_ignore_answer(answers, processed_steps, "q1", "yes") is True
    assert should_ignore_answer(answers, processed_steps, "q1", "no") is False
    assert should_ignore_answer(answers, processed_steps, "q2", "yes") is False
