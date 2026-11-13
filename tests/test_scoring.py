# tests/test_scoring.py

import pytest

from app.services.scoring import (
    CHEER_POINTS,
    DAILY_COMPLETION_BONUS,
    HELP_FRIEND_POINTS,
    LATE_TASK_POINTS,
    MISSED_TASK_POINTS,
    ON_TIME_TASK_POINTS,
    cheer_points,
    daily_completion_bonus,
    task_completion_points,
)


def test_on_time_task_awards_ten_points():
    assert task_completion_points("on_time") == ON_TIME_TASK_POINTS == 10


def test_late_task_awards_three_points():
    assert task_completion_points("late") == LATE_TASK_POINTS == 3


def test_missed_task_awards_zero_points():
    assert task_completion_points("missed") == MISSED_TASK_POINTS == 0


def test_invalid_task_status_raises_error():
    with pytest.raises(ValueError):
        task_completion_points("pending")


def test_completing_all_daily_tasks_awards_bonus():
    assert daily_completion_bonus(5, 5) == DAILY_COMPLETION_BONUS == 20


def test_incomplete_day_does_not_award_bonus():
    assert daily_completion_bonus(5, 4) == 0


def test_zero_tasks_does_not_award_bonus():
    assert daily_completion_bonus(0, 0) == 0


def test_negative_task_count_raises_error():
    with pytest.raises(ValueError):
        daily_completion_bonus(-1, 0)


def test_completed_tasks_cannot_exceed_total_tasks():
    with pytest.raises(ValueError):
        daily_completion_bonus(3, 4)


def test_cheer_awards_one_point():
    assert cheer_points(0) == CHEER_POINTS == 1


def test_fifth_cheer_is_allowed():
    assert cheer_points(4) == 1


def test_sixth_cheer_is_not_allowed():
    assert cheer_points(5) == 0


def test_negative_cheer_count_raises_error():
    with pytest.raises(ValueError):
        cheer_points(-1)


def test_helping_a_friend_is_worth_five_points():
    assert HELP_FRIEND_POINTS == 5