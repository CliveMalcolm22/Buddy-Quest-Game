
import pytest

from app.services.streaks import is_streak_day
from app.services.streaks import calculate_current_streak, is_streak_day

def test_completing_80_percent_of_tasks_qualifies_for_streak():
    assert is_streak_day(5, 4) is True


def test_completing_more_than_80_percent_qualifies_for_streak():
    assert is_streak_day(5, 5) is True


def test_completing_less_than_80_percent_does_not_qualify():
    assert is_streak_day(5, 3) is False


def test_zero_tasks_does_not_qualify_for_streak():
    assert is_streak_day(0, 0) is False


def test_negative_task_count_raises_error():
    with pytest.raises(ValueError):
        is_streak_day(-1, 0)


def test_completed_tasks_cannot_exceed_total_tasks():
    with pytest.raises(ValueError):
        is_streak_day(3, 4)

def test_three_consecutive_qualifying_days_give_three_day_streak():
    assert calculate_current_streak([True, True, True]) == 3


def test_non_qualifying_day_breaks_streak():
    assert calculate_current_streak(
        [True, True, False, True, True]
    ) == 2


def test_streak_starts_again_after_a_missed_day():
    assert calculate_current_streak(
        [True, True, False]
    ) == 0


def test_empty_days_give_zero_streak():
    assert calculate_current_streak([]) == 0


def test_single_qualifying_day_gives_one_day_streak():
    assert calculate_current_streak([True]) == 1
