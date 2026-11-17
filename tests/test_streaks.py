
import pytest

from app.services.streaks import is_streak_day


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
